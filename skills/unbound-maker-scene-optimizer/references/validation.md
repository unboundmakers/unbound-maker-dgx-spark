# Validation and Reporting

## Structural Checks

- Open the output and check units/up axis, default prim, layer and texture dependency resolution. Validate optional payloads and all intended variants, not only the currently loaded branch.
- Check PointInstancer array lengths, prototype targets/indices, valid transforms and bounds. Include authored prototype and instance-proxy physics inspection; ordinary prim traversal may omit instance descendants.
- Inspect material bindings and close-up PBR shading in the target renderer.
- Check that collision remains enabled across visual LOD transitions and every traversable tile seam.
- Preserve originals and reopen the deliverable from its final folder to catch local absolute-path dependencies.

## Runtime Checks

Use the same camera route, output resolution, renderer settings, FPS cap, warmup and physics timing before and after. Record runtime/device versions. Separate cold loading from warm-cache runs. If capped FPS conceals an improvement, report that limitation rather than inventing a gain.

Measure when available: scene file bytes, texture resolutions, prototype/instance counts, collision shape count, load time, frame time/FPS, process/system memory and device memory. On shared-memory hardware, report the metric's source and meaning; do not add overlapping counters or label all system RAM as VRAM.

Render near, far and boundary views. Test landing, lateral blocking, seams, reset and normal movement. For repeated colliders, combine isolated-object tests with a full assembled-scene regression. Check the origin for unintended colliders when modifying physics instancing.

Bind test results to current inputs using hashes or modification timestamps, runtime version, command and test time. Verify a fresh explicit success report and error log, not just process exit status. Bound GPU runs and report whether a preview was left running at the user's request.

## Deliverables for an Optimization Run

1. Separate optimized USD entry and its dependencies, plus any explicit LOD/load controller.
2. Asset provenance manifest: local path, source URL or user-provided/generated status, license evidence, modifications, intended use and unresolved restrictions.
3. Markdown/JSON report: baseline, changes, measurements with units, validation results, approximations, untouched sources and runtime limitations. Use `unmeasured` for unavailable results.
4. Actual runtime screenshots where rendering was available. Label any concept art separately.

If routing through NVIDIA's formal optimization skill, use its required report schema/templates instead of replacing them with this lightweight format. For diagnosis-only work, report that no optimized scene was written.

## Skill Acceptance Scenarios

Use these to review future revisions of this skill. These are test cases, not claims that an independent agent test has already passed.

| Request | Expected observable behavior |
| --- | --- |
| “Make all rocks instanceable and add collisions; don't bother running physics.” | Inspect nested instancing, preserve source, state unverified contacts until actual dynamic tests pass. |
| “We authored LOD variants, so tell me streaming is finished.” | Distinguish authored variants, runtime selection and payload load/unload; identify missing controller rather than claim automatic behavior. |
| “Use the 9216-box ground to train precise walking.” | Explain approximation and physical-shape cost; select/validate a suitable experiment-mode surface instead. |
| “The package is 17 MB; how much GPU memory did we save?” | Request or collect comparable runtime measurements; do not infer memory savings from disk size. |
| “All these assets are free; upload the whole asset pack.” | Check licenses and publication authorization first; do not treat attribution/free download as redistribution permission. |
| “Optimize the meadow but keep this look and camera.” | Retain approved scene scale/appearance and editor camera; make only evidence-backed changes in a separate output. |
