# Unbound Maker Builder Agent 0.1.0

Independent, bounded Python Agent for the five Unbound Maker Skills. Runs on DGX Spark;
no OpenClaw dependency, cloud model, public listener, arbitrary code execution or training.

## What It Does

Natural-language instruction -> model-selected parameter patch -> asset -> personality ->
scene -> optimizer -> simulation Runner -> verified screenshot, trajectory, reports and portable scene ZIP.

The local model selects actions using a JSON action protocol over `/v1/chat/completions`.
The Harness validates every action. It has 12 model turns and one format/plan repair;
successful prose cannot bypass missing tools, bad inventories or failed simulation reports.

Two explicit modes:

- `agent`: real configured local model makes decisions. Unavailable model = failed job.
- `structured`: validated design form runs the same fixed Skill chain without calling a model.

Mock models appear only in tests and report `execution_mode=mock`. Do not call those real Agent verification.

## Requirements

Python 3.10+ on Linux/macOS, stdlib only. The five Skills must be installed under a common
`skills_root`. CPU USD, Isaac Sim and scene template assets are external prerequisites.
Use each Skill's own setup instructions; the Agent never installs them automatically.

`operator.spark.example.json` records this Spark's installed paths. On another host,
edit all absolute paths and installed USD locations. Do not guess versions.
`model.base_url` is restricted to a loopback HTTP `/v1` endpoint; no cloud fallback.

## Local Model

Qwen3.6-35B-A3B (`qwen3.6:35b-a3b-spark128`) passed the real browser-to-Agent-to-Isaac
workflow and a browser force-only follow-up, with 11 Runner checks passing per run.
`Qwen36-Spark.Modelfile` retains the Q4_K_M weights with `num_batch=128`.
See [browser acceptance](../../verification/builder-agent/frontend-qwen36-acceptance.md).
Register it with `ollama create qwen3.6:35b-a3b-spark128 -f Qwen36-Spark.Modelfile`
and explicitly set that name in your operator config if testing this workaround.
The system's Ollama 0.20.2 rejected that model. A separate official ARM64 Ollama 0.34.4
was installed under `/home/spark/unbound-maker/tools/ollama-0.34.4`; system Ollama and
existing cached models were not replaced. Model weights use the existing Ollama cache.

Start it explicitly in its own terminal, only when port 11434 is free:

```sh
env OLLAMA_HOST=127.0.0.1:11434 OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_NUM_PARALLEL=1 OLLAMA_KEEP_ALIVE=2m OLLAMA_NO_CLOUD=1 OLLAMA_NOPRUNE=1 /home/spark/unbound-maker/tools/ollama-0.34.4/bin/ollama serve
```

In another terminal, download/resume the user-approved model:

```sh
/home/spark/unbound-maker/tools/ollama-0.34.4/bin/ollama pull qwen3.6:35b-a3b
```

The model-list readiness check proves registration/reachability only, not successful inference.
Real-model acceptance requires the integration command below to pass.

## CLI

From `/home/spark/unbound-maker/agents/builder`:

```sh
python3 builder.py --config operator.spark.example.json capabilities
python3 builder.py --config operator.spark.example.json project --design examples/blue-moon.json
python3 builder.py --config operator.spark.example.json submit --project PROJECT_ID --revision REVISION_ID --mode agent --request-id demo-1 --instruction 'Make a blue flying cat on the moon; run a 10-second test.'
python3 builder.py --config operator.spark.example.json worker --once
python3 builder.py --config operator.spark.example.json status --job JOB_ID
python3 builder.py --config operator.spark.example.json cancel --job JOB_ID
```

Use returned IDs, not the placeholder names. Without `--once`, worker processes queued jobs
until interrupted. No daemon or login autostart is installed. Failed or interrupted jobs are
never silently retried; submit a new request ID after fixing the cause.

## Frontend API

Set `UNBOUND_BUILDER_TOKEN` to a random ASCII secret of at least 32 characters in your shell
or secret manager. Never commit it. Then:

```sh
python3 builder.py --config operator.spark.example.json serve --port 8765
```

This starts HTTP and one worker. All API requests require `Authorization: Bearer TOKEN`.
The fixed UI shell at `/` is accessible without a token; data and job creation are not.
Enter the token in the page to connect. It is held in memory only and cleared on reload.
JSON request body maximum 64 KiB. No CORS, no public binding, single-user service only.
Mac access uses an SSH tunnel (substitute the current Spark address):

```sh
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 USER@SPARK_HOST
```

