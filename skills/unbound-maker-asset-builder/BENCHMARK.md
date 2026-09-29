# Asset Builder 0.1.0 Test Status

Release-candidate supplement (2026-09-29): fresh Mac/Spark regression, limited
prompt-only comparisons and security review are recorded in
[release checks](../../verification/release-20260929/README.md). Earlier pending
statements below are historical. Prompt probes are not full tool-execution A/B;
the new Qwen3.6 runtime failure is not counted as a pass.

Date: 2026-09-29.

## Development checks

Mac: Python 3.12.14, OpenUSD 0.25.5 (usd-core 25.5.1).
Initial suite: 14 tests passed, including invalid requests, dependency failure, actual USD builds, sRGB conversion, scale, 77 mesh/14 joint preservation, relocation, source immutability, output protection and template tampering.
OpenUSD wheel prints an ARCH_CACHE_LINE_SIZE warning on this Mac; it did not fail the tests. This warning is not evidence of Spark compatibility.
One later default-parallel suite failed intermittently while reading USDC (scale test failed; source-immutability test errored). Source hashes were unchanged. Ten subsequent default-parallel runs and twenty runs with PXR_WORK_THREAD_LIMIT=1 passed. Root cause is not proven fixed; Mac development uses the process-level single-thread setting for now.
The latest test count and Spark results are maintained in the project verification report, not implied by this initial run.

## Spark development validation

Linux aarch64, Isaac-bundled Python 3.11.13 and OpenUSD 0.24.5. No packages installed into Isaac, no GPU scene started.
First run: 13 passed, 1 test failed because -S still inherited PYTHONPATH, so the missing-dependency fixture was not isolated. Corrected test subprocess flags to -I -S; asset generation code was unchanged.
After correction: all 14 tests passed. Five additional default-thread runs: 70 tests, zero failures/errors/skips. A real #2867D7, 1.5x template build succeeded.
This validates CPU USD file construction on Spark, not rendering, physics, Agent orchestration or a closed fix for the intermittent Mac issue.

## Agent evaluation

NOT RUN. Six task definitions are prepared. No with/without-Skill runs, SkillLift, timing benefit, token savings or agent pass rate have been measured.
These development tests are not a NVIDIA SkillEvaluator Tier 3 benchmark.

## Security and signing

Formal SkillSpector/SkillEvaluator scans: NOT RUN.
Team signature and strict signature verification: NOT RUN.
Do not label this development package fully verified or officially certified.
