---
name: unbound-maker-scene-optimizer
description: Use when auditing or optimizing Unbound Maker OpenUSD scene packages for Isaac Sim, including existing instancers, payloads, visual LOD and collision preservation. Produces a separate scene and evidence report, not robot training or a running simulation.
---

# Unbound Maker Scene Optimizer

Use the bundled CLI for trusted **Scene Builder 0.1.0** packages. For other USD
scenes, use the decision guide in [optimization recipes](references/optimization-recipes.md)
and establish a separate adapter first; do not relabel arbitrary USD as supported.

## Execute

If asked to make a scene cheaper while preserving its approved appearance and
contacts, propose the `preserve` audit first. Say explicitly that this profile
does not lower visual detail and that GPU savings have not been measured.
Offer `preview` only as an explicit quality tradeoff. Do not simply refuse a
supported audit because you cannot promise a performance improvement.

```sh
python scripts/scene_optimizer.py capabilities
python scripts/scene_optimizer.py optimize \
  --input /absolute/path/to/scene-builder-output \
  --request examples/preserve.json \
  --output /absolute/path/to/new-optimized-output
```

Use an existing Python with OpenUSD. The output parent must exist; the output
directory must be new and outside the source. No network, renderer or Blender is
required. Treat input USD and its manifest as trusted local content, not a sandbox
for hostile assets. Hash checks establish integrity, not authorship or signatures.

- **preserve**, default: inspect dependencies, instancers, bindings and protected
  state; retain the approved look. Explicitly report that no visual optimization ran.
- **preview**, when lower distant detail is acceptable: select existing `far`
  variants beyond the fixed preview-camera thresholds. Never upgrade an existing
  far/distant choice. Moon close-up geometry is left untouched.

Read [integration and limits](references/integration.md) before connecting an
Agent or Runner. This is **static** LOD, not camera-following LOD or streaming.
Moving toward a reduced-detail object needs a Runner to select `near` again.

## Preserve

Retain original files under `base/`; write only a stronger `optimized.usda` layer.
Do not flatten, rebuild scatter, make collision prototypes instanceable, change
UV tiling, rescale the scene or replace the editor camera. Keep collider geometry,
physics-instancer arrays, character, gravity, lights and cameras invariant.
The CLI checks these composed properties before accepting its output.

Prior contact pitfalls and approximation limits are in
[the meadow case](references/meadow-case.md); its historical dimensions are not
the current scene's dimensions. Inspect the actual input. Shared prototypes do
not reduce the number of simulated contact shapes by themselves.

## Verify and Report

Require CLI success **and** a fresh `manifest.json` and `optimization-report.json`.
Report changes and structural counts with their actual meaning. Disk bytes,
PointInstancer placement counts and mesh points are not GPU-memory measurements.
No-op results are valid, particularly for the already-optimized meadow or moon.

CPU validation is not Isaac rendering/contact validation. Follow
[runtime verification](references/validation.md) for subsequent bounded GPU tests;
inspect running work first and preserve unrelated processes. Do not claim actual
FPS gains, CUDA optimization, NVIDIA Usd Optimize execution or formal certification
from this CLI. Agent pressure cases in `evals/evals.json` are not completed A/B tests.

Deliver the full output folder, its entrypoint, profile, report and unmeasured
items. Do not publish bundled assets until their individual redistribution rights
and upload authorization have been reviewed. This Skill zip contains no scene assets.
