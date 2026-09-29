---
name: unbound-maker-simulation-runner
description: Use when preparing, launching, stopping or testing bounded Isaac Sim previews of Unbound Maker Scene Builder or Scene Optimizer packages, including flight controls, manual expressions and visual LOD. Not robot policy training or public streaming.
---

# Unbound Maker Simulation Runner

Run the existing flying-cat playground through a bounded, single-use job. Read
[runtime contract](references/runtime-contract.md) before connecting an Agent.
This is an executable Skill, not a resident Agent or a trained robot controller.

## Workflow

1. Inspect the trusted input package and requested scene. Run `capabilities`.
2. Prepare a **new** job directory. It contains its own scene, request and fixed
   runtime. Source packages and the original playable prototype are not modified.
3. Before GPU launch, check the installed Isaac version, other running work and
   GPU temperature/utilization. Do not kill other previews, upgrade the environment,
   start overlapping GPU jobs or leave a window running by default.
   If another job is running, wait or report blocked. Never propose ending an
   unrelated process, even one described as non-critical. Only a positively
   identified job owned by this Runner may be stopped via its job directory.
4. Launch explicitly using that host's installed Isaac `python.sh`. Use a bounded
   wall timeout. Keep CPU-only USD library overrides out of the graphical runtime.
5. Require `launch-report.json` **and** a matching fresh `run-report.json`; Kit can
   exit zero even after Python errors. Inspect failed checks, traceback/logs and
   screenshot before calling a smoke run successful.
6. Stop using the job-local `stop` command. It never accepts a PID. The supervising
   launcher terminates only the process group it created if stop/timeout requires it.

```sh
python scripts/simulation_runner.py prepare \
  --input /absolute/path/to/scene-package \
  --request examples/smoke.json --output /absolute/path/to/new-job
python scripts/simulation_runner.py launch \
  --job /absolute/path/to/new-job --isaac-python /installed/isaac/python.sh \
  --timeout-seconds 240
python scripts/simulation_runner.py status --job /absolute/path/to/new-job
# In another terminal, if necessary:
python scripts/simulation_runner.py stop --job /absolute/path/to/new-job
```

Preparation/status/stop need standard Python only. Launch requires the actual
Isaac runtime, renderer and display access for interactive jobs. No Blender or
model/API service is needed. The packaged Python code is trusted project runtime;
never import executable code from an arbitrary input asset or frontend code_stub.

## Modes and Parameters

Before proposing launch for a claimed takeoff, compare upward thrust with weight
`mass_kg * gravity_m_s2` and explain the result. On Earth, 6 kg weighs about
58.86 N: 11 N is insufficient for takeoff from rest. State this even in a short
answer. Keep the requested parameters for the comparison experiment; do not
silently add thrust, reduce gravity or label failure to lift as a software error.

- Meadow/space: story presets; physics fields are read-only. They remain bounded
  educational scenes, not infinite terrain or real-scale orbital mechanics.
  A request for lunar gravity in story mode must be rejected as a story edit.
  Offer a separate `moon` experiment job instead; do not silently change modes
  or suggest that story gravity is editable. No mode trains the character's legs.
- Moon: experiment; earth/moon/zero gravity, mass 0.5..10 kg, thrust 0..50 N,
  duration 5/10/20 s, default 10 s. Insufficient thrust is a warning, not an error
  to hide or compensate away. Parameter changes require a fresh prepared job.
- `smoke`: scripted physical inputs, headless by default. This does not test real
  keyboard focus or manual widget interaction.
- `interactive`: bounded 60 s session by default (5..300 s). UI offers reset,
  expressions and head controls; environment/physics are set before launch.

## Controls and Honest Limits

Arrows move; hold A for lift; space scene also supports Z down and Space braking.
R resets. C switches follow/overview cameras; editor cameras remain user-selectable
and are not forced back each frame. Escape stops. Face/head UI controls remain
manual; default expression is natural and fangs appear only when angry.

One final skeletal writer combines visual gait and personality. Actor motion uses
a force-controlled upright capsule, with environmental collision inherited from
the scene. This is not joint-level locomotion, learned balance, real aerodynamics
or a Sim2Real-ready articulated robot. LOD changes visuals, not collision geometry.

Deliver the job path, reports, screenshot, checks and outstanding limits. Do not
claim every rock contact or human keyboard use was tested from the scripted smoke
test. No measured GPU-memory improvement, independent evaluation, formal security
scan or NVIDIA certification is implied. See [validation](BENCHMARK.md).