| Method / path | JSON body / purpose |
| --- | --- |
| GET `/api/capabilities` | Ranges, scene modes, model registration readiness |
| POST `/api/projects` | `{"design": {...}}`; returns project and immutable revision |
| POST `/api/projects/{id}/revisions` | `{"parent_revision":"...","patch":{"simulation":{"thrust_n":11}}}` |
| POST `/api/jobs` | `{"project_id":"...","revision_id":"...","execution_mode":"agent","request_id":"unique","instruction":"..."}` |
| GET `/api/jobs/{id}` | Stage events, status, effective revision and registered artifact IDs |
| POST `/api/jobs/{id}/cancel` | `{}`; persists cancellation independently of client connection |
| GET `/api/artifacts/{id}` | Only registered, hash-checked files; never arbitrary paths |

Duplicate request ID and identical inputs return the existing job. Different inputs with the
same ID, or an outdated parent revision, return 409. Invalid inputs return 400, missing IDs 404.
`detail.revision_id` is the effective model-modified version; the top-level revision remains
the immutable original submission. Save the effective ID for the next edit.

Open `http://127.0.0.1:8765/` after starting the tunnel. The included panel supports a
natural-language job, progress/cancel, the real screenshot/report, and a structured
moon-thrust follow-up. The latter does not call the model again.

An optional `serve --preview-html /absolute/path/to/concept.html` loads an operator-provided
concept page into a sandboxed iframe. Its network and community publishing are disabled.
Only a validated body color is imported on explicit click; wings, phrase, battery and
personality tags are not mapped. The upstream HTML is not distributed in this repository
pending its license confirmation. Without it, the page shows a placeholder.

The frontend team owns the fuller conversation UI and community workflow.
This Agent owns parameter validation, construction, version reuse and execution evidence.
The scene ZIP is a portable OpenUSD bundle, not a self-contained Isaac application or web stream.

## Safety / Limits

- Only `flyingcat-v1`, manual natural/curious/angry runtime expressions, meadow/space/moon templates.
- Story physics is read-only. Moon supports Earth/Moon/zero gravity, mass, thrust and 5/10/20s runs.
- Weak thrust is an experiment outcome, not permission to modify requested physics.
- Cache keys include adapter contract, Skill content hashes, normalized input and upstream manifest SHA.
- Reused assets are hash-checked again. Runner jobs and simulation evidence are never reused.
- Force-only changes reuse the first four stages. Color/scale changes invalidate all downstream assets.
- One worker per state root, shared GPU lock, refusal when other Isaac work is detected.
- Cancellation signals only owned processes, with Runner STOP and bounded cleanup of nested Isaac processes.
- A hard crash cannot promise immediate child cleanup. Restart marks unfinished jobs interrupted;
  detected leftover Isaac sessions block new GPU work and are never killed by unverified PID.
- Local model calls are bounded to 120 seconds by default; cancellation during inference is applied
  after the current request returns or times out. It is not instantaneous inference cancellation.
- Source Skills and old playable scenes are not edited. No Isaac Lab training or Sim2Real claims.

## Tests / Evidence

```sh
python3 -m unittest discover -s tests -v
python3 tests/integration_spark.py --config operator.spark.example.json --mode structured
python3 tests/integration_spark.py --config operator.spark.example.json --mode agent
python3 tests/integration_cancel.py --config operator.spark.example.json
```

Integration commands start real bounded GPU work. They require free Isaac/GPU capacity and
do not run automatically with unit tests. Results live under `root` (default `builder-state`).
Inspect `jobs/JOB_ID/error.json`, stage logs, manifests and Runner reports when failures occur.
See project `verification/builder-agent-ledger.md` for completed verification records.
These are team tests, not NVIDIA official certification or a security audit.

Opt-in browser acceptance (requires the service, SSH tunnel, Playwright and Chrome):

```sh
UNBOUND_TEST_TOKEN_FILE=/private/path/access-token node tests/frontend_spark.cjs
```

Set `PLAYWRIGHT_MODULE` to an installed package path if it is not in Node's search path.
For the verified Qwen3.6 configuration, set `UNBOUND_TEST_MODEL=qwen3.6:35b-a3b-spark128`
and `UNBOUND_TEST_CONCEPT=0`; set `UNBOUND_TEST_URL` to the local tunnel address.
The service operator config must select the same model. The test performs real GPU work
and writes private evidence under `artifacts/`. Do not publish its browser profile or token.
See [Qwen3.6 browser acceptance](../../verification/builder-agent/frontend-qwen36-acceptance.md).
