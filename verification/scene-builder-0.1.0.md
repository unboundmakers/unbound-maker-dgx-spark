# Scene Builder 0.1.0 Development Verification

Date: 2026-09-29. Scope: template packaging and CPU OpenUSD validation.

## Evidence

| Item | Result | Evidence |
| --- | --- | --- |
| Mac scene suite | 10 passed, no errors/failures | scene-builder-mac-tests.txt |
| Spark scene suite | 10 passed, no errors/failures | scene-builder-spark-tests.txt |
| Mac Asset regression | 14 passed | scene-asset-regression-mac.txt |
| Mac Personality regression | 16 passed | scene-personality-regression-mac.txt |
| Source parity | 98 selected source files, none missing or changed | scene-builder-spark-source-check.json |
| Mac builds | meadow, space, moon succeeded | scene-builder-mac-builds.json |
| Spark builds | meadow, space, moon succeeded | scene-builder-spark-builds.json |
| Skill metadata | quick_validate.py passed | Recorded command output |

Mac used existing Python 3.12 / USD 0.25.5 with process-local PXR_WORK_THREAD_LIMIT=1. Spark used existing Isaac Python 3.11 / USD 0.24.5 without a thread override. No dependencies or GPU processes were installed/started.

Archive: dist/unbound-maker-scene-builder-0.1.0-dev.zip, 26,537 bytes. SHA256: `90ca01ad12d6327528ab026f289d42d02b9734b1619340200eda085beb2228d3`. All 13 packaged files matched both the local source and installed Spark copy; see scene-builder-spark-package-check.json. SHA256 is not a digital signature.

## What Was Checked

Three real environment templates (not placeholder primitive scenes); matching scene/mode selection; finite heading; preset spawn; strict request keys and duplicate-key rejection; relative file paths and hashes; source character unchanged; one character skeleton; retained material bindings, collisions, PointInstancer, near/far variants; payload unload/reload; moon-only astronaut/camp; optional preview camera; default gravity; missing texture rejection and relocation to another directory.

The new character has no RigidBodyAPI. Runtime animation/input/physics are intentionally not started. A direct Mac bounds probe confirmed the scaled character's lower bound is 0.05 m above the meadow start plane and its 1.5 scale remains authored.

TDD: initial tests failed because scene_builder was absent. After implementation, all real scene builds and contract checks passed; additional missing-texture, duplicate JSON and path restriction cases passed. Author review checked source ownership, selected dependencies, modes, actor offset, material requirements and scope. No independent reviewer was available.

## Output Sizes

Spark manifest totals excluding the final manifest itself:

- meadow: 37,058,784 bytes, 34 files.
- space: 16,054,933 bytes, 40 files.
- moon: 147,822,709 bytes, 69 files.

These are disk bytes, not runtime memory or GPU savings. Per-output copies intentionally trade disk deduplication for relocatability. Original templates preserve their internal instancing and relative references.

## Expected Warnings / Limitations

Mac USD wheel emits ARCH_CACHE_LINE_SIZE warning. The missing-texture negative test deliberately emits a missing earth-4k.jpg warning. Astronaut dependency analysis emits unresolved OmniPBR.mdl/OmniGlass.mdl warnings in CPU USD; exactly these two are declared consumer runtime requirements. No other missing texture is accepted.

Both MDL files were found under /home/spark/IsaacSim/_build/linux-aarch64/release/kit/mdl/core/Base. Initial directory search also reported an unrelated screenshot-directory permission denial; no permission was changed. Module presence is not shader compilation or visual verification.

No live Isaac screenshots, GPU resource measurements, PhysX contact tests, keyboard interaction, automatic LOD switching, Agent A/B evaluation, security scanner, team signature or upload were performed. Source provenance stays in each selected package; downloadable redistribution of third-party assets remains a separate permission review.
