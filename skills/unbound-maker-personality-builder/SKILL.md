---
name: unbound-maker-personality-builder
description: Package manual head poses and natural, curious or angry expressions for Unbound Maker character assets. Use after Asset Builder when a character needs visual personality controls; not for gait training, emotion inference, scene creation or chatbot personas.
---

# Unbound Maker Personality Builder

Turn the creator's expression intent into supported visual controls. Current executable adapter: Asset Builder 0.1.0 `flyingcat-v1`. Other bodies require inspection and a separate adapter; never assume the same joint map works.

## Preserve the Character

- Curious and opinionated, relaxed by default. Natural is the default; fangs appear only for manually selected angry expression.
- Independent head yaw and slight tilt; eyes, mouth and teeth follow the head hierarchy.
- No inferred emotion, child profiling, automatic gaze, speech or autonomous behavior.
- Do not change gait, flight, mass, gravity, collision, camera or existing movement/reset keys.

## Build

When describing the plan, explicitly keep `natural` as the default and select
`angry` only through a manual control. The **parent** directory must exist; the
**output** directory must not exist. Do not reverse these two preconditions or
ask the user to pre-create the output folder.

Run `scripts/personality_builder.py capabilities` without OpenUSD to inspect supported controls. For a build, use an existing Python with `pxr`; do not install another USD version into Isaac Sim.

`capabilities` lists this adapter's static support; it does not inspect or certify
an arbitrary robot. For an uninspected rover, stop before build and require a
separate inspected adapter. Missing OpenUSD blocks build, not `capabilities`.
Never clean an existing output folder as a workaround; choose a new path.

```sh
python scripts/personality_builder.py build \
  --asset /absolute/path/to/asset-builder-output \
  --profile examples/flyingcat.json \
  --output /absolute/path/to/new-personality-output
```

Use this skill directory as the command working directory or expand script/profile paths. Output parent must exist; output must not. The builder validates the pinned source, hashes and restricted USD wrapper before composing a stage. It copies the input package, adds a natural-pose USD overlay, config, runtime and manifest. Source files remain untouched. No network, simulator launch or shell execution is performed by the builder.

`manifest.json` with `status=succeeded` is the completion marker. If a build fails after directory creation, keep it as an incomplete diagnostic artifact; retry with a new output directory, never overwrite it blindly. Copy the entire output folder, not just its USD entrypoint.

## Runtime Integration

Read [runtime contract](references/runtime-contract.md) before connecting a UI or a moving character. **One final writer owns the skeleton.** For a host with gait, compose the face onto the current unexpressed body pose in that writer. Do not create a second animation source to fight the gait controller. Standalone preview controller is for a rig without another active animation owner.

Expose natural/curious/angry plus head turn/tilt/center as manual callbacks. Bind buttons or keys in the host only after checking its existing controls. Opening `personality.usda` shows the default static pose; it does not execute Python or create buttons automatically.

## Report Accurately

Distinguish package built, CPU USD tested, live Isaac preview tested and real hardware tested. This package provides visual animation, not a physics-ready articulation or trained behavior. Unit tests and hashes do not amount to NVIDIA verification, Agent A/B evaluation or a digital signature. See `skill-card.md` and `BENCHMARK.md` for current evidence boundaries.
