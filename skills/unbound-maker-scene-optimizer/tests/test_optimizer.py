import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL/'scripts'))


class OptimizerTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('scene_optimizer'), 'Missing executable Scene Optimizer')
        import scene_optimizer
        return scene_optimizer

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = Path(os.environ.get('UNBOUND_SCENE_PACKAGES', str(SKILL.parents[1]/'artifacts')))

    def source(self, scene):
        path = self.artifacts/('scene-'+scene+'-v0.1.0')
        self.assertTrue(path.is_dir(), 'Build Scene Builder examples first; set UNBOUND_SCENE_PACKAGES')
        return path

    def test_request_contract(self):
        m = self.module()
        self.assertEqual(m.validate_request({'schema_version':1})['profile'], 'preserve')
        for patch in [{'schema_version':True}, {'profile':'fastest'}, {'profile':[]},
                      {'radius':5}, {'command':'rm'}, {'schema_version':float('nan')}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                m.validate_request({'schema_version':1, **patch})

    def test_capabilities_without_usd(self):
        self.module()
        result = subprocess.run([sys.executable,'-S',str(SKILL/'scripts/scene_optimizer.py'),'capabilities'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['profiles'],['preserve','preview'])

    def test_malformed_manifest_is_a_contract_error(self):
        m = self.module()
        base = m.read_json(self.source('space')/'manifest.json')
        for value in [[],None,{**base,'schema_version':True},{**base,'request':[]}]:
            m.write_json(self.root/'manifest.json',value)
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                m.inventory(self.root)

    def test_duplicate_keys_and_unsafe_paths(self):
        m = self.module()
        request = self.root/'bad.json'
        request.write_text('{"schema_version":1,"profile":"preserve","profile":"preview"}')
        with self.assertRaises(ValueError):
            m.read_json(request)
        for path in ['../file','/tmp/file','a\\b','https://x','./file','']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                m.local_file(self.root,path)
        (self.root/'link').symlink_to(self.source('space')/'scene.usda')
        with self.assertRaises(ValueError):
            m.local_file(self.root,'link')

    def test_preserve_all_scenes_and_relocation(self):
        from pxr import Usd
        m = self.module()
        for name in ['meadow','space','moon']:
            with self.subTest(scene=name):
                source = self.source(name)
                original = {str(p.relative_to(source)):m.digest(p) for p in source.rglob('*') if p.is_file()}
                out = self.root/name
                result = m.optimize(source,{'schema_version':1},out)
                self.assertEqual(result['status'],'succeeded')
                self.assertFalse(result['isaac_sim_tested'])
                report = m.read_json(out/'optimization-report.json')
                self.assertEqual(report['changes'],[])
                self.assertEqual(report['before'],report['after'])
                self.assertEqual(report['gpu_memory'],'unmeasured')
                self.assertTrue(report['protected_state_unchanged'])
                moved = self.root/(name+'-moved')
                out.rename(moved)
                m.dependencies(moved/'optimized.usda',moved,name)
                stage = Usd.Stage.Open(str(moved/'optimized.usda'))
                count = len(list(stage.Traverse()))
                stage.Unload('/World/Environment')
                self.assertLess(len(list(stage.Traverse())),count)
                stage.Load('/World/Environment')
                self.assertEqual(len(list(stage.Traverse())),count)
                for item in result['files']:
                    self.assertEqual(m.digest(moved/item['path']),item['sha256'])
                self.assertEqual(original,{str(p.relative_to(source)):m.digest(p) for p in source.rglob('*') if p.is_file()})

    def test_preview_reduces_existing_visual_detail_only(self):
        m = self.module()
        for name in ['meadow','space','moon']:
            with self.subTest(scene=name):
                out = self.root/name
                m.optimize(self.source(name),{'schema_version':1,'profile':'preview'},out)
                r = m.read_json(out/'optimization-report.json')
                self.assertTrue(r['protected_state_unchanged'])
                self.assertEqual(r['before']['collider_prims_including_instance_proxies'],r['after']['collider_prims_including_instance_proxies'])
                if name == 'moon':
                    self.assertEqual(r['changes'],[])
                else:
                    self.assertTrue(r['changes'])
                    self.assertTrue(all(c['before']=='near' and c['after']=='far' for c in r['changes']))
                    metric = 'point_instancer_placements' if name=='meadow' else 'visible_mesh_points_expanded_native_instances'
                    self.assertLess(r['after'][metric],r['before'][metric])

    def test_bad_hash_and_existing_output_fail_without_manifest(self):
        m = self.module()
        with self.assertRaises(ValueError):
            m.optimize(self.source('space'),{'schema_version':1},self.root)
        source = self.root/'input'
        shutil.copytree(self.source('space'),source)
        (source/'scene.usda').write_text('#usda 1.0\n')
        with self.assertRaises(ValueError):
            m.optimize(source,{'schema_version':1},self.root/'bad')
        self.assertFalse((self.root/'bad/manifest.json').exists())

    def test_nested_output_and_foreign_manifest_rejected(self):
        m = self.module()
        source = self.root/'input'
        shutil.copytree(self.source('space'),source)
        with self.assertRaises(ValueError):
            m.optimize(source,{'schema_version':1},source/'nested')
        manifest = m.read_json(source/'manifest.json')
        manifest['skill'] = 'arbitrary-usd'
        m.write_json(source/'manifest.json',manifest)
        with self.assertRaises(ValueError):
            m.optimize(source,{'schema_version':1},self.root/'bad')

    def test_missing_texture_and_unlisted_dependency_rejected(self):
        m = self.module()
        source = self.root/'input'
        shutil.copytree(self.source('space'),source)
        manifest = m.read_json(source/'manifest.json')
        texture = 'environment/assets/space/nasa/earth-4k.jpg'
        manifest['files'] = [i for i in manifest['files'] if i['path']!=texture]
        m.write_json(source/'manifest.json',manifest)
        with self.assertRaises(ValueError):
            m.optimize(source,{'schema_version':1},self.root/'unlisted')
        (source/texture).unlink()
        with self.assertRaises(ValueError):
            m.dependencies(source/'scene.usda',source,'space')

    def test_instancer_arrays_checked(self):
        from pxr import Usd, UsdGeom
        m = self.module()
        stage = Usd.Stage.CreateInMemory()
        pi = UsdGeom.PointInstancer.Define(stage,'/I')
        cube = UsdGeom.Cube.Define(stage,'/I/P')
        pi.CreatePrototypesRel().SetTargets([cube.GetPath()])
        pi.CreatePositionsAttr([(0,0,0)])
        pi.CreateProtoIndicesAttr([2])
        with self.assertRaises(ValueError):
            m.metrics(stage)
        pi.GetProtoIndicesAttr().Set([0])
        self.assertEqual(m.metrics(stage)['point_instancer_placements'],1)
        pi.CreateScalesAttr([(1,1,1),(1,1,1)])
        with self.assertRaises(ValueError):
            m.metrics(stage)

    def test_variant_that_changes_contacts_is_rejected(self):
        from pxr import Usd, UsdGeom, UsdPhysics
        m = self.module()
        source = self.root/'input'
        shutil.copytree(self.source('space'),source)
        stage = Usd.Stage.Open(str(source/'scene.usda'))
        variant = stage.GetPrimAtPath('/World/Environment/Planets/Helios/Visual').GetVariantSet('detail')
        variant.SetVariantSelection('far')
        with variant.GetVariantEditContext():
            c = UsdGeom.Cube.Define(stage,'/World/Environment/Planets/Helios/Visual/UnexpectedContact')
            c.CreateVisibilityAttr('invisible')
            UsdPhysics.CollisionAPI.Apply(c.GetPrim())
        variant.SetVariantSelection('near')
        stage.GetRootLayer().Save()
        manifest = m.read_json(source/'manifest.json')
        for item in manifest['files']:
            if item['path']=='scene.usda':
                item.update(sha256=m.digest(source/'scene.usda'),bytes=(source/'scene.usda').stat().st_size)
        m.write_json(source/'manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'Protected'):
            m.optimize(source,{'schema_version':1,'profile':'preview'},self.root/'bad')
        self.assertFalse((self.root/'bad/manifest.json').exists())

    def test_cli_error_has_nonzero_exit_and_no_success_manifest(self):
        self.module()
        request = self.root/'bad.json'
        request.write_text('{"schema_version":1,"profile":"unknown"}')
        result = subprocess.run([sys.executable,str(SKILL/'scripts/scene_optimizer.py'),'optimize',
                                 '--input',str(self.source('space')),'--request',str(request),
                                 '--output',str(self.root/'bad')],text=True,capture_output=True)
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)['status'],'failed')
        self.assertFalse((self.root/'bad').exists())

    def test_protected_state_detects_colliders_character_and_camera(self):
        from pxr import Usd, UsdGeom, UsdPhysics
        m = self.module()
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(stage,'/World')
        c = UsdGeom.Cube.Define(stage,'/World/Rock')
        UsdPhysics.CollisionAPI.Apply(c.GetPrim())
        actor = UsdGeom.Xform.Define(stage,'/World/Character')
        camera = UsdGeom.Camera.Define(stage,'/World/Camera')
        baseline = m.protected_state(stage)
        c.GetSizeAttr().Set(5)
        self.assertNotEqual(baseline,m.protected_state(stage))
        baseline = m.protected_state(stage)
        actor.AddTranslateOp().Set((1,0,0))
        self.assertNotEqual(baseline,m.protected_state(stage))
        baseline = m.protected_state(stage)
        camera.GetFocalLengthAttr().Set(30)
        self.assertNotEqual(baseline,m.protected_state(stage))


if __name__ == '__main__':
    unittest.main()
