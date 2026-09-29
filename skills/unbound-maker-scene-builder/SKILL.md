---
name: unbound-maker-scene-builder
description: Assemble Unbound Maker meadow, solar-space or lunar scene templates with an existing Asset Builder or Personality Builder character. Use for choosing a supported environment and packaging a local OpenUSD scene; not arbitrary text-to-world generation, physics training or simulator launch.
---

# Unbound Maker Scene Builder

Build an independently relocatable scene from inspected local templates. Preserve the approved environment and character rather than regenerating either. Large meshes/textures are separate from this small Skill package.

## Supported Scope

| Scene ID | Mode | Environment |
| --- | --- | --- |
| meadow | story | Grass, gravel, rocks, trees, daytime EXR |
| space | story | Compressed planetary playground with NASA-derived textures |
| moon | experiment | Detailed lunar terrain, astronaut, static rover and lander |

Use these exact IDs: the solar-system preset is `space`, never `solar`.
Existing compatible flying-cat packages can be placed in `meadow` without changing
their expression. This is a supported task; missing tools mean describe the plan
without claiming execution, not reject the task as unsupported.

Use `scripts/scene_builder.py capabilities` to inspect fields. Version 0.1.0 exposes the inspected `start` spawn and heading only. No arbitrary coordinates, geometry dimensions or physics tuning. Moon config retains the 10-second experiment default. Creating this config does not run the experiment.

## Assemble

1. Get the local asset root containing the catalog-pinned files, and a successful Asset/Personality Builder 0.1.0 output. Do not download paid assets or substitute missing ones silently. Only use trusted local character packages; native USD parsing is not a security sandbox.
2. Prepare the small request JSON using an example. Keep `scene_id` and `mode` compatible; unsupported values reject rather than being ignored.
3. Run the CLI with an existing compatible OpenUSD Python:

```sh
python scripts/scene_builder.py build \
  --request examples/moon.json \
  --assets /absolute/path/to/template-root \
  --character /absolute/path/to/character-output \
  --output /absolute/path/to/new-scene-output
```

Paths above are examples; use this Skill as working directory or expand script/example paths. Output parent must exist and output must not exist. No source is overwritten. A failed partial directory is diagnostic, not a finished scene; retry into a new directory.

Do not pre-create the output folder, even empty. The builder creates it; only its
parent directory must already exist.

4. Check the returned JSON and `manifest.json`. Preserve the whole output directory. `scene.usda` alone is insufficient. Read [integration contract](references/integration.md) before handing off to the Agent, optimizer or simulation runner.

## Preserve and Disclose

- Keep existing payloads, instanced geometry, PointInstancer scatter, detail variants, PBR maps and collision proxies. Do not flatten just to simplify copying.
- Dynamic distance-based LOD switching and planet animation require the separate Simulation Runner; USD variants alone do not animate or switch themselves.
- The new PreviewCamera is optional. Do not force viewport selection or edit the user's Perspective camera.
- Terrain and prop collisions are retained. Character is still a skinned visual, not a rigid body, articulation or trained robot. Gravity is authored but no simulation is executed.
- The solar environment uses compressed fictional sizes/distances. Moon relief is an illustrative scene, and pink-blue glow is decorative, not a real lunar atmosphere.
- NVIDIA astronaut depends on Isaac's OmniPBR/OmniGlass modules. A CPU USD environment may warn about these two names; report them as runtime requirements, not missing textures or proven shader compilation.
- Preserve source records. Free access does not establish redistribution permission. This Skill archive does not contain those third-party binary assets; local scene outputs need a separate release review before upload.

## Verification

Report separately: build complete, CPU structure checked, Isaac rendered, interaction/contact tested. Tests and Skill metadata checks are development evidence, not Agent evaluation or certification. Do not register an Agent, install global dependencies, start GPU work or publish as part of a scene build.

`scripts/snapshot_catalog.py` is maintainer-only tooling for an inspected local source tree. Never regenerate catalog hashes to bypass a failed integrity check; investigate version drift first.
