"""Audit trusted Scene Builder packages and author reversible static LOD overrides."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import sys

VERSION = '0.1.0'
MODES = {'meadow':'story', 'space':'story', 'moon':'experiment'}
MDL = {'OmniPBR.mdl', 'OmniGlass.mdl'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: '+key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_request(value):
    if not isinstance(value, dict) or set(value)-{'schema_version','profile'}:
        raise ValueError('Only schema_version and profile are supported.')
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ValueError('schema_version must be integer 1.')
    profile = value.get('profile','preserve')
    if not isinstance(profile,str) or profile not in ('preserve','preview'):
        raise ValueError('profile must be preserve or preview.')
    return dict(schema_version=1, profile=profile)


def local_file(root, name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:
        raise ValueError('Unsafe package path.')
    part = PurePosixPath(name)
    if part.is_absolute() or '..' in part.parts or str(part)!=name or name=='.':
        raise ValueError('Unsafe package path: '+name)
    path = root/name
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Missing or escaping file: '+name)
    cursor = root
    for component in part.parts:
        cursor = cursor/component
        if cursor.is_symlink():
            raise ValueError('Symlink in package: '+name)
    return path


def inventory(source):
    manifest = read_json(local_file(source,'manifest.json'))
    if (not isinstance(manifest,dict) or type(manifest.get('schema_version')) is not int or
        manifest['schema_version']!=1 or not isinstance(manifest.get('request'),dict)):
        raise ValueError('Malformed Scene Builder manifest.')
    if (manifest.get('skill')!='unbound-maker-scene-builder' or
        manifest.get('skill_version')!=VERSION or manifest.get('status')!='succeeded' or
        manifest.get('entrypoint')!='scene.usda' or manifest.get('default_prim')!='/World'):
        raise ValueError('Expected a successful Scene Builder 0.1.0 package.')
    scene = manifest.get('request',{}).get('scene_id')
    if not isinstance(scene,str) or scene not in MODES or manifest['request'].get('mode')!=MODES[scene]:
        raise ValueError('Unsupported scene/mode.')
    entries = manifest.get('files')
    if not isinstance(entries,list) or not entries:
        raise ValueError('Missing file inventory.')
    files = {}
    for item in entries:
        if not isinstance(item,dict) or not {'path','sha256','bytes'}.issubset(item):
            raise ValueError('Malformed file inventory.')
        name = item['path']
        path = local_file(source,name)
        if name in files or name=='manifest.json':
            raise ValueError('Duplicate or reserved inventory entry.')
        if digest(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
            raise ValueError('File integrity mismatch: '+name)
        files[name] = dict(path=path,sha256=item['sha256'])
    for required in ('scene.usda','scene-config.json','sources.json','validation.json'):
        if required not in files:
            raise ValueError('Required file not inventoried: '+required)
    config = read_json(files['scene-config.json']['path'])
    if not isinstance(config,dict) or config.get('request')!=manifest['request']:
        raise ValueError('Scene config and manifest disagree.')
    files['manifest.json'] = dict(path=source/'manifest.json',sha256=digest(source/'manifest.json'))
    return manifest, files


def dependencies(entry, root, scene):
    from pxr import UsdUtils
    layers, assets, missing = UsdUtils.ComputeAllDependencies(str(entry))
    allowed = MDL if scene=='moon' else set()
    if set(missing)-allowed:
        raise ValueError('Unresolved dependencies: '+str(missing))
    paths = set()
    for path in [Path(l.realPath) for l in layers]+[Path(p) for p in assets]:
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Dependency outside package: '+str(path))
        name = str(path.resolve().relative_to(root.resolve()))
        local_file(root,name)
        paths.add(name)
    return dict(files=sorted(paths),layer_count=len(layers),asset_count=len(assets),
                runtime_mdl_dependencies=sorted(allowed))


def prims(stage):
    from pxr import Usd
    return list(Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()))


def metrics(stage):
    from pxr import UsdGeom, UsdPhysics
    result = dict(point_instancer_count=0,point_instancer_placements=0,
                  collider_prims_including_instance_proxies=0,
                  visible_mesh_points_expanded_native_instances=0,native_instance_count=0,
                  payload_prim_count=0,detail_selections={})
    for p in prims(stage):
        result['native_instance_count'] += int(p.IsInstance())
        result['payload_prim_count'] += int(p.HasPayload())
        result['collider_prims_including_instance_proxies'] += int(p.HasAPI(UsdPhysics.CollisionAPI))
        if p.IsA(UsdGeom.Mesh) and UsdGeom.Imageable(p).ComputeVisibility()!='invisible':
            result['visible_mesh_points_expanded_native_instances'] += len(UsdGeom.Mesh(p).GetPointsAttr().Get() or [])
        variant = p.GetVariantSet('detail')
        if variant.GetVariantNames():
            key = variant.GetVariantSelection()
            result['detail_selections'][key] = result['detail_selections'].get(key,0)+1
        if p.IsA(UsdGeom.PointInstancer):
            pi = UsdGeom.PointInstancer(p)
            positions = pi.GetPositionsAttr().Get()
            indices = pi.GetProtoIndicesAttr().Get()
            targets = pi.GetPrototypesRel().GetTargets()
            if positions is None or indices is None or len(positions)!=len(indices) or not targets:
                raise ValueError('Invalid PointInstancer arrays: '+str(p.GetPath()))
            if any(not stage.GetPrimAtPath(t) for t in targets) or any(i<0 or i>=len(targets) for i in indices):
                raise ValueError('Invalid PointInstancer prototypes: '+str(p.GetPath()))
            if any(not math.isfinite(v) for pos in positions for v in pos):
                raise ValueError('Nonfinite PointInstancer position.')
            for attribute in (pi.GetScalesAttr(),pi.GetOrientationsAttr(),pi.GetIdsAttr()):
                value = attribute.Get()
                if value is not None and len(value) not in (0,len(indices)):
                    raise ValueError('Inconsistent PointInstancer optional array: '+str(attribute.GetPath()))
            result['point_instancer_count'] += 1
            result['point_instancer_placements'] += len(indices)
    return result


def canonical(value):
    from pxr import Sdf
    if isinstance(value,Sdf.AssetPath):
        return value.path
    if value is None or isinstance(value,(str,bool,int,float)):
        return value
    try:
        return [canonical(v) for v in value]
    except TypeError:
        return str(value)


def protected_state(stage):
    """Fingerprint composed contacts, character, lights, cameras and their ancestors."""
    from pxr import Sdf, UsdGeom, UsdPhysics
    all_prims = prims(stage)
    contacts = [p.GetPath() for p in all_prims if p.HasAPI(UsdPhysics.CollisionAPI)]
    selected = set()
    for p in all_prims:
        path = p.GetPath()
        protect = (path.HasPrefix(Sdf.Path('/World/Character')) or path in contacts or
                   p.IsA(UsdGeom.Camera) or p.IsA(UsdPhysics.Scene) or
                   p.HasAPI(UsdPhysics.RigidBodyAPI) or p.GetTypeName().endswith('Light'))
        if p.IsA(UsdGeom.PointInstancer):
            targets = UsdGeom.PointInstancer(p).GetPrototypesRel().GetTargets()
            protect = protect or any(c.HasPrefix(t) for c in contacts for t in targets)
        if protect:
            while path != Sdf.Path.absoluteRootPath:
                selected.add(str(path))
                path = path.GetParentPath()
    h = hashlib.sha256()
    for path in sorted(selected):
        p = stage.GetPrimAtPath(path)
        record = dict(path=path,type=p.GetTypeName(),apis=list(p.GetAppliedSchemas()),
                      instanceable=p.IsInstanceable(),attributes={},relationships={})
        for attr in p.GetAttributes():
            record['attributes'][attr.GetName()] = dict(value=canonical(attr.Get()),
                samples=[[t,canonical(attr.Get(t))] for t in attr.GetTimeSamples()],
                connections=[str(c) for c in attr.GetConnections()])
        for rel in p.GetRelationships():
            record['relationships'][rel.GetName()] = [str(t) for t in rel.GetTargets()]
        h.update(json.dumps(record,sort_keys=True,allow_nan=False).encode())
    return h.hexdigest()


def validate_stage(stage):
    from pxr import UsdGeom, UsdShade, UsdSkel
    if (str(stage.GetDefaultPrim().GetPath())!='/World' or UsdGeom.GetStageUpAxis(stage)!='Z'
        or UsdGeom.GetStageMetersPerUnit(stage)!=1.):
        raise ValueError('Expected /World, Z up and meter units.')
    skeletons = [p for p in prims(stage) if p.IsA(UsdSkel.Skeleton)]
    if len(skeletons)!=1 or not str(skeletons[0].GetPath()).startswith('/World/Character/'):
        raise ValueError('Expected one character skeleton.')
    for p in prims(stage):
        if p.IsA(UsdGeom.Mesh) and UsdGeom.Imageable(p).ComputeVisibility()!='invisible':
            if not UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()[0]:
                raise ValueError('Unbound mesh material: '+str(p.GetPath()))


def apply_preview(stage, scene):
    from pxr import Usd, UsdGeom
    camera = stage.GetPrimAtPath('/World/PreviewCamera')
    if not camera or not camera.IsA(UsdGeom.Camera):
        raise ValueError('Missing preview camera.')
    cache = UsdGeom.XformCache()
    eye = cache.GetLocalToWorldTransform(camera).ExtractTranslation()
    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render'])
    candidates = []
    for p in stage.Traverse():
        path = str(p.GetPath())
        variant = p.GetVariantSet('detail')
        if variant.GetVariantSelection()!='near' or 'far' not in variant.GetVariantNames():
            continue
        if scene=='meadow' and path.startswith('/World/Environment/Environment/Tiles/') and p.GetName()=='Grass':
            center = cache.GetLocalToWorldTransform(p).ExtractTranslation()
            distance = math.hypot(center[0]-eye[0],center[1]-eye[1])
            limit = 12.
        elif scene=='space' and path.startswith('/World/Environment/Planets/') and p.GetName()=='Visual':
            bounds = bbox.ComputeWorldBound(p).ComputeAlignedRange()
            if bounds.IsEmpty():
                raise ValueError('Empty planet bounds.')
            low,high = bounds.GetMin(),bounds.GetMax()
            distance = math.sqrt(sum(max(low[i]-eye[i],0.,eye[i]-high[i])**2 for i in range(3)))
            limit = 40.
        else:
            continue
        if math.isfinite(distance) and distance>limit:
            candidates.append(dict(path=path,before='near',after='far',distance_m=round(distance,3),threshold_m=limit))
    # Collect first: recomposition invalidates prim iterators and handles.
    for change in candidates:
        if not stage.GetPrimAtPath(change['path']).GetVariantSet('detail').SetVariantSelection('far'):
            raise ValueError('Failed to set detail variant.')
    return candidates


def optimize(source, request, output):
    request = validate_request(request)
    source,output = Path(source).resolve(),Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.resolve().is_relative_to(source):
        raise ValueError('Choose a new output directory outside the input package under an existing parent.')
    manifest,files = inventory(source)
    scene = manifest['request']['scene_id']
    deps = dependencies(source/'scene.usda',source,scene)
    if set(deps['files'])-set(files):
        raise ValueError('Dependencies absent from the input inventory.')
    from pxr import Usd, UsdGeom
    original = Usd.Stage.Open(str(source/'scene.usda'))
    validate_stage(original)
    before,protected = metrics(original),protected_state(original)
    output.mkdir()
    for name,item in files.items():
        dest = output/'base'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(item['path'],dest)
        if digest(dest)!=item['sha256']:
            raise ValueError('Input changed during copy: '+name)
    stage = Usd.Stage.CreateNew(str(output/'optimized.usda'))
    stage.GetRootLayer().subLayerPaths = ['./base/scene.usda']
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    UsdGeom.SetStageUpAxis(stage,UsdGeom.GetStageUpAxis(original))
    UsdGeom.SetStageMetersPerUnit(stage,UsdGeom.GetStageMetersPerUnit(original))
    changes = apply_preview(stage,scene) if request['profile']=='preview' else []
    stage.GetRootLayer().Save()
    stage = Usd.Stage.Open(str(output/'optimized.usda'))
    validate_stage(stage)
    after = metrics(stage)
    if protected_state(stage)!=protected:
        raise ValueError('Protected physics, character, camera or lighting state changed.')
    out_deps = dependencies(output/'optimized.usda',output,scene)
    report = dict(schema_version=1,status='passed',scene=scene,request=request,
        changes=changes,before=before,after=after,protected_state_unchanged=True,
        protected_state_sha256=protected,dependency_check=out_deps,
        gpu_memory='unmeasured',frame_time='unmeasured',load_time='unmeasured',
        isaac_sim_tested=False,contact_simulation_tested=False,
        notes=['Static LOD only; movement needs Simulation Runner to restore near detail.',
               'Moon close-up terrain is unchanged; no supported visual LOD edit.',
               'Counts are structural, not VRAM, physical-shape count or rendered triangle count.',
               'All base files and all detail variants are retained; this does not reduce package bytes.'])
    report['input_package_bytes'] = sum(i['path'].stat().st_size for i in files.values())
    write_json(output/'optimization-report.json',report)
    config = read_json(source/'scene-config.json')
    config.update(scene_entrypoint='optimized.usda',base_package='base',optimization_profile=request['profile'])
    write_json(output/'scene-config.json',config)
    result = dict(schema_version=1,status='succeeded',skill='unbound-maker-scene-optimizer',skill_version=VERSION,
        entrypoint='optimized.usda',default_prim='/World',request=request,scene_id=scene,
        source_manifest_sha256=files['manifest.json']['sha256'],isaac_sim_tested=False,
        character_physics_ready=manifest.get('character_physics_ready',False),
        runtime_mdl_dependencies=deps['runtime_mdl_dependencies'],
        files=[dict(path=str(p.relative_to(output)),sha256=digest(p),bytes=p.stat().st_size)
               for p in sorted(output.rglob('*')) if p.is_file()])
    result['package_bytes_without_manifest'] = sum(i['bytes'] for i in result['files'])
    write_json(output/'manifest.json',result)
    return result


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('capabilities')
    run = sub.add_parser('optimize')
    for name in ('input','request','output'):
        run.add_argument('--'+name,required=True,type=Path)
    args = parser.parse_args()
    try:
        if args.command=='capabilities':
            result = dict(skill='unbound-maker-scene-optimizer',version=VERSION,profiles=['preserve','preview'],
                          scenes=list(MODES),static_lod_only=True,launches_gpu=False)
        else:
            result = optimize(args.input,read_json(args.request),args.output)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except (ValueError,KeyError,TypeError,OSError,RuntimeError,ImportError) as exc:
        print(json.dumps(dict(status='failed',error=str(exc)),ensure_ascii=False))
        return 2


if __name__=='__main__':
    sys.exit(main())
