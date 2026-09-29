# Development Checks

Release-candidate supplement (2026-09-29): fresh Mac/Spark regression, limited
prompt-only comparisons and security review are recorded in
[release checks](../../verification/release-20260929/README.md). Earlier pending
statements below are historical. Prompt probes are not full tool-execution A/B;
the new Qwen3.6 runtime failure is not counted as a pass.

From repository root, use an existing OpenUSD Python and both sibling builder Skills:

```sh
UNBOUND_SCENE_ASSETS=/absolute/path/to/approved/template-root python -m unittest discover -s skills/unbound-maker-scene-builder/tests -v
```

Tests use actual authored templates, not primitive stand-ins. Missing assets fail the suite rather than reporting skipped success. Source root must match assets/catalog.json. Mac wheel stability setup may use process-local PXR_WORK_THREAD_LIMIT=1; do not globalize that setting into Isaac.

Coverage: all three scenes, valid/invalid mode and heading, source inventory integrity, path restrictions, character relocation and source preservation, dependency closure, missing texture rejection, retained instancers/colliders/variants, payload unload/reload, moon-only camp, optional camera and default gravity.

No GPU timings, VRAM reduction, contacts, live controls or renderer shader compilation are measured here. Hashes are not signatures. Agent cases in evals/evals.json are prepared but not A/B tested. Exact run results are in the repository verification folder.
