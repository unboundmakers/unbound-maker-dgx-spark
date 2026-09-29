import hashlib
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
sys.path.insert(0, str(SKILL.parent/'unbound-maker-asset-builder/scripts'))
sys.path.insert(0, str(SKILL.parent/'unbound-maker-personality-builder/scripts'))


class ContractTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('scene_builder'), 'Scene Builder has no executable entry yet')
        import scene_builder
        return scene_builder

    def test_defaults_and_mode_mapping(self):
        module = self.module()
        for scene, mode in [('meadow','story'), ('space','story'), ('moon','experiment')]:
            request = module.validate_request({'schema_version':1, 'scene_id':scene})
            self.assertEqual(request['mode'], mode)
            self.assertEqual(request['spawn_id'], 'start')
            self.assertEqual(request['heading_degrees'], 0.)

    def test_invalid_requests(self):
        module = self.module()
        for patch in [{'scene_id':'unknown'}, {'schema_version':True}, {'mode':'story'},
                      {'heading_degrees':True}, {'heading_degrees':float('nan')},
                      {'heading_degrees':181}, {'spawn_id':'inside_rock'}, {'mass':6}, {'command':'echo hi'}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                module.validate_request({'schema_version':1,'scene_id':'moon', **patch})

    def test_capabilities_without_usd(self):
        self.module()
        script = SKILL/'scripts/scene_builder.py'
        result = subprocess.run([sys.executable,'-S',str(script),'capabilities'], text=True, capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(set(json.loads(result.stdout)['scenes']), {'meadow','space','moon'})

    def test_package_path_restrictions(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ('../escape','/tmp/x','https://a','a\\b',''):
                with self.subTest(name=name),self.assertRaises(ValueError):
                    module.local_file(root,name)

    def test_duplicate_request_cli_fails_without_output(self):
        self.module()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'request.json').write_text('{"schema_version":1,"scene_id":"moon","scene_id":"space"}')
            result=subprocess.run([sys.executable,str(SKILL/'scripts/scene_builder.py'),'build',
                                   '--request',str(root/'request.json'),'--assets',d,'--character',d,
                                   '--output',str(root/'out')],text=True,capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(json.loads(result.stdout)['status'],'failed')
            self.assertFalse((root/'out').exists())


class BuildTests(unittest.TestCase):
    module = ContractTests.module
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = Path(os.environ.get('UNBOUND_SCENE_ASSETS', str(SKILL.parents[2]/'unbound-maker-scene-builder/meadow-v0.3')))
        self.assertTrue(self.assets.is_dir(), 'Set UNBOUND_SCENE_ASSETS to the trusted template root')
        from asset_builder import build_asset
        from personality_builder import build_personality
        self.character = self.root/'character'
        build_asset({'schema_version':1,'template_id':'flyingcat-v1','scale':1.5},self.root/'base')
        build_personality(self.root/'base',{'schema_version':1,'adapter':'flyingcat-v1'},self.character)

    def test_all_templates_portable_structure_and_character(self):
        from pxr import Usd, UsdGeom, UsdPhysics, UsdSkel
        module = self.module()
        original = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.character.rglob('*') if p.is_file()}
        for scene, mode, gravity in [('meadow','story',9.81),('space','story',0.),('moon','experiment',1.62)]:
            with self.subTest(scene=scene):
                output = self.root/scene
                manifest = module.build_scene({'schema_version':1,'scene_id':scene,'heading_degrees':25}, self.assets,self.character,output)
                self.assertEqual(manifest['status'],'succeeded')
                self.assertFalse(manifest['isaac_sim_tested'])
                self.assertEqual(manifest['request']['mode'],mode)
                moved = self.root/(scene+'-moved')
                output.rename(moved)
                stage = Usd.Stage.Open(str(moved/'scene.usda'))
                self.assertEqual(str(stage.GetDefaultPrim().GetPath()),'/World')
                self.assertEqual(UsdGeom.GetStageUpAxis(stage),'Z')
                self.assertAlmostEqual(UsdPhysics.Scene.Get(stage,'/World/Physics').GetGravityMagnitudeAttr().Get(),gravity,places=5)
                character = stage.GetPrimAtPath('/World/Character')
                self.assertFalse(character.HasAPI(UsdPhysics.RigidBodyAPI))
                self.assertEqual(character.GetAttribute('xformOp:rotateZ').Get(),25.)
                skels=[p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
                self.assertEqual(len(skels),1)
                self.assertTrue(stage.GetPrimAtPath('/World/PreviewCamera'))
                self.assertEqual(bool(stage.GetPrimAtPath('/World/Astronaut')),scene=='moon')
                self.assertEqual(bool(stage.GetPrimAtPath('/World/LunarVehicles')),scene=='moon')
                self.assertGreater(sum(p.IsA(UsdGeom.PointInstancer) for p in stage.Traverse()),0)
                self.assertGreater(sum(p.HasAPI(UsdPhysics.CollisionAPI) for p in stage.Traverse()),0)
                if scene in ('meadow','space'):
                    variants=[p.GetVariantSet('detail') for p in stage.Traverse() if p.HasVariantSets() and p.GetVariantSet('detail').GetVariantNames()]
                    self.assertTrue(variants)
                    self.assertTrue(all({'near','far'}.issubset(v.GetVariantNames()) for v in variants))
                    for variant in variants:
                        variant.SetVariantSelection('far')
                    self.assertTrue(all(v.GetVariantSelection()=='far' for v in variants))
                if scene=='moon':
                    self.assertEqual(json.loads((moved/'scene-config.json').read_text())['runtime']['duration_s'],10)
                module.validate_scene(moved/'scene.usda',moved,scene)
                for item in manifest['files']:
                    self.assertEqual(hashlib.sha256((moved/item['path']).read_bytes()).hexdigest(),item['sha256'])
                before = len(list(stage.Traverse()))
                stage.Unload('/World/Environment')
                self.assertLess(len(list(stage.Traverse())),before)
                stage.Load('/World/Environment')
                self.assertEqual(len(list(stage.Traverse())),before)
        self.assertEqual(original,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.character.rglob('*') if p.is_file()})

    def test_missing_catalog_asset_fails_before_output(self):
        module = self.module()
        empty = self.root/'empty'
        empty.mkdir()
        with self.assertRaises(ValueError):
            module.build_scene({'schema_version':1,'scene_id':'meadow'},empty,self.character,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_existing_output_and_bad_character_rejected(self):
        module = self.module()
        with self.assertRaises(ValueError):
            module.build_scene({'schema_version':1,'scene_id':'moon'},self.assets,self.character,self.character)
        (self.character/'personality.usda').write_text('#usda 1.0\n')
        with self.assertRaises(ValueError):
            module.build_scene({'schema_version':1,'scene_id':'meadow'},self.assets,self.character,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_asset_builder_output_also_supported(self):
        module=self.module()
        result=module.build_scene({'schema_version':1,'scene_id':'space'},self.assets,self.root/'base',self.root/'plain')
        self.assertEqual(result['character']['kind'],'unbound-maker-asset-builder')
        self.assertFalse((self.root/'plain/environment/assets/moon').exists())

    def test_missing_texture_after_build_is_not_success(self):
        module=self.module()
        output=self.root/'space'
        module.build_scene({'schema_version':1,'scene_id':'space'},self.assets,self.character,output)
        (output/'environment/assets/space/nasa/earth-4k.jpg').unlink()
        with self.assertRaises(ValueError):
            module.validate_scene(output/'scene.usda',output,'space')


if __name__ == '__main__':
    unittest.main()
