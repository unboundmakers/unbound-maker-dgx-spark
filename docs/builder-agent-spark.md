# Builder Agent on DGX Spark

2026-09-29 working deployment. Qwen3.6-35B-A3B Q4_K_M independent Agent integration passed. Earlier Qwen2.5-7B real Agent and minimal browser acceptance passed. See [Qwen3.6](../verification/builder-agent/qwen36-acceptance.md) and [Qwen2.5](../verification/builder-agent/qwen25-acceptance.md).

## Runtime Note

Repeated prompt evaluation with Qwen3.6 on this Ollama/Spark combination encountered
a CUDA illegal memory access in the quantized matrix kernel, including after a
cold load. The same Runner prompts returned with `num_batch=128`. The optional
`agents/builder/Qwen36-Spark.Modelfile` registers an alias using the same weights;
it is a deployment workaround observed in prompt tests, not a stability guarantee.
Use bounded jobs and inspect actual reports on service errors. Never report a
model service error as a successful build or silently substitute another model.

## Locations

| Component | Spark path |
| --- | --- |
| Agent source | `/home/spark/unbound-maker/agents/builder` |
| Operator config | `/home/spark/unbound-maker/agents/builder/operator.spark.example.json` |
| Existing five Skills | `/home/spark/unbound-maker/skills` |
| Template scenes | `/home/spark/unbound-maker-meadow-v0.3` |
| Isolated Ollama 0.34.4 | `/home/spark/unbound-maker/tools/ollama-0.34.4/bin/ollama` |
| Model cache | `/home/spark/.ollama/models` |
| Download progress | `/home/spark/unbound-maker/downloads/qwen3.6-pull.log` |
| Jobs / immutable artifacts | `/home/spark/unbound-maker/builder-state/jobs` |
| Model integration status | `/home/spark/unbound-maker/builder-state/model-integration-status.json` |
| Real model integration log | `/home/spark/unbound-maker/builder-state/model-integration.log` |

Connect using your own `USER@SPARK_HOST` and verify the device's SSH host key.
The IP can change with Wi-Fi; never bypass host-key checks.

## Verified So Far

- 26 regression tests on Mac and Spark, including real localhost HTTP requests.
- Five real Skills in structured mode: blue flying cat, moon, 10-second smoke simulation.
- Force-only change 7N -> 11N: first four stages reused, new Runner, all checks passed.
- Real Isaac cancellation: no remaining detected Isaac processes.
- Screenshot inspected; all existing Skill sources unchanged during integration.

The earlier structured tests do not prove model inference. A separate Qwen2.5-7B
run now demonstrates one real model-directed case after prompt corrections, with one
JSON repair. This is not a broad reliability benchmark or a Qwen3.6 result.
The project source contains no mock fallback and cannot turn model unavailability into success.

## Repeat Model Acceptance When Needed

The selected Qwen3.6 model is already registered. The download/test helper below
is retained for future deployments, not as a currently pending task:

```sh
python3 /home/spark/unbound-maker/agents/builder/tests/wait_model_integration.py --config /home/spark/unbound-maker/agents/builder/operator.spark.example.json --wait-seconds 7200
```

Only run one copy. It waits for the selected model to be registered, then runs actual Agent
integration and a force-only follow-up. States are `waiting_for_download`,
`running_real_model_integration`, `passed`, `failed` or `timed_out`.
It does not fix failed tests automatically, restart downloads, install services or run periodically.
It records separate evidence and never labels a pending download as verified.

Do not restart a healthy download to change its time limit. Inspect the currently
running process and logs before any recovery action. Ollama can reuse valid downloaded
chunks; interrupting a write may damage checkpoint metadata. Do not delete caches or
overwrite system Ollama. Runtime limits depend on how the operator started the process.

## Frontend Handoff

See `agents/builder/README.md` for API contracts and SSH forwarding. The frontend team keeps
its conversation and form UI, sends supported design fields, polls `job_id`, and fetches
registered preview/report/scene ZIP artifacts. The minimal browser path is tested with Qwen2.5; the larger concept frontend remains a separate integration.

The team must still integrate the UI, test a real human keyboard session, review asset licenses
before distribution, and prepare competition documentation/video. Team self-verification is
distinct from NVIDIA official signing. No NVIDIA signing claim is made.
