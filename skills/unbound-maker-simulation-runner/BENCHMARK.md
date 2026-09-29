# Validation

Release-candidate supplement (2026-09-29): fresh Mac/Spark regression, limited
prompt-only comparisons and security review are recorded in
[release checks](../../verification/release-20260929/README.md). Earlier pending
statements below are historical. Prompt probes are not full tool-execution A/B;
the new Qwen3.6 runtime failure is not counted as a pass.

CPU regression (standard Python plus USD for session/animation test):

```sh
UNBOUND_SCENE_PACKAGES=/absolute/path/to/artifacts python -m unittest discover -s skills/unbound-maker-simulation-runner/tests -v
```

Requires all six prior `scene-{meadow,space,moon}-v0.1.0` and
`optimized-{meadow,space,moon}-v0.1.0` packages. Missing inputs fail, not skip.
Cases cover modes/parameters, inventory/tampering, source preservation, job relocation,
single-use launch, zero exit without report, stop scope, forces/LOD, session-only
character and camera edits, single skeletal writer, raycast types and frame budget.
The 13-case suite also runs real non-GPU child processes to check timeout and
live STOP cleanup, and checks status while the runtime includes a job identity.

GPU smoke: prepare a fresh job with `examples/smoke.json`, then explicitly launch
with the installed Isaac Python and a bounded timeout. Inspect all checks and logs,
view preview.png and require job/request identity matches. Run one GPU test at a time.
Never infer success from a zero Kit exit or a leftover screenshot from another job.

Smoke checks include finite trajectory, real physics callbacks, spawn contact on
grounded templates, horizontal movement, lift when thrust exceeds weight, reset,
gravity, physics duration, source-layer preservation and screenshot existence.
Source disk file hashes should also be rechecked after a real run.

GPU memory improvement, all rock contacts, long-distance traversal, manual UI,
keyboard focus and performance comparison are separate validation tasks.
Exact executed results belong in `verification/simulation-runner-0.1.0.md`.
