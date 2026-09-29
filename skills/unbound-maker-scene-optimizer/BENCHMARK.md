# Development Validation

Release-candidate supplement (2026-09-29): fresh Mac/Spark regression, limited
prompt-only comparisons and security review are recorded in
[release checks](../../verification/release-20260929/README.md). Earlier pending
statements below are historical. Prompt probes are not full tool-execution A/B;
the new Qwen3.6 runtime failure is not counted as a pass.

Run using an existing OpenUSD Python:

```sh
UNBOUND_SCENE_PACKAGES=/absolute/path/to/artifacts python -m unittest discover -s skills/unbound-maker-scene-optimizer/tests -v
```

The artifact folder must contain `scene-meadow-v0.1.0`, `scene-space-v0.1.0` and
`scene-moon-v0.1.0` from Scene Builder. Missing artifacts fail instead of silently
skipping integration tests. Production CLI has no dependency on sibling Skills.

Cases cover request validation, dependency inventory, missing textures, path safety,
hash tampering, preserve/preview, relocation, payload loading, instancer arrays,
protected character/collider/camera state and output manifest integrity.

This is a CPU structure suite, not a GPU benchmark. Exact run evidence, versions
and observed before/after counts belong in `verification/scene-optimizer-0.1.0.md`.
Do not translate disk bytes or mesh points into VRAM savings. Agent cases are
prepared in `evals/evals.json`; independent behavioral execution is still pending.
