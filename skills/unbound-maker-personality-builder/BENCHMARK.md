# Development Verification

Release-candidate supplement (2026-09-29): fresh Mac/Spark regression, limited
prompt-only comparisons and security review are recorded in
[release checks](../../verification/release-20260929/README.md). Earlier pending
statements below are historical. Prompt probes are not full tool-execution A/B;
the new Qwen3.6 runtime failure is not counted as a pass.

Run from repository root with an existing OpenUSD Python:

```sh
python -m unittest discover -s skills/unbound-maker-personality-builder/tests -v
python -m unittest discover -s skills/unbound-maker-asset-builder/tests -v
```

The sibling Asset Builder is a test-fixture dependency only. The Personality Builder's build CLI consumes its output without importing its code.

Coverage: default/three expressions, limits/invalid inputs/reset, full-body pose preservation and no cumulative drift, head descendant transforms and skin bindings, teeth visibility, asset scale/color preservation, relocation without original sources, package hashes, composition tampering, symlinks, conflicting animation owner, missing dependencies and structured CLI errors.

This is not an Agent A/B benchmark, frame-rate measurement, Isaac rendering test or physical safety validation. Prepared Agent cases live in evals/evals.json and have not been executed. Actual dated run evidence is tracked in the repository's verification directory.
