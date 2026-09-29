# Skill Card

Current source-candidate checks supersede the historical pending items below:
[release scope and limits](../../verification/release-20260929/README.md).
No full behavior verification or NVIDIA certification is claimed.

- Name/version: unbound-maker-personality-builder / 0.1.0 development.
- Owner: Unbound Maker project team. Original code: Apache-2.0; original Skill prose: CC BY 4.0. Character source assets excluded; see ../../LICENSING.md.
- Capability: manual head yaw/tilt and three expressions for the pinned flyingcat-v1 visual rig; portable USD overlay and Python runtime.
- Source: expression semantics adapted from the team's meadow-v0.3 character_expression.py and character_animation.py. Original scene files remain unchanged.
- Access: reads a local input package; writes a new output directory. No network, credentials, subprocess execution, model API, telemetry, GPU launch or global installation in production scripts.
- Limits: template-specific, no automatic emotions, motor commands, physical articulation, trained policy or generic mesh rigging. Native USD parsing is not a security sandbox.
- Verification: deterministic development tests; see BENCHMARK.md. Agent A/B, independent security scan, team signature, live rendering and formal release verification are separate pending gates.
- Trust: input/output SHA256 hashes establish integrity only. Not NVIDIA-certified or NVIDIA-signed.
