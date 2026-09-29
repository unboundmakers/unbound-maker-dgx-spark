# Runner Contract 0.1.0

## Input

Trusted local successful Scene Builder or Scene Optimizer **0.1.0** output.
The supplied inventory is verified and only its listed files copied. This does
not sandbox hostile USD native parsers or establish asset authenticity.
Input character is the current flyingcat-v1 skeleton. The runtime uses its own
fixed personality/motion modules, not Python bundled inside the character input.

Request accepts these fields only:

| Field | Values / default |
| --- | --- |
| schema_version | Integer 1 |
| run_kind | smoke (default), interactive |
| headless | Boolean; defaults true for smoke, false for interactive |
| session_seconds | Interactive bound 5..300 s, default 60 |
| environment | Moon experiment only: earth 9.81, moon 1.62 (default), zero 0 m/s2 |
| mass_kg | Moon experiment only: 0.5..10, default 2 |
| thrust_n | Moon experiment only: 0..50, default 7 |
| duration_s | Moon experiment only: integer 5, 10 (default), 20 |

Story presets reject explicit physics fields even if they repeat the default.
UI should disable those fields. Gravity and mass are independent of visual scale.
Upward force includes an explicitly approximate vertical drag term; it is not a
vacuum free-fall/aerodynamics model. The moon zero-gravity option is an educational
comparison on the same surface, not a claim about actual lunar conditions.

The moon interactive trial stops accepting motion inputs at its experiment time;
R resets and starts another trial within the bounded preview session. Gravity still
acts afterward. Mass/thrust/environment cannot be hot-modified: stop and prepare a
new job. Source scene and mode are selected during preparation, not switched in-place.

## Job Lifecycle

```text
job.json                job id, entry paths, complete immutable input inventory
request.json            normalized runtime parameters
scene/                  full copied scene package, including licenses/source records
runtime/                trusted fixed runner, personality and motion modules
launch.lock             exclusive, never removed for reuse
state.json              starting/running heartbeat, then final runtime state
STOP                    job-local cancellation request, optional
runtime.log             Isaac stdout/stderr
trajectory.json         sampled simulation time, XYZ, velocity XYZ, clearance
preview.png             actual viewport image, not generated concept art
run-report.json         runtime checks, job id and request hash
launch-report.json      parent verdict, exit code, wall duration, report validity
```

`prepare` writes the job last. Incomplete directories without job.json are not
deliverables. Every run is single-use, including failed/stopped runs; use a new
directory for retries. Do not edit a prepared request or runtime: verification
will reject changed file hashes. Scene/worker paths are relative within the job.

The launcher is a foreground supervisor, not a daemon/service. An Agent may run it
as its managed child and poll status from another invocation. `stop` writes a flag;
runtime exits at its next loop check. Parent gives up to 8 s grace then terminates
its own process group, escalating after 5 s if needed. Default startup+run timeout
is 240 s, configurable 1..600 s. A vanished supervisor may leave a stale heartbeat;
status alone is not proof a process is alive. Never recover by killing generic
`python`, `kit` or `Isaac` processes.

## Runtime Integration

Create an anonymous live root with the packaged entry as a sublayer. Kit may author
transient root metadata there. User runtime edits (physics actor, animation, camera,
LOD) use the session layer. No source layer is saved or flattened.

Actor is `/World/Character`, visual `/World/Character/Pose/Visual`.
An upright capsule with CCD is added as a simple gameplay proxy; its dimensions
follow character bounds, its mass stays explicit. Rotation is locked on the body;
visual flight tilt and joint animation do not turn the collision body.

One World.step(render=True) per 1/30 s frame advances four 1/120 s physics substeps.
Force is refreshed on each physics callback. Smoke acceptance compares actual
callback time to requested duration, not just outer-loop iterations.

Follow camera is a separate actor child. Camera choice changes only on startup or
explicit C input. Grass LOD uses the existing 21/27 m near and 42/52 m distant
hysteresis; space uses 90/120 m. Selection runs every 0.5 simulated seconds using
the active camera. Existing far variants are restored to near on approach. No
payload/contact unloading or automatic planet navigation is implemented here.

## Origins and Packaging

`runtime/personality.py` is vendored unchanged from Personality Builder 0.1.0.
`runtime/character_motion.py` is vendored unchanged from the project meadow-v0.3
visual animation. Other runner code adapts the inspected project run_flight,
character_animation, meadow_scene and space control logic to the new package paths.
No third-party models/textures/fonts are included in the Skill archive. Original
scene attribution and usage restrictions remain in the job's scene tree.

Reference for the standalone lifecycle:
[NVIDIA Isaac Sim 5.1 Hello World](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/core_api_tutorials/tutorial_core_hello_world.html).
Installed source/API examples, not latest-version assumptions, govern compatibility.
