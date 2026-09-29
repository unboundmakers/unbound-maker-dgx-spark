"""Build a pinned visual character asset; never launch a simulator or shell."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"


class BuildError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def validate_request(value):
    if not isinstance(value, dict):
        raise BuildError("invalid_request", "Request must be a JSON object.")
    unknown = set(value) - {"schema_version", "template_id", "body_color", "scale"}
    if unknown:
        raise BuildError("invalid_request", "Unsupported fields: " + ", ".join(sorted(unknown)))
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise BuildError("invalid_request", "schema_version must be integer 1.")
    if value.get("template_id") != "flyingcat-v1":
        raise BuildError("invalid_request", "Only template_id=flyingcat-v1 is supported.")
    scale = value.get("scale", 1.0)
    if type(scale) not in (int, float) or not 0.5 <= scale <= 2.0:
        raise BuildError("invalid_request", "scale must be finite and within 0.5..2.0.")
    result = {"schema_version": 1, "template_id": "flyingcat-v1", "scale": float(scale)}
    if "body_color" in value:
        color = value["body_color"]
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise BuildError("invalid_request", "body_color must use #RRGGBB sRGB notation.")
        result["body_color"] = color.upper()
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BuildError("invalid_request", "Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_request(path):
    try:
        return validate_request(json.loads(Path(path).read_text(encoding="utf-8"),
                                           object_pairs_hook=unique_object))
    except (ValueError, UnicodeError) as exc:
        raise BuildError("invalid_request", "Cannot parse request JSON.") from exc


def build_asset(request, output):
    request = validate_request(request)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise BuildError("output_exists", "Choose a new output directory; existing paths are never overwritten.")
    if not output.parent.is_dir():
        raise BuildError("invalid_output", "The output parent directory must already exist.")
    try:
        from pxr import Gf, Usd, UsdGeom, UsdShade
    except ImportError as exc:
        raise BuildError("missing_dependency", "Run with a Python environment providing pxr OpenUSD.") from exc
    source, template = load_template()
    try:
        source_stage = Usd.Stage.Open(str(source))
        if not source_stage:
            raise BuildError("invalid_template", "Cannot open template.")
        validate_stage(source_stage, source, template, "/CatVisual", source.parent)
    except BuildError as exc:
        raise BuildError("invalid_template", str(exc)) from exc

    # Exclusive creation reserves this job's directory; never remove caller data.
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise BuildError("output_exists", "Another build already created this output.") from exc
    sources = output / "sources"
    sources.mkdir()
    copied = sources / "flyingcat-v1.usdc"
    shutil.copyfile(source, copied)
    if file_hash(copied) != template["sha256"]:
        raise BuildError("invalid_template", "Template changed while copying; discard this incomplete build.")
    entrypoint = output / "asset.usda"
    stage = Usd.Stage.CreateNew(str(entrypoint))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/FlyingCat")
    root.GetPrim().GetReferences().AddReference("./sources/flyingcat-v1.usdc", "/CatVisual")
    root.AddScaleOp(opSuffix="assetScale").Set(Gf.Vec3f(request["scale"]))
    stage.SetDefaultPrim(root.GetPrim())
    if "body_color" in request:
        shader = UsdShade.Shader.Get(stage, "/FlyingCat/" + template["body_material"])
        shader.GetInput("diffuseColor").Set(Gf.Vec3f(*linear_color(request["body_color"])))
    stage.GetRootLayer().Save()
    reopened = Usd.Stage.Open(str(entrypoint))
    checks = validate_stage(reopened, entrypoint, template, "/FlyingCat", output)
    validation = {"status": "passed", "scope": "OpenUSD structural checks only",
                  "isaac_sim_tested": False, "checks": checks}
    write_json(output / "validation.json", validation)
    write_json(output / "request.json", request)
    write_json(output / "provenance.json", template)
    manifest = {
        "schema_version": 1, "status": "succeeded", "skill": "unbound-maker-asset-builder",
        "skill_version": VERSION, "usd_version": ".".join(map(str, Usd.GetVersion())),
        "request": request, "entrypoint": "asset.usda", "default_prim": "/FlyingCat",
        "asset_kind": "skinned_visual", "physics_ready": False,
        "source_sha256": template["sha256"], "validation": "validation.json",
        "limitations": ["No rigid body, collider, mass, articulation or URDF is authored.",
                        "No scene, gait controller or expression controller is started.",
                        "Only the primary gold body material is recolored; accents are preserved.",
                        "Public redistribution licensing awaits owner confirmation."],
        "files": [{"path": str(path.relative_to(output)), "sha256": file_hash(path),
                   "bytes": path.stat().st_size}
                  for path in sorted(output.rglob("*")) if path.is_file()],
    }
    # This is the completion marker. Incomplete builds never get a success manifest.
    write_json(output / "manifest.json", manifest)
    return manifest


def file_hash(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                          encoding="utf-8")


def load_template():
    source = SKILL_ROOT / "assets/flyingcat-v1.usdc"
    try:
        template = json.loads((SKILL_ROOT / "assets/template.json").read_text(encoding="utf-8"))
        if file_hash(source) != template["sha256"]:
            raise BuildError("invalid_template", "Template hash mismatch.")
    except (OSError, ValueError, KeyError) as exc:
        raise BuildError("invalid_template", "Template or its manifest is missing or invalid.") from exc
    return source, template


def linear_color(hex_color):
    values = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]


def validate_stage(stage, entrypoint, template, root_path, package):
    from pxr import UsdGeom, UsdPhysics, UsdShade, UsdSkel, UsdUtils
    if not stage or str(stage.GetDefaultPrim().GetPath()) != root_path:
        raise BuildError("validation_failed", "Missing expected default prim.")
    if UsdGeom.GetStageUpAxis(stage) != "Z" or UsdGeom.GetStageMetersPerUnit(stage) != 1.0:
        raise BuildError("validation_failed", "Expected Z up and meter units.")
    meshes = [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
    skeleton = UsdSkel.Skeleton.Get(stage, root_path + "/CatRig/CatSkeleton")
    if len(meshes) != template["mesh_count"] or not skeleton:
        raise BuildError("validation_failed", "Template meshes or skeleton are missing.")
    joints = skeleton.GetJointsAttr().Get()
    if len(joints or []) != template["joint_count"]:
        raise BuildError("validation_failed", "Unexpected skeleton joint count.")
    for mesh in meshes:
        targets = UsdSkel.BindingAPI(mesh).GetSkeletonRel().GetTargets()
        if targets != [skeleton.GetPath()]:
            raise BuildError("validation_failed", "Broken skeleton binding: " + str(mesh.GetPath()))
        material = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial()[0]
        if not material:
            raise BuildError("validation_failed", "Unbound material: " + str(mesh.GetPath()))
    if any(prim.HasAPI(UsdPhysics.RigidBodyAPI) or prim.HasAPI(UsdPhysics.CollisionAPI)
           for prim in stage.Traverse()):
        raise BuildError("validation_failed", "This template must remain visual-only.")
    shader = UsdShade.Shader.Get(stage, root_path + "/" + template["body_material"])
    if not shader or shader.GetInput("diffuseColor").Get() is None:
        raise BuildError("validation_failed", "Primary body shader is missing.")
    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(entrypoint))
    if unresolved or assets:
        raise BuildError("validation_failed", "Template requires external assets; this version supports self-contained USD only.")
    for layer in layers:
        if not Path(layer.realPath).resolve().is_relative_to(package.resolve()):
            raise BuildError("validation_failed", "A USD dependency escapes the asset package.")
    bounds = UsdGeom.BBoxCache(0, ["default", "render"]).ComputeWorldBound(
        stage.GetDefaultPrim()).ComputeAlignedRange()
    if bounds.IsEmpty() or not all(math.isfinite(v) and v > 0 for v in bounds.GetSize()):
        raise BuildError("validation_failed", "Invalid world-space bounds.")
    return {"mesh_count": len(meshes), "joint_count": len(joints),
            "material_bindings": "passed", "skeleton_bindings": "passed",
            "dependency_count": len(layers), "unresolved_dependencies": [],
            "bounds_min": list(bounds.GetMin()), "bounds_max": list(bounds.GetMax())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    build = sub.add_parser("build")
    build.add_argument("--request", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capabilities":
            result = {"skill": "unbound-maker-asset-builder", "version": VERSION,
                      "templates": ["flyingcat-v1"], "scale_range": [0.5, 2.0],
                      "body_color": "optional #RRGGBB sRGB; omitted preserves template",
                      "physics_ready": False, "asset_kind": "skinned_visual"}
        else:
            result = build_asset(read_request(args.request), args.output)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except BuildError as exc:
        print(json.dumps({"status": "failed", "error": {"code": exc.code, "message": str(exc)}}))
        return 2
    except OSError as exc:
        print(json.dumps({"status": "failed", "error": {"code": "io_error", "message": str(exc)}}))
        return 2
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": {"code": "build_failed", "message": str(exc)}}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
