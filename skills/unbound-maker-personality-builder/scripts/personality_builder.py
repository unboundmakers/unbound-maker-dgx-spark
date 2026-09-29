"""Package manual expressions for a verified flyingcat-v1 Asset Builder output."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from personality import EXPRESSIONS, PersonalityController, validate_profile

VERSION = '0.1.0'
SOURCE_SHA256 = 'a11089da650a12098be3fc71292d296bb173e5db60d17ed645e94d7ca0a2cc88'
INPUT_FILES = ('asset.usda', 'sources/flyingcat-v1.usdc', 'request.json', 'provenance.json', 'validation.json')


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def expected_asset_layer(request):
    """Recreate the small permitted wrapper WITHOUT resolving its USD references."""
    from pxr import Gf, Sdf, Usd, UsdGeom
    if not isinstance(request, dict) or set(request) - {'schema_version', 'template_id', 'scale', 'body_color'}:
        raise ValueError('Unsupported Asset Builder request.')
    if type(request.get('schema_version')) is not int or request['schema_version'] != 1 or request.get('template_id') != 'flyingcat-v1':
        raise ValueError('Unsupported Asset Builder template.')
    scale = request.get('scale', 1.)
    if type(scale) not in (int, float) or not .5 <= scale <= 2.:
        raise ValueError('Unsupported asset scale.')
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, 'Z')
    UsdGeom.SetStageMetersPerUnit(stage, 1.)
    root = UsdGeom.Xform.Define(stage, '/FlyingCat')
    stage.SetDefaultPrim(root.GetPrim())
    root.AddScaleOp(opSuffix='assetScale').Set(Gf.Vec3f(scale))
    if 'body_color' in request:
        color = request['body_color']
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Unsupported asset color.')
        rgb = [int(color[i:i+2], 16)/255. for i in (1, 3, 5)]
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        stage.OverridePrim('/FlyingCat/_materials/gold/Principled_BSDF').CreateAttribute(
            'inputs:diffuseColor', Sdf.ValueTypeNames.Color3f, custom=False).Set(Gf.Vec3f(*linear))
    layer = Sdf.Layer.CreateAnonymous('permitted-asset.usda')
    layer.TransferContent(stage.GetRootLayer())
    return layer


def inspect_package(asset):
    from pxr import Sdf
    asset = Path(asset).resolve()
    for name in (*INPUT_FILES, 'manifest.json'):
        path = asset / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(asset):
            raise ValueError('Missing or unsafe package file: ' + name)
    manifest = read_json(asset/'manifest.json')
    if (manifest.get('status') != 'succeeded' or manifest.get('skill') != 'unbound-maker-asset-builder'
            or manifest.get('skill_version') != '0.1.0' or manifest.get('source_sha256') != SOURCE_SHA256):
        raise ValueError('Expected a successful Asset Builder 0.1.0 package.')
    entries = manifest.get('files', [])
    if len(entries) != len(INPUT_FILES) or {i.get('path') for i in entries} != set(INPUT_FILES):
        raise ValueError('Unexpected Asset Builder manifest file list.')
    for item in entries:
        if file_hash(asset/item['path']) != item['sha256']:
            raise ValueError('Input package hash mismatch: ' + item['path'])
    if file_hash(asset/'sources/flyingcat-v1.usdc') != SOURCE_SHA256:
        raise ValueError('The rig adapter supports only the pinned source template.')
    request = read_json(asset/'request.json')
    if request != manifest.get('request'):
        raise ValueError('Input request and manifest disagree.')
    expected = expected_asset_layer(request)
    # The temporary Usd.Stage has gone out of scope, so adding this Sdf arc cannot load a file.
    expected.GetPrimAtPath('/FlyingCat').referenceList.prependedItems = [
        Sdf.Reference('./sources/flyingcat-v1.usdc', '/CatVisual')]
    actual = Sdf.Layer.FindOrOpen(str(asset/'asset.usda'))
    if not actual or actual.ExportToString() != expected.ExportToString():
        raise ValueError('Asset wrapper differs from the supported template; external arcs are not accepted.')
    return asset, manifest


def build_personality(asset, profile, output):
    profile = validate_profile(profile)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('Choose a new output directory under an existing parent.')
    from pxr import Usd, UsdGeom, UsdUtils
    asset, source_manifest = inspect_package(asset)
    output.mkdir()
    base = output/'base'
    (base/'sources').mkdir(parents=True)
    for name in (*INPUT_FILES, 'manifest.json'):
        shutil.copyfile(asset/name, base/name)
    # Revalidate the copy before opening a composed stage (including races during copying).
    inspect_package(base)
    stage = Usd.Stage.CreateNew(str(output/'personality.usda'))
    UsdGeom.SetStageUpAxis(stage, 'Z')
    UsdGeom.SetStageMetersPerUnit(stage, 1.)
    root = UsdGeom.Xform.Define(stage, '/FlyingCat')
    root.GetPrim().GetReferences().AddReference('./base/asset.usda', '/FlyingCat')
    stage.SetDefaultPrim(root.GetPrim())
    controller = PersonalityController(stage, '/FlyingCat', layer=stage.GetRootLayer())
    stage.GetRootLayer().Save()
    layers, assets, missing = UsdUtils.ComputeAllDependencies(str(output/'personality.usda'))
    if assets or missing or any(not Path(l.realPath).resolve().is_relative_to(output.resolve()) for l in layers):
        raise ValueError('Output has unexpected external dependencies.')
    write_json(output/'personality.json', profile)
    (output/'runtime').mkdir()
    shutil.copyfile(Path(__file__).with_name('personality.py'), output/'runtime/personality.py')
    validation = {'status': 'passed', 'scope': 'CPU USD structure and default pose',
                  'default_expression': 'natural', 'fangs_visible': False,
                  'joint_count': len(controller.joints), 'fang_mesh_count': len(controller.fangs),
                  'self_contained': True, 'isaac_sim_tested': False}
    write_json(output/'validation.json', validation)
    manifest = {'schema_version': 1, 'status': 'succeeded', 'skill': 'unbound-maker-personality-builder',
                'skill_version': VERSION, 'entrypoint': 'personality.usda', 'default_prim': '/FlyingCat',
                'profile': profile, 'source_sha256': SOURCE_SHA256,
                'asset_request': source_manifest['request'], 'isaac_sim_tested': False,
                'usd_version': '.'.join(map(str, Usd.GetVersion())),
                'limitations': ['Manual visual animation only; no emotion inference or trained policy.',
                                'No changes to locomotion, physics, camera or keyboard bindings.',
                                'Runtime host must integrate the controller; opening USD alone is static.',
                                'Publication licensing and formal skill verification remain separate.'],
                'files': [{'path': str(p.relative_to(output)), 'sha256': file_hash(p), 'bytes': p.stat().st_size}
                          for p in sorted(output.rglob('*')) if p.is_file()]}
    write_json(output/'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('capabilities')
    build = sub.add_parser('build')
    build.add_argument('--asset', type=Path, required=True)
    build.add_argument('--profile', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'capabilities':
            result = {'skill': 'unbound-maker-personality-builder', 'version': VERSION,
                      'adapters': ['flyingcat-v1'], 'expressions': list(EXPRESSIONS),
                      'head_yaw_degrees': [-35, 35], 'head_tilt_degrees': [-12, 12],
                      'automatic_emotion': False, 'default_expression': 'natural'}
        else:
            result = build_personality(args.asset, read_json(args.profile), args.output)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except ImportError as exc:
        result = {'code': 'missing_dependency', 'message': 'Use Python with OpenUSD pxr: ' + str(exc)}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {'code': 'invalid_input_or_io', 'message': str(exc)}
    except Exception as exc:
        result = {'code': 'build_failed', 'message': str(exc)}
    print(json.dumps({'status': 'failed', 'error': result}))
    return 2


if __name__ == '__main__':
    sys.exit(main())
