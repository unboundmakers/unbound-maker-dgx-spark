import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, UsdSkel, UsdUtils

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from asset_builder import build_asset, BuildError

BASE = {"schema_version": 1, "template_id": "flyingcat-v1"}
BODY = "/FlyingCat/_materials/gold/Principled_BSDF"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UsdBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "result"

    def build(self, **changes):
        try:
            return build_asset(dict(BASE, **changes), self.output)
        except BuildError as exc:
            self.fail("Expected a real USD build, got " + exc.code + ": " + str(exc))

    def test_build_preserves_meshes_skeleton_bindings_and_no_physics(self):
        result = self.build()
        self.assertEqual(result["status"], "succeeded")
        self.assertFalse(result["physics_ready"])
        self.assertEqual(result["entrypoint"], "asset.usda")
        stage = Usd.Stage.Open(str(self.output / result["entrypoint"]))
        self.assertEqual(str(stage.GetDefaultPrim().GetPath()), "/FlyingCat")
        self.assertEqual(UsdGeom.GetStageUpAxis(stage), "Z")
        self.assertEqual(UsdGeom.GetStageMetersPerUnit(stage), 1.0)
        meshes = [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
        self.assertEqual(len(meshes), 77)
        skeleton = UsdSkel.Skeleton.Get(stage, "/FlyingCat/CatRig/CatSkeleton")
        self.assertEqual(len(skeleton.GetJointsAttr().Get()), 14)
        for prim in meshes:
            targets = UsdSkel.BindingAPI(prim).GetSkeletonRel().GetTargets()
            self.assertEqual([str(t) for t in targets], ["/FlyingCat/CatRig/CatSkeleton"])
            self.assertTrue(UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0])
        self.assertFalse(any(p.HasAPI(UsdPhysics.RigidBodyAPI) or
                             p.HasAPI(UsdPhysics.CollisionAPI) for p in stage.Traverse()))
        report = json.loads((self.output / "validation.json").read_text())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["checks"]["mesh_count"], 77)
        self.assertFalse(report["isaac_sim_tested"])

    def test_color_is_linear_rgb_and_other_materials_unchanged(self):
        self.build(body_color="#8080FF")
        stage = Usd.Stage.Open(str(self.output / "asset.usda"))
        color = UsdShade.Shader.Get(stage, BODY).GetInput("diffuseColor").Get()
        self.assertAlmostEqual(color[0], 0.2158605, places=6)
        self.assertAlmostEqual(color[1], 0.2158605, places=6)
        self.assertAlmostEqual(color[2], 1.0, places=6)
        wing = UsdShade.Shader.Get(stage, "/FlyingCat/_materials/pink/Principled_BSDF")
        self.assertAlmostEqual(wing.GetInput("diffuseColor").Get()[0], 0.96, places=6)
        eyes = UsdShade.Shader.Get(stage, "/FlyingCat/_materials/Expression___blue_eyes/Principled_BSDF")
        self.assertAlmostEqual(eyes.GetInput("diffuseColor").Get()[2], 0.7, places=6)

    def test_default_color_preserves_template(self):
        self.build()
        stage = Usd.Stage.Open(str(self.output / "asset.usda"))
        color = UsdShade.Shader.Get(stage, BODY).GetInput("diffuseColor").Get()
        self.assertAlmostEqual(color[1], 0.66, places=6)

    def test_scale_changes_world_bounds(self):
        self.output = self.root / "one"
        self.build()
        self.output = self.root / "result"
        self.build(scale=1.5)
        first = Usd.Stage.Open(str(self.root / "one/asset.usda"))
        second = Usd.Stage.Open(str(self.output / "asset.usda"))
        cache = UsdGeom.BBoxCache(0, ["default", "render"])
        one = cache.ComputeWorldBound(first.GetDefaultPrim()).ComputeAlignedRange().GetSize()
        two = cache.ComputeWorldBound(second.GetDefaultPrim()).ComputeAlignedRange().GetSize()
        for axis in range(3):
            self.assertAlmostEqual(two[axis] / one[axis], 1.5, places=5)

    def test_package_relocates_and_manifest_hashes_match(self):
        result = self.build(body_color="#2867D7")
        moved = self.root / "elsewhere"
        shutil.move(str(self.output), moved)
        stage = Usd.Stage.Open(str(moved / "asset.usda"))
        self.assertTrue(stage.GetPrimAtPath("/FlyingCat/CatRig/cat_head"))
        layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(moved / "asset.usda"))
        self.assertEqual(unresolved, [])
        self.assertEqual(assets, [])
        for layer in layers:
            self.assertTrue(Path(layer.realPath).resolve().is_relative_to(moved.resolve()))
        for item in result["files"]:
            self.assertEqual(digest(moved / item["path"]), item["sha256"])
        text = (moved / "asset.usda").read_text()
        self.assertNotIn(str(SKILL), text)
        self.assertNotIn(str(self.root), text)

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "do-not-touch"
        sentinel.write_text("existing work")
        with self.assertRaises(BuildError) as caught:
            build_asset(BASE, self.output)
        self.assertEqual(caught.exception.code, "output_exists")
        self.assertEqual(sentinel.read_text(), "existing work")

    def test_symlink_output_rejected(self):
        target = self.root / "target"
        self.output.symlink_to(target, target_is_directory=True)
        with self.assertRaises(BuildError) as caught:
            build_asset(BASE, self.output)
        self.assertEqual(caught.exception.code, "output_exists")
        self.assertFalse(target.exists())

    def test_source_is_unchanged(self):
        source = SKILL / "assets/flyingcat-v1.usdc"
        before = digest(source)
        self.build(body_color="#FF0000", scale=2)
        self.assertEqual(digest(source), before)
        self.assertEqual(digest(self.output / "sources/flyingcat-v1.usdc"), before)

    def test_altered_or_missing_template_is_rejected(self):
        clone = self.root / "skill"
        shutil.copytree(SKILL, clone, ignore=shutil.ignore_patterns("__pycache__"))
        source = clone / "assets/flyingcat-v1.usdc"
        request = self.root / "request.json"
        request.write_text(json.dumps(BASE))
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    source.unlink()
                else:
                    source.write_bytes(source.read_bytes() + b"tampered")
                result = subprocess.run([sys.executable, str(clone / "scripts/asset_builder.py"),
                    "build", "--request", str(request), "--output", str(self.output)],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["error"]["code"], "invalid_template")
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
