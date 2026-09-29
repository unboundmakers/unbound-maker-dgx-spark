# Scene Optimizer 0.1.0 Development Verification

Date: 2026-09-29. Scope: executable Skill packaging, CPU USD validation, private
project-directory deployment. No public upload and no change to the playable prototype.

## Deliverables

- Skill: `skills/unbound-maker-scene-optimizer` (14 files).
- Archive: `dist/unbound-maker-scene-optimizer-0.1.0-dev.zip`, 25,807 bytes.
- Archive SHA256: `21d1e7042755d75f4540927c30af950577081b1ffc47f0c5275b1738c978a15e`.
- Spark: `/home/spark/unbound-maker/skills/unbound-maker-scene-optimizer`.
- Local and Spark examples: `artifacts/optimized-{meadow,space,moon}-v0.1.0`.
- Each example contains `optimized.usda`, full unchanged `base/`, scene config,
  optimization report and complete file manifest.
- Local source, archive and Spark installation: all 14 file hashes identical,
  recorded in `scene-optimizer-package-check.json`.

## Executed Evidence

- RED: initial 10 tests failed because the implementation was absent.
- First implementation exposed a missing root-layer defaultPrim declaration;
  fixed explicitly without changing input metadata.
- Mac first 10 tests passed; two added adverse-contact/CLI tests also passed.
- A malformed manifest test exposed unhandled object types; contract validation
  was added and the complete final suite rerun.
- Spark final suite: **13/13 passed**, 53.034 s, Python 3.11.13 / USD 0.24.5,
  aarch64. `scene-optimizer-spark-final-tests.txt`.
- Mac final suite: **13/13 passed**, 405.272 s, Python 3.12.14 / USD 25.5.1,
  process-local single-thread setup. `scene-optimizer-mac-final-tests.txt`.
  Suite duration is not a controlled load-time or performance benchmark.
- Mac regressions: Asset Builder **14/14** and Personality Builder **16/16** passed.
  Logs: `optimizer-asset-regression-mac.txt`, `optimizer-personality-regression-mac.txt`.
- Final local artifact integrity: all **298 listed files across 6 packages**
  (three original, three optimized) match their manifests;
  `scene-optimizer-local-artifact-check.json`.
- Skill frontmatter validation passed; zip integrity check passed.
- Production CLI inspection found no subprocess, network or shell execution.
  Tests use subprocess only to exercise this same CLI. This inspection is not a
  SkillSpector or independent security audit.

CPU tests include all three real scenes, preserve and preview outputs, relocation,
payload unload/reload, all-variant dependency inventory, selected-variant material
bindings/instancer array checks, bad hashes, missing textures, unsafe paths,
malformed requests/manifests and protected-state comparisons.
One fixture deliberately adds a collider to a far variant: the optimizer rejects
it and does not write a successful completion manifest.

## Observed Preview Results

The following counts agree between Mac USD 25.5.1 and Spark USD 0.24.5:

| Scene | Actual change | Structural before / after | Collider prims before / after |
| --- | --- | --- | --- |
| Meadow | 3 distant-from-camera near tiles switch to far | PI placements 42,327 / 37,647 | 84 / 84 |
| Space | 6 distant planets switch to far | Visible mesh points 109,949 / 71,878 | 9 / 9 |
| Moon | Explicit no-op; close-up terrain retained | PI placements 175,210 / 175,210 | 32 / 32 |

All composed protected-state checks passed, including collider shape attributes,
ancestor transforms, collision-instancer arrays, character, gravity, cameras and
lights. These checks do not prove dynamic physical contacts in Isaac Sim.

PI placements include physical and decorative instancers. Mesh-point counts expand
native instance proxies but do not multiply PI prototype geometry by placements.
They are not unique allocated geometry, GPU-memory consumption or rendered workload.

Output bytes excluding final manifest on Spark: meadow 37,071,086; space 16,069,251;
moon 147,844,977. The retained base means output is slightly larger than input on
disk. Small cross-runtime ASCII serialization differences do not alter the counts.
No disk-shrink or VRAM-saving claim is made.

## Known Warnings and Limits

- The negative missing-earth-texture test intentionally emits a dependency warning.
- Standalone CPU USD cannot resolve `OmniPBR.mdl` / `OmniGlass.mdl`. These exact
  built-in names are declared Isaac runtime requirements for the moon. Other missing
  dependencies fail. This run did not compile MDL or render the astronaut.
- Mac wheel emits the previously known cache-line-size warning and uses
  process-local `PXR_WORK_THREAD_LIMIT=1`; no global runtime changes were made.
- Static camera-distance overrides only, no runtime movement-aware LOD. All
  alternate variants remain available for the future Simulation Runner.
- GPU rendering, FPS/frame time, VRAM/shared-memory, load time, dynamic contact
  and live controls: **unmeasured / not tested** this run.
- No formal NVIDIA Usd Optimize processor, CUDA optimization, official signature,
  self-signature, independent review, SkillSpector scan or Agent A/B evaluation.
  This is development validation, not NVIDIA-Verified certification.
- Third-party provenance remains in the base package. No asset publication rights
  were inferred from free downloads, and no binary assets were put in the Skill zip.

## Reference

The override/payload approach follows existing project composition. General
performance guidance was checked against the official
[OpenUSD performance documentation](https://openusd.org/release/maxperf.html).
That documentation does not establish measured performance for these outputs.
