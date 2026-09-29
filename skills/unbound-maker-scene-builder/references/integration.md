# Scene Builder Contract 0.1.0

## Inputs

Request: `schema_version: 1`, `scene_id: meadow|space|moon`, optional matching `mode`, `spawn_id: start`, `heading_degrees: -180..180`. Unknown fields and duplicate JSON keys are errors. Defaults: heading 0, start, mode inferred from the scene. Invalid mode is never silently corrected.

`--assets`: approved local template root. Catalog uses relative paths, byte counts and SHA256. All selected files must match before output is created. The catalog was snapshotted from the working meadow-v0.3 tree, including both near/far textures. It excludes downloaded originals, Blender backups, screenshots and unrelated scenes.

`--character`: trusted local Asset Builder or Personality Builder 0.1.0 output. File inventory hashes are checked; relative paths cannot escape the package. Source manifests and runtime/config files remain in the copied character directory. Python files are never executed by this builder. This integrity check is not a signature or sandbox against hostile USD files.

`--output`: new directory; parent exists. CLI writes JSON on stdout and errors use exit 2. Build is CPU-only and needs compatible `pxr`; capabilities does not.

## Output / Runner Handoff

`scene.usda`, `scene-config.json`, `manifest.json`, `validation.json`, `sources.json`, `environment/`, `character/`.

- `/World/Environment`: selected environment payload; grass retains its original nested World children.
- `/World/Character`: actor placement transform, intentionally no dynamic physics.
- `/World/Character/Pose/Visual`: referenced character root; pose offset aligns original lower bounds just above the spawn support plane without removing asset scale.
- `/World/Physics`: gravity direction down Z; magnitude meadow 9.81, space 0, moon 1.62 m/s².
- `/World/PreviewCamera`: optional camera, never automatically selected.
- Moon only: `/World/Astronaut`, `/World/AstronautContact`, `/World/LunarVehicles`.

`scene-config.json` carries exact spawn, character prim paths, runtime defaults and renderer preferences. A future runner must apply/restore renderer settings deliberately, attach physics/control to the character, bind inputs and integrate Personality Builder in one skeleton writer. Simply opening the USD displays a static assembled scene. Do not launch old run_flight.py against this output and assume its old hardcoded paths match.

The Moon astronaut remains 2.5 times the character's bound height and uses the established (4,6) camp location, relative to terrain. Existing static rover/lander placement and collision proxies are preserved; those props are not driveable robots.

## Optimization Boundary

Authored environment files are copied byte-for-byte, preserving references, payloads, detail variants, PointInstancer geometry and collision proxies. Scene Builder does not retessellate, rebake textures, train policies or guarantee lower GPU memory. Each output owns a selected dependency copy for portability. Future shared storage/hardlink/cache deduplication is separate; no cross-job mutable assets are introduced now.

Current catalog authoring uses snapshot_catalog.py only against our trusted source tree, which includes the inspected moon_rules helper. It is not a general third-party asset importer. Catalog mismatch means stop and inspect, not refresh hashes automatically.

## Known Consumer Requirements

Astronaut material networks retain `OmniPBR.mdl` and `OmniGlass.mdl`. These are explicit Isaac/Kit runtime shader dependencies, not bundled files. CPU checks allow exactly those module names for the Moon; all other unresolved references are errors. Shader availability on a machine must be checked separately, and a file on disk alone does not prove the target renderer compiles it.

All native texture and USD file paths must resolve inside the generated package. CPU validation checks units, root, character skeleton, mesh material bindings and dependency closure. It does not test actual PhysX contact, GPU appearance, dynamic LOD, follow-camera behavior or controls.

## Provenance / Publication

The selected catalog includes project source notes, NASA provenance, NVIDIA astronaut/gravel notes and camp attribution. Meadow EXR is the user-provided Poly Haven meadow file; grass meshes come from NVIDIA examples. Keep required credits and asset terms. Local use and a small source-code Skill archive do not authorize public redistribution of the assembled environment binaries.
