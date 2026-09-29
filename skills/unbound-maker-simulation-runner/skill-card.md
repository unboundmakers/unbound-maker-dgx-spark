# Skill Card

Current source-candidate checks supersede the historical pending items below:
[release scope and limits](../../verification/release-20260929/README.md).
Runner prompt-retest service failures remain recorded; no full behavior
verification or NVIDIA certification is claimed.

- Owner: Unbound Maker team; version 0.1.0 development.
- Purpose: prepare, supervise and inspect bounded Isaac scene previews.
- Permissions: read trusted scene packages; write one job; execute explicitly
  supplied installed Isaac Python; stop only that launcher's process group.
- Output: immutable job inventory plus fresh logs, checks, trajectory and image.
- Trust: local USD and runtime installation are trusted. SHA256 is not signing.
- Side effects: Isaac may write its normal user cache/logs; renderer uses GPU.
- Boundaries: no model installation, training, automatic emotions, frontend server,
  remote streaming, asset publication or global environment modification.
- Test status: see repository verification report; scripted input is not manual
  keyboard/UI verification, contact checks do not cover every environmental object.
- Governance: development validation, not NVIDIA-Verified; no official signature,
  SkillSpector scan or independent Agent A/B result is claimed.
