# Asset Builder 0.1.0 Contract

## Request

| Field | Required | Meaning |
| --- | --- | --- |
| schema_version | yes | Integer 1, not a boolean |
| template_id | yes | flyingcat-v1 |
| body_color | no | #RRGGBB in sRGB; converted to linear RGB for UsdPreviewSurface. Omitted means original color |
| scale | no | Finite number, 0.5 through 2.0 inclusive; default 1.0; uniform, dimensionless |

Unknown fields, duplicate JSON keys, booleans as numbers, NaN and infinity are rejected. Source paths, shell commands and mass fields are not supported. Operator-supplied CLI paths are separate from model-generated request fields.

## Output and composition

`asset.usda` uses meters, Z up and default prim `/FlyingCat`. A relative reference includes `sources/flyingcat-v1.usdc`. The original 77 meshes and 14 skeleton joints remain intact; the gold shader override and uniform root scale are authored in the new layer. Other colors and character transforms are preserved.

The source template is pinned by SHA256. Current source has no external textures or layers; any such new dependency requires an explicit template update and packaging support, not silently dropping files. Never flatten the full scene to manufacture portability.

Copy the complete folder. Output files:

- asset.usda: reference this from a scene, not the bundled raw template.
- sources/flyingcat-v1.usdc: exact source copy; reusable by downstream asset management.
- request.json: normalized input.
- provenance.json: source, hash and release restrictions.
- validation.json: structural USD results; explicitly not an Isaac physics/render test.
- manifest.json: final success marker, relative entrypoint, hashes of the other files and limitations. The manifest does not hash itself and is not signed.

One build copies approximately 2.3 MB of source geometry for portability. Within scenes, reuse the built asset via references/instances rather than duplicating it per character. This Skill does not measure GPU memory or claim a rendering optimization.

The parent Agent must assign a private job directory and wait for process exit before consuming results. A failure after output creation can leave an incomplete directory but never a success manifest. Preserve it for diagnosis and use a new directory on retry; there is no automatic destructive cleanup or overwrite.

## Errors

Successful commands return JSON on stdout and exit 0. Build errors return `status: failed`, `error.code`, `error.message`, and exit 2. Native USD warnings may go to stderr even on success. CLI syntax/help uses standard argparse behavior.

| Code | Meaning |
| --- | --- |
| invalid_request | Invalid JSON, unsupported field/template or out-of-range parameter |
| output_exists | Existing path, including symlink; select a new job directory |
| invalid_output | Parent directory missing |
| missing_dependency | This Python cannot import pxr |
| invalid_template | Missing/altered template, manifest or failed source structure check |
| validation_failed | Generated USD fails structural checks |
| io_error | Filesystem access failure |
| build_failed | Other build/runtime error; do not report a successful asset |

This implementation has no network calls and no subprocess execution. The caller is responsible for a trusted installed Skill directory and an approved output root; it is a local CLI, not an authenticated multi-user API.

The character has no authored rigid body, collision, mass or articulation. Its skeleton is for visual deformation, not physical robot joints. Scene/physics setup and controller attachment occur downstream.

Reference: [OpenUSD utilities and dependency analysis](https://openusd.org/release/api/usd_utils_page_front.html).

