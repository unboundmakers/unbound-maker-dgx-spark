# Qwen2.5-7B real Agent acceptance

Date: 2026-09-29. Device: DGX Spark, local Ollama 0.34.4.
Model: `qwen2.5:7b`, Q4_K_M, installed model digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`.
This is not a Qwen3.6 result or an NVIDIA certification.

## Evidence

- [Integration report](integration-agent-qwen25-6ad8713666254e43bd6fed3be3c906bb.json)
- [Agent design and stage results](qwen25-result.json)
- [Isaac run report](run-report.json)
- [Actual Isaac preview](preview.png)

Natural-language request: create a blue `#2867D7` flying cat at scale 1 in the moon experiment scene, mass 2kg, upward thrust 7N, natural expression, and a 10-second headless smoke test.

The real model chose configure, asset, personality, scene, optimizer, runner and finish. Five stages passed; no source Skill was changed by the run. Isaac simulated 10 seconds / 1200 physics ticks, with all 11 automated checks true. The report records 25.435 seconds of Runner wall time, not whole-pipeline time. `session_seconds` remained 60; the smoke test actually uses `duration_s=10`. No claim is made that every requested field was explicitly set by the model.

The structured force-only follow-up changed thrust to 11N and reused asset, personality, scene and optimizer, with a fresh Runner. This follow-up was not a second natural-language conversation.

## Failures and correction

Two earlier attempts did not pass:

1. `3feb07933ad0474a8bc1134600a7547a`: physics fields were placed inside scene; validation rejected them and the model requested input.
2. `042751fb9e4741b6be6c8ea918f19ae7`: physics were proposed before switching away from the story scene; validation rejected both attempts.

The operator prompt was clarified to put physics under simulation and switch scene in the same configure action. No validation was relaxed and no automatic success was inserted.

Successful job `6ad8713666254e43bd6fed3be3c906bb` still needed the existing one-repair allowance for a duplicate JSON `arguments` key on turn 1. Correct configuration arrived on turn 2; finish arrived on turn 8. This is one successful end-to-end case after debugging, not a general success-rate benchmark.

## Limits

- No manual keyboard/UI test or frontend integration in this run.
- No learned gait, articulated balance, or aerodynamic model.
- Not all rock contacts tested; GPU memory not measured.
- Separate state directory from the pending Qwen3.6 test; same simulation GPU lock.
- Qwen3.6 download was left running and unchanged during this test.
