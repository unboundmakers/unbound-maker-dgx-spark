"""Assemble pinned local environment templates and an existing character package."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import sys

SKILL = Path(__file__).resolve().parents[1]
VERSION = '0.1.0'
MODES = {'meadow':'story', 'space':'story', 'moon':'experiment'}
BUILTIN_MDL = {'OmniPBR.mdl', 'OmniGlass.mdl'}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key: '+key)
        value[key] = item
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def write_json(path, data):
    Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def validate_request(value):
    if not isinstance(value,dict) or set(value)-{'schema_version','scene_id','mode','spawn_id','heading_degrees'}:
        raise ValueError('Unsupported scene request fields.')
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ValueError('schema_version must be integer 1.')
    scene=value.get('scene_id')
    if not isinstance(scene,str) or scene not in MODES:
        raise ValueError('scene_id must be meadow, space or moon.')
    mode=value.get('mode',MODES[scene])
    if mode != MODES[scene]:
        raise ValueError('This template requires mode='+MODES[scene])
    if value.get('spawn_id','start') != 'start':
        raise ValueError('Only the inspected start spawn is supported in v0.1.0.')
    heading=value.get('heading_degrees',0.)
    if type(heading) not in (int,float) or not math.isfinite(heading) or not -180 <= heading <= 180:
        raise ValueError('heading_degrees must be a number within -180..180.')
    return dict(schema_version=1,scene_id=scene,mode=mode,spawn_id='start',heading_degrees=float(heading))


def local_file(root, relative):
    if not isinstance(relative,str) or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe package path.')
    part=PurePosixPath(relative)
    if part.is_absolute() or '..' in part.parts or str(part)!=relative or relative in ('','.'): 
        raise ValueError('Unsafe package path: '+relative)
    path=root/relative
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Missing or escaping package file: '+relative)
    return path


def checked_files(root, entries):
    if not isinstance(entries,list) or not entries:
        raise ValueError('Empty file inventory.')
    found={}
    for item in entries:
        name=item['path']
        if name in found:
            raise ValueError('Duplicate file inventory path.')
        path=local_file(root,name)
        if digest(path)!=item['sha256']:
            raise ValueError('File hash mismatch: '+name)
        found[name]=path
    return found


def character_inventory(root):
    root=Path(root).resolve()
    manifest=read_json(local_file(root,'manifest.json'))
    kind=manifest.get('skill')
    entry={'unbound-maker-asset-builder':'asset.usda',
           'unbound-maker-personality-builder':'personality.usda'}.get(kind)
    if not entry or manifest.get('status')!='succeeded' or manifest.get('skill_version')!='0.1.0':
        raise ValueError('Expected an Asset or Personality Builder 0.1.0 output.')
    if manifest.get('entrypoint')!=entry or manifest.get('default_prim')!='/FlyingCat':
        raise ValueError('Unsupported character entrypoint.')
    files=checked_files(root,manifest.get('files'))
    if entry not in files:
        raise ValueError('Character entrypoint missing from inventory.')
    files['manifest.json']=root/'manifest.json'
    return files,dict(kind=kind,entrypoint=entry,source_sha256=digest(root/'manifest.json'))


def copy_checked(files, root, expected):
    for name,path in files.items():
        dest=root/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,dest)
        if digest(dest)!=expected[name]:
            raise ValueError('File changed during copy: '+name)


def validate_scene(entry, package, scene):
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, UsdSkel, UsdUtils
    layers,assets,missing=UsdUtils.ComputeAllDependencies(str(entry))
    allowed=BUILTIN_MDL if scene=='moon' else set()
    if set(missing)-allowed:
        raise ValueError('Unresolved scene dependencies: '+str(missing))
    paths=[Path(l.realPath) for l in layers]+[Path(p) for p in assets]
    for path in paths:
        if not path.is_file() or not path.resolve().is_relative_to(package.resolve()):
            raise ValueError('Dependency outside package: '+str(path))
    stage=Usd.Stage.Open(str(entry))
    if str(stage.GetDefaultPrim().GetPath())!='/World' or UsdGeom.GetStageUpAxis(stage)!='Z' or UsdGeom.GetStageMetersPerUnit(stage)!=1.:
        raise ValueError('Scene must use /World, Z up, meters.')
    skels=[p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
    if len(skels)!=1 or not str(skels[0].GetPath()).startswith('/World/Character/'):
        raise ValueError('Missing character skeleton.')
    unbound=[]
    for p in stage.Traverse():
        if p.IsA(UsdGeom.Mesh) and UsdGeom.Imageable(p).ComputeVisibility()!='invisible':
            if not UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()[0]:
                unbound.append(str(p.GetPath()))
    if unbound:
        raise ValueError('Unbound mesh materials: '+str(unbound[:8]))
    return dict(status='passed',scope='CPU USD structure, not rendering or contact simulation',
                layer_count=len(layers),texture_count=len(assets),
                runtime_mdl_dependencies=sorted(allowed),unresolved_non_runtime_dependencies=[],
                point_instancer_count=sum(p.IsA(UsdGeom.PointInstancer) for p in stage.Traverse()),
                collider_prim_count=sum(p.HasAPI(UsdPhysics.CollisionAPI) for p in stage.Traverse()),
                variant_prim_count=sum(bool(p.GetVariantSets().GetNames()) for p in stage.Traverse()),
                isaac_sim_tested=False)


def build_scene(request, assets, character, output):
    request=validate_request(request)
    assets,output=Path(assets).resolve(),Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('Choose a new output directory under an existing parent.')
    catalog=read_json(SKILL/'assets/catalog.json')
    spec=catalog['scenes'][request['scene_id']]
    env_files=checked_files(assets,spec['files'])
    char_files,char_info=character_inventory(character)
    # Pin copies before writing any output. Hashes are integrity checks, not signatures.
    env_hashes={i['path']:i['sha256'] for i in spec['files']}
    char_hashes={n:digest(p) for n,p in char_files.items()}
    from pxr import Gf, Usd, UsdGeom, UsdPhysics
    output.mkdir()
    copy_checked(env_files,output/'environment',env_hashes)
    copy_checked(char_files,output/'character',char_hashes)
    stage=Usd.Stage.CreateNew(str(output/'scene.usda'))
    world=UsdGeom.Xform.Define(stage,'/World')
    stage.SetDefaultPrim(world.GetPrim())
    UsdGeom.SetStageUpAxis(stage,'Z')
    UsdGeom.SetStageMetersPerUnit(stage,1.)
    for component in spec['components']:
        prim=UsdGeom.Xform.Define(stage,component['prim']).GetPrim()
        prim.GetPayloads().AddPayload('./environment/'+component['entry'],component['source_prim'])
    actor=UsdGeom.Xform.Define(stage,'/World/Character')
    actor.AddTranslateOp().Set(Gf.Vec3d(*spec['spawn']))
    actor.AddRotateZOp().Set(request['heading_degrees'])
    pose=UsdGeom.Xform.Define(stage,'/World/Character/Pose')
    visual=UsdGeom.Xform.Define(stage,'/World/Character/Pose/Visual')
    visual.GetPrim().GetReferences().AddReference('./character/'+char_info['entrypoint'],'/FlyingCat')
    bound=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render']).ComputeLocalBound(visual.GetPrim()).ComputeAlignedRange()
    if bound.IsEmpty() or not all(math.isfinite(v) for v in [*bound.GetMin(),*bound.GetMax()]):
        raise ValueError('Character bounds are invalid.')
    # Character origin denotes the support plane. The full visual is offset above it.
    pose.AddTranslateOp().Set(Gf.Vec3d(0,0,-bound.GetMin()[2]+.05))
    if request['scene_id']=='moon':
        astronaut=UsdGeom.Xformable(stage.GetPrimAtPath('/World/Astronaut'))
        astro_bound=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render']).ComputeLocalBound(astronaut.GetPrim()).ComputeAlignedRange()
        factor=2.5*bound.GetSize()[2]/astro_bound.GetSize()[2]
        astronaut.AddTranslateOp().Set(Gf.Vec3d(4,6,spec['astronaut_ground_z']-astro_bound.GetMin()[2]*factor))
        astronaut.AddScaleOp().Set(Gf.Vec3f(factor))
        collision=UsdGeom.Capsule.Define(stage,'/World/AstronautContact')
        height=2.5*bound.GetSize()[2]
        collision.CreateAxisAttr('Z'); collision.CreateRadiusAttr(height*.17); collision.CreateHeightAttr(height*.66)
        collision.AddTranslateOp().Set(Gf.Vec3d(4,6,spec['astronaut_ground_z']+height/2))
        collision.CreateVisibilityAttr('invisible')
        UsdPhysics.CollisionAPI.Apply(collision.GetPrim())
    physics=UsdPhysics.Scene.Define(stage,'/World/Physics')
    physics.CreateGravityDirectionAttr(Gf.Vec3f(0,0,-1))
    physics.CreateGravityMagnitudeAttr(spec['gravity_m_s2'])
    eye,target=Gf.Vec3d(*spec['camera_eye']),Gf.Vec3d(*spec['camera_target'])
    camera=UsdGeom.Camera.Define(stage,'/World/PreviewCamera')
    camera.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(eye,target,Gf.Vec3d(0,0,1)).GetInverse())
    camera.CreateFocalLengthAttr(21)
    camera.CreateClippingRangeAttr(Gf.Vec2f(.05,12000))
    stage.GetRootLayer().Save()
    config=dict(schema_version=1,request=request,character_prim='/World/Character',
                visual_prim='/World/Character/Pose/Visual',spawn_world=spec['spawn'],
                preview_camera='/World/PreviewCamera',runtime=spec['runtime'],
                renderer_settings=spec['renderer_settings'],notes=spec['notes'])
    write_json(output/'scene-config.json',config)
    checks=validate_scene(output/'scene.usda',output,request['scene_id'])
    write_json(output/'validation.json',checks)
    write_json(output/'sources.json',dict(catalog_version=catalog['version'],scene=request['scene_id'],
                                         notes=spec['notes'],environment_files=spec['files'],
                                         redistribution='Local use only; per-source release review required.'))
    manifest=dict(schema_version=1,status='succeeded',skill='unbound-maker-scene-builder',skill_version=VERSION,
                  entrypoint='scene.usda',default_prim='/World',request=request,character=char_info,
                  isaac_sim_tested=False,character_physics_ready=False,
                  runtime_mdl_dependencies=checks['runtime_mdl_dependencies'],
                  files=[dict(path=str(p.relative_to(output)),sha256=digest(p),bytes=p.stat().st_size)
                         for p in sorted(output.rglob('*')) if p.is_file()])
    manifest['package_bytes_without_manifest']=sum(i['bytes'] for i in manifest['files'])
    write_json(output/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('capabilities')
    build=sub.add_parser('build')
    for flag in ('request','assets','character','output'):
        build.add_argument('--'+flag,required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.command=='capabilities':
            result=dict(skill='unbound-maker-scene-builder',version=VERSION,scenes=MODES,
                        spawn_ids=['start'],heading_range_degrees=[-180,180],starts_simulator=False)
        else:
            result=build_scene(read_json(args.request),args.assets,args.character,args.output)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except ImportError as exc:
        error=dict(code='missing_dependency',message=str(exc))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        error=dict(code='invalid_input_or_io',message=str(exc))
    except Exception as exc:
        error=dict(code='build_failed',message=str(exc))
    print(json.dumps(dict(status='failed',error=error)))
    return 2


if __name__=='__main__':
    sys.exit(main())
