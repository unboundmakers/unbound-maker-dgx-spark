# Validated Meadow Case

Historical evidence, reviewed 2026-09-27. Do not assume paths, host addresses or engine limitations still apply. This reference is optional outside the meadow/Spark workflow; the general skill does not depend on these files.

## Source and Runtime

- Local scene project: `unbound-maker-scene-builder/meadow-v1` in the developer's workspace (not bundled).
- Remote project at the time: `/home/spark/unbound-maker-meadow-v1`
- Target: DGX Spark GB10, aarch64, Isaac Sim 5.1, Kit 107.3.3.
- Actual scene: `scene.usda`, `assets/library.usdc`, `layers/landscape.usda`, `layers/distant.usda`.
- Reusable implementation examples: `build_scene.py`, `layout.py`, `meadow_scene.py`, `view_settings.py`.
- Regression examples: `test_layout.py`, `test_stage.py`, `test_rock_contacts.py`, `run_flight.py`.

Inspect these scripts before reusing them. They contain scene-specific geometry and runtime assumptions; do not copy them as a universal optimizer or package third-party assets inside the skill.

## Working Choices

| Area | Actual implementation |
| --- | --- |
| Footprint | Nine 16 m tiles, 48 x 48 m total; periodic surface maintains seams |
| Terrain visuals | One shared terrain prototype, nine native instances |
| Vegetation | Two NVIDIA grass meshes; PointInstancer; three material variations |
| Grass LOD | Per tile near 1600/far 200; runtime check every 0.5 s, 21/27 m hysteresis |
| Rocks | Three generated prototypes, 15 PointInstancer placements |
| Trees | Two generated prototypes, eight placements, no collision |
| PBR | Generated 1K terrain/rock textures; user-provided 2K EXR |
| Distant view | Simplified geometry in a separate payload; no automatic unloading |
| Runtime | 30 FPS cap, physics timestep 1/120 s; independent follow camera |

## Physics Fallbacks, Not Universal Defaults

Non-flat triangle terrain and tilted collision proxies failed dynamic contact tests in this runtime, while flat controls worked. Root cause remains unresolved. Check `diagnose_contacts.py` and `outputs/contact-matrix.json` rather than claiming all Isaac Sim terrains are broken.

The working fallback uses nine PointInstancers of 1024 static horizontal Cube shapes each: **9216 physics shapes**, 0.5 m sampling, 2 m depth. Shared USD prototypes reduce authored scenegraph repetition, not the number of physics shapes. The visual/contact height difference is bounded at roughly 0.113 m for this particular surface. This is acceptable for the tested flying/sliding demo, not a default surface for precision gait learning. Prefer a validated simpler terrain collider in new environments.

Rock prototypes each contain one invisible static Cube proxy. Adding nested native instancing to the PointInstancer physics prototypes caused ghost contact near the origin in this setup. Setting the three rock prototype roots `instanceable=False` retained PointInstancer sharing and passed contact tests. Reproduce before applying the same workaround elsewhere.

`rock_support.py` estimates support height only to select visual pose; it does not move the physics body. Trees, grass and distant mountains have no collision by design.

## Evidence and Limits

- Recorded structure/layout result: seven tests passed.
- `outputs/rock-contacts.json`: 15 drop and 15 lateral-block checks passed, with rock placements separated in an anonymous test layer. This isolates individual proxies; it does not by itself prove combined scene behavior.
- `outputs/physics-test.json`: 18 full-flight regression checks passed. Read current report and test mode; scripted input is not proof of manual keyboard interaction.
- Actual renderer images: `outputs/meadow-wide.png`, `outputs/meadow-close.png`, `outputs/test-flight.png`.
- No controlled before/after GPU-memory benchmark was performed. The compact asset package is not evidence of a particular VRAM reduction.
- NVIDIA grass remains third-party derivative geometry after recoloring. The EXR source/license must be confirmed; do not infer provenance from its filename. Preserve attribution and verify distribution rights separately.

## Runtime Cautions

The standalone USD authoring environment used explicit USD library paths. Do not carry those `PYTHONPATH`/`LD_LIBRARY_PATH` overrides into SimulationApp tests without validating compatibility.

Kit shutdown can hide a Python failure behind an exit code of zero. Require a newly generated report with successful checks and inspect logs. Old reports are historical evidence, not validation of a newly modified scene.
