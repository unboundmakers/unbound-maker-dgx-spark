# Simulation Runner 0.1.0 Verification

Date: 2026-09-29. Self-tested development package, not NVIDIA-Verified.
No official signature, SkillSpector scan, independent Agent evaluation or public upload.

## Executed Tests

| Environment | Result | Evidence |
| --- | --- | --- |
| Mac Python 3.12.14 / usd-core 25.5.1 | 13/13, 12.765 s | runner-tests-mac.log |
| Spark aarch64 Python 3.11.13 / USD 0.24.5 | 13/13, 11.215 s | runner-tests-spark.log |
| Skill frontmatter validation | Passed | skill-creator quick_validate.py |
| Spark Isaac 5.1 meadow | Succeeded, 10 s / 1200 physics callbacks, 7 LOD changes | runner-meadow/run-report.json |
| Spark Isaac 5.1 space | Succeeded, 10 s / 1200 physics callbacks, 3 LOD changes | runner-space/run-report.json |
| Spark Isaac 5.1 moon | Succeeded, 10 s / 1200 physics callbacks | runner-moon/run-report.json |
| Moon scene, earth gravity comparison | Succeeded, 10 s / 1200 callbacks, insufficient-thrust warning | runner-moon-earth/run-report.json |
| Post-run scene/job inventories | All listed files match SHA256 | runner-integrity-spark.json |

Actual viewport screenshots for the three scenes were opened and inspected. Each
shows the blue test cat, environment materials and inherited scene composition.
These are real Isaac screenshots, not AI-generated concepts. Moon retains its
astronaut, rover, lander and detailed surface. No redesign was attempted.
The three successful logs contain no Traceback, AttributeError or [Error] matches.

An additional identical-input moon/earth comparison used 2 kg, 7 N and the same
scripted inputs. In simulated seconds 3.5..5, max actor Z was 2.933 m under lunar
gravity and 0.035 m under earth gravity; settled Z was approximately 0 in both.
The earth run correctly warned of insufficient thrust. Its screenshot was also
opened and inspected. This checks educational contrast, not vacuum-model accuracy.

All four jobs passed post-run inventory checks and all their runtime Python files
match the final Skill: `runner-final-integrity-spark.json`.

## Package and Cleanup

- Archive: `dist/unbound-maker-simulation-runner-0.1.0-dev.zip`.
- 17 files, 31,788 bytes; source, zip and Spark installed files match byte-for-byte.
- SHA256: `1ee89e28834e1db28b8ce6b222fd64b8cd7c04c1743bf210633be5746a15b43f`.
- Inventory evidence: `runner-package.json`, `runner-package-spark.json`.
- Final Spark GPU snapshot: 43 C, 0% utilization; process-name check found no
  isaac_runtime.py, Isaac Kit or simulation_runner.py launch process.
- Skill installed only at `/home/spark/unbound-maker/skills/unbound-maker-simulation-runner`.
  No global Codex/OpenClaw registration was made.

Smoke checks cover finite trajectory, actual physics callback, horizontal movement,
lift where thrust exceeds weight, reset, gravity, requested physics duration, source
root preservation and screenshot creation. Grounded templates also check spawn
settling near ground. Source/job file hashes were rechecked after execution.

CPU tests use six real Scene Builder/Optimizer packages, test relocation, integrity
and tamper rejection, isolated session edits, single animation writer, manual facial
state, LOD/collision separation, raycast type compatibility and timing. Real bounded
non-GPU subprocess fixtures exercise timeout and STOP cleanup. A zero exit without
a matching report is rejected; used jobs cannot be relaunched.

## Fixed During Verification

1. PhysX RaycastHit objects do not implement dict.get; accept both object and dict.
2. A rendered World.step already advances four physics substeps. The old mixed
   loop advanced 2100 ticks while claiming 10 s. New loop measures 1200 ticks.
3. Kit authors transient root metadata. An anonymous live root now holds the
   source as a sublayer; runtime overrides stay in the session layer.
4. The second prepared task retained the earlier runtime. A fresh r3 task was
   prepared from the synchronized code; immutable old jobs were not edited.
5. Running status could contain job_id twice. Added a failing regression case,
   then fixed dictionary merge. Both platforms pass the final 13-case suite.

Failed earlier runs are retained on Spark as runner-meadow-smoke-v0.1.0 and -r2.
Only -r3 is accepted meadow evidence. Parent verdicts require matching job/request
identity rather than trusting Kit exit code zero.

## Boundaries

- GPU smoke injects scripted inputs. Physical keyboard focus, UI widgets and
  switching cameras by hand were NOT tested. Previous camera transform is checked.
- No articulated balance, trained gait, aerodynamic or scientifically accurate
  vacuum model. Motion uses an upright capsule; legs/head/face are visual animation.
- Individual rock collisions, long-distance terrain traversal, frame-rate and GPU
  memory improvement were not measured. LOD counts are not a memory benchmark.
- Only trusted local inputs/runtime; input hashes are not authenticity signatures.
- Original playable prototype and prior Skill source were not edited. No global
  environment changes, GitHub upload or Agent/frontend service was made.

See `docs/simulation-runner-spark.md` and the Skill's `references/runtime-contract.md`
for launch/stop semantics, input ranges, source attribution and known limits.
