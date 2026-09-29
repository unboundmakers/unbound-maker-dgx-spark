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

from pxr import Gf, Usd, UsdGeom, UsdShade, UsdSkel, UsdUtils, Vt

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
ASSET_SKILL = SKILL.parent / 'unbound-maker-asset-builder'
sys.path.insert(0, str(ASSET_SKILL / 'scripts'))
from asset_builder import build_asset


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class USDPersonalityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.asset = self.root / 'asset'
        build_asset({'schema_version': 1, 'template_id': 'flyingcat-v1',
                     'body_color': '#2867D7', 'scale': 1.5}, self.asset)

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('personality_builder'), 'Builder CLI is not packaged')
        import personality_builder
        return personality_builder

    def build(self):
        out = self.root / 'personality'
        manifest = self.module().build_personality(
            self.asset, {'schema_version': 1, 'adapter': 'flyingcat-v1'}, out)
        return out, manifest

    def test_portable_output_default_material_scale_source_unchanged(self):
        before = {str(p): digest(p) for p in self.asset.rglob('*') if p.is_file()}
        out, manifest = self.build()
        self.assertEqual(manifest['status'], 'succeeded')
        self.assertFalse(manifest['isaac_sim_tested'])
        for item in manifest['files']:
            self.assertEqual(digest(out / item['path']), item['sha256'])
        self.assertEqual(before, {str(p): digest(p) for p in self.asset.rglob('*') if p.is_file()})
        moved = self.root / 'moved'
        shutil.copytree(out, moved)
        shutil.rmtree(out)
        shutil.rmtree(self.asset)
        stage = Usd.Stage.Open(str(moved / 'personality.usda'))
        self.assertEqual(str(stage.GetDefaultPrim().GetPath()), '/FlyingCat')
        self.assertEqual(list(stage.GetDefaultPrim().GetAttribute('xformOp:scale:assetScale').Get()), [1.5]*3)
        color = UsdShade.Shader.Get(stage, '/FlyingCat/_materials/gold/Principled_BSDF').GetInput('diffuseColor').Get()
        self.assertAlmostEqual(color[0], 0.021219, places=5)
        fangs = [p for p in stage.Traverse() if p.IsA(UsdGeom.Mesh) and p.GetName().startswith('Fang_')]
        self.assertEqual(len(fangs), 4)
        self.assertTrue(all(UsdGeom.Imageable(p).ComputeVisibility() == 'invisible' for p in fangs))
        layers, assets, missing = UsdUtils.ComputeAllDependencies(str(moved / 'personality.usda'))
        self.assertFalse(assets or missing)
        self.assertTrue(all(Path(l.realPath).is_relative_to(moved) for l in layers))

    def test_full_body_frame_preserved_while_face_changes_without_drift(self):
        self.module()
        from personality import PersonalityState, compose_pose
        stage = Usd.Stage.Open(str(self.asset / 'asset.usda'))
        skeleton = UsdSkel.Skeleton.Get(stage, '/FlyingCat/CatRig/CatSkeleton')
        joints = list(skeleton.GetJointsAttr().Get())
        names = [str(j).rsplit('/', 1)[-1] for j in joints]
        t, r, s = UsdSkel.DecomposeTransforms(skeleton.GetRestTransformsAttr().Get())
        thigh = names.index('left_thigh')
        r[thigh] = Gf.Quatf(Gf.Rotation(Gf.Vec3d(1, 0, 0), 27).GetQuat())
        t[0] += Gf.Vec3f(0, 0, .02)
        originals = (Vt.Vec3fArray(t), Vt.QuatfArray(r), Vt.Vec3hArray(s))
        state = PersonalityState()
        state.turn(20, 4)
        state.select('angry')
        a = compose_pose(joints, t, r, s, state)
        b = compose_pose(joints, t, r, s, state)
        self.assertEqual(a, b)
        self.assertEqual((t, r, s), originals)
        for i, name in enumerate(names):
            if name not in ('head', 'face_lid_left', 'face_lid_right', 'face_gaze_left', 'face_gaze_right', 'face_mouth'):
                self.assertEqual((a[0][i], a[1][i], a[2][i]), (t[i], r[i], s[i]))
        self.assertNotEqual(a[1][names.index('head')], r[names.index('head')])

    def test_runtime_updates_and_no_physics_or_camera_edits(self):
        out, _ = self.build()
        from personality import PersonalityController
        stage = Usd.Stage.Open(str(out / 'personality.usda'))
        controller = PersonalityController(stage, '/FlyingCat')
        t, r, s = controller.body_frame
        r[1] = Gf.Quatf(Gf.Rotation(Gf.Vec3d(1, 0, 0), 22).GetQuat())
        controller.apply_frame(t, r, s)
        controller.select('angry')
        self.assertTrue(all(f.ComputeVisibility() == 'inherited' for f in controller.fangs))
        controller.turn(15, 3)
        controller.reset()
        self.assertEqual(controller.animation.GetRotationsAttr().Get()[1], r[1])
        self.assertTrue(all(f.ComputeVisibility() == 'invisible' for f in controller.fangs))
        edited = stage.GetSessionLayer().ExportToString()
        self.assertNotIn('physics:', edited)
        self.assertNotIn('Camera', edited)
        self.assertEqual(stage.GetEditTarget().GetLayer(), stage.GetRootLayer())

    def test_head_descendants_and_skin_follow_head(self):
        out, _ = self.build()
        from personality import PersonalityController
        stage = Usd.Stage.Open(str(out / 'personality.usda'))
        controller = PersonalityController(stage, '/FlyingCat')
        skeleton = controller.skeleton
        joints = list(skeleton.GetJointsAttr().Get())
        cache = UsdSkel.Cache()
        before = cache.GetSkelQuery(skeleton).ComputeJointSkelTransforms(Usd.TimeCode.Default())
        controller.turn(30, 8)
        cache.Clear()
        after = cache.GetSkelQuery(skeleton).ComputeJointSkelTransforms(Usd.TimeCode.Default())
        for i, joint in enumerate(joints):
            if 'head' in str(joint).split('/'):
                self.assertNotEqual(before[i], after[i], joint)
            else:
                self.assertEqual(before[i], after[i], joint)
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh) and (prim.GetName().startswith(('Fang_', 'Mouth_', 'viewer_')) or prim.GetName() == 'cat_head'):
                binding = UsdSkel.BindingAPI(prim)
                indices = binding.GetJointIndicesPrimvar().Get()
                self.assertTrue(indices, str(prim.GetPath()))
                self.assertTrue(all('head' in str(joints[i]).split('/') for i in indices))
                self.assertTrue(all(abs(w - 1.) < 1e-6 for w in binding.GetJointWeightsPrimvar().Get()))

    def test_existing_output_and_invalid_profile_leave_source_unchanged(self):
        module = self.module()
        with self.assertRaises(ValueError):
            module.build_personality(self.asset, {'schema_version': 1, 'adapter': 'unknown'}, self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
        with self.assertRaises(ValueError):
            module.build_personality(self.asset, {'schema_version': 1, 'adapter': 'flyingcat-v1'}, self.asset)

    def test_tampered_source_and_escaping_usd_are_rejected(self):
        module = self.module()
        (self.asset/'asset.usda').write_text('#usda 1.0\n( subLayers = [@https://example.invalid/a.usda@] )\n')
        with self.assertRaises(ValueError):
            module.build_personality(self.asset, {'schema_version': 1, 'adapter': 'flyingcat-v1'}, self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_runtime_rejects_other_animation_owner(self):
        out, _ = self.build()
        from personality import PersonalityController
        stage = Usd.Stage.Open(str(out/'personality.usda'))
        skel = stage.GetPrimAtPath('/FlyingCat/CatRig/CatSkeleton')
        UsdSkel.BindingAPI.Apply(skel).CreateAnimationSourceRel().SetTargets(['/FlyingCat/OtherMotion'])
        with self.assertRaises(ValueError):
            PersonalityController(stage, '/FlyingCat')

    def test_rehashed_foreign_composition_is_rejected_before_stage_open(self):
        module = self.module()
        wrapper = self.asset/'asset.usda'
        wrapper.write_text('#usda 1.0\n( subLayers = [@https://example.invalid/a.usda@] )\n')
        manifest = json.loads((self.asset/'manifest.json').read_text())
        for item in manifest['files']:
            if item['path'] == 'asset.usda':
                item['sha256'] = digest(wrapper)
        (self.asset/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'wrapper differs'):
            module.build_personality(self.asset, {'schema_version': 1, 'adapter': 'flyingcat-v1'}, self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_invalid_pose_and_joint_hierarchy_rejected(self):
        self.module()
        from personality import PersonalityState, compose_pose
        stage = Usd.Stage.Open(str(self.asset/'asset.usda'))
        skel = UsdSkel.Skeleton.Get(stage, '/FlyingCat/CatRig/CatSkeleton')
        joints = list(skel.GetJointsAttr().Get())
        t, r, s = UsdSkel.DecomposeTransforms(skel.GetRestTransformsAttr().Get())
        with self.assertRaises(ValueError):
            compose_pose(joints, t[:-1], r, s, PersonalityState())
        s[0] = Gf.Vec3h(0)
        with self.assertRaises(ValueError):
            compose_pose(joints, t, r, s, PersonalityState())
        joints[-1] = 'pelvis/face_mouth'
        with self.assertRaises(ValueError):
            compose_pose(joints, t, r, s, PersonalityState())

    def test_symlink_input_and_output_rejected(self):
        module = self.module()
        profile = {'schema_version': 1, 'adapter': 'flyingcat-v1'}
        (self.root/'output-link').symlink_to(self.root/'nonexistent')
        with self.assertRaises(ValueError):
            module.build_personality(self.asset, profile, self.root/'output-link')
        source = self.asset/'sources/flyingcat-v1.usdc'
        outside = self.root/'outside.usdc'
        source.rename(outside)
        source.symlink_to(outside)
        with self.assertRaises(ValueError):
            module.build_personality(self.asset, profile, self.root/'bad')

    def test_missing_dependency_reports_json_and_no_partial_output(self):
        self.module()
        request = self.root/'profile.json'
        request.write_text('{"schema_version":1,"adapter":"flyingcat-v1"}')
        script = SKILL/'scripts/personality_builder.py'
        launcher = 'import runpy,sys; sys.path.insert(0,sys.argv[1]); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name="__main__")'
        result = subprocess.run([sys.executable, '-I', '-S', '-c', launcher, str(script.parent), str(script),
                                 'build', '--asset', str(self.asset), '--profile', str(request),
                                 '--output', str(self.root/'missing')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'missing_dependency')
        self.assertFalse((self.root/'missing').exists())

    def test_cli_capabilities_and_bad_json_without_usd(self):
        self.module()
        script = SKILL / 'scripts/personality_builder.py'
        result = subprocess.run([sys.executable, '-S', str(script), 'capabilities'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['expressions'], ['natural', 'curious', 'angry'])
        request = self.root/'request.json'
        request.write_text('{"schema_version":1,"schema_version":1,"adapter":"flyingcat-v1"}')
        result = subprocess.run([sys.executable, str(script), 'build', '--asset', str(self.asset),
                                 '--profile', str(request), '--output', str(self.root/'invalid')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse((self.root/'invalid').exists())


if __name__ == '__main__':
    unittest.main()
