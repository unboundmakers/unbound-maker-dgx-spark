# Skill Card: Unbound Maker Asset Builder

Version: 0.1.0. Maintainer: Unbound Makers project team.
Purpose: locally build a supported skinned visual USD character with limited appearance edits.
Source: Unbound Maker development project; no GitHub release or commit assigned yet.
License: original code Apache-2.0; original Skill prose CC BY 4.0. See ../../LICENSING.md. The FlyingCat source template is excluded from public distribution; display permission does not authorize character reuse. Do not label it CC0 or third-party NVIDIA content.

## Environment and permissions

- Python 3.10+ with pxr OpenUSD. Tested: Python 3.12 / usd-core 25.5.1 on Mac; Isaac-bundled Python 3.11.13 / USD 0.24.5 on Spark aarch64. Spark tests cover file construction, not Isaac rendering.
- No model service, API credential or network access required. No simulator or GPU session starts.
- Reads request JSON and bundled template; writes only the caller-selected new output directory. Caller must provide an approved, private output parent and trusted installation.
- Does not overwrite existing output, delete existing builds or modify the original playable scene.
- Native USD libraries parse the pinned local asset. This is not a safe loader for arbitrary untrusted USD files; the CLI intentionally does not accept them.

## Limits and risks

Only flyingcat-v1, primary-body color and uniform scale are supported. No arbitrary model generation, anatomy reconstruction, URDF, sim-to-real, emotional inference or training.
Asset validation checks USD structure, bindings, units, dependencies and bounds. It does not establish artistic quality, material appearance in every renderer or physics readiness.
One intermittent Mac USDC read failure was observed during repeated testing; subsequent runs passed. A process-level PXR_WORK_THREAD_LIMIT=1 setting is used for Mac development checks. This is a mitigation under observation, not a proven upstream fix. Spark's separate default-thread test results are recorded in BENCHMARK.md.
SHA256 pins accidental template changes, but an attacker who can alter both code and registry can bypass it. Publisher authenticity requires a separately verified release signature.
Do not insert children's names, photos, private conversations or credentials into request/provenance files.

## Verification status

Current source candidate: see [2026-09-29 release checks](../../verification/release-20260929/README.md)
for fresh dual-host regressions, Bandit review, limited prompt probes and remaining
gates. Historical development status below does not override that scoped report.

Development unit/structural tests: run; see BENCHMARK.md and project verification report for exact scope.
Skill format validation: recorded after execution in the project report.
SkillSpector/SkillEvaluator security and Agent A/B evaluation: not run.
Team signing: not performed. NVIDIA official certification: not requested and not claimed.
Evaluation tasks exist in evals/evals.json; presence of a dataset is not an evaluation result.
