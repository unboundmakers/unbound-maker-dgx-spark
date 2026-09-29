# Qwen3.6 independent Agent acceptance

Date: 2026-09-29. Platform: DGX Spark, local Ollama 0.34.4.
Model: `qwen3.6:35b-a3b`, 35.5B, Q4_K_M (not FP8).
Registered model size: 22,621,314,381 bytes. Download completed before this test.

Later release prompt probes encountered CUDA illegal memory access. The earlier
successful integration remains historical evidence, not proof of current service
stability. See [release checks](../release-20260929/README.md). Keep the existing
Qwen2.5 browser configuration rather than silently swapping the demo model.

## Observed result

- Model integration status: `passed`; integration summary: `succeeded`.
- First Agent job: `3cc7c3ff10aa4a119980a9650f2025df`.
- Force-only follow-up: `f1d5795d4d5a48558fd322f44abed396`.
- Scenario: blue template character, moon, 2kg, 7N, 10 seconds; follow-up 11N.
- Follow-up reused asset, personality, scene and optimizer; Runner was not reused.
- Existing first-stage caches were available in this state directory. This is not
  evidence of a cold rebuild of every asset; it is model-directed orchestration,
  verified cache reuse and a fresh actual simulator run.
- Skill sources unchanged; no trained locomotion policy.

The follow-up uses the structured parameter-edit path; do not call it a second
natural-language planning test. Source summary: [qwen36-result.json](qwen36-result.json).

## Scope

This is one bounded integration case, not an aggregate model success rate.
No separate Qwen3.6 browser or human keyboard acceptance was performed.
The demonstrated browser path remains Qwen2.5. No arbitrary image-to-robot
generation, NVIDIA certification or new physical robot capability is claimed.
