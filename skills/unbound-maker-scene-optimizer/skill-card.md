# Skill Card

Current source-candidate checks supersede the historical pending items below:
[release scope and limits](../../verification/release-20260929/README.md).
No full behavior verification or NVIDIA certification is claimed.

- Owner: Unbound Maker project team.
- Version: 0.1.0 development package.
- Capability: CPU audit and reversible static visual-LOD overrides for trusted
  Scene Builder 0.1.0 grass, solar-system and lunar packages.
- Permissions: read input files, write one new output directory. No network or
  subprocess execution in production CLI; no GPU launch or global install.
- Trust: USD files are local trusted inputs. Hashes are integrity checks, not
  digital signatures, security scanning or proof of asset ownership.
- Evidence: see BENCHMARK.md and repository verification report for executed tests.
- Review: author review only; no independent review or Agent A/B run claimed.
- Limits: static selection, no texture/mesh regeneration, collision simplification,
  dynamic LOD, formal NVIDIA optimizer, rendering validation or measured GPU gain.
- Assets: no third-party models/textures included in the Skill. Scene output retains
  their source records and remains subject to their individual usage restrictions.
- Status: not NVIDIA-Verified; no official signature, self-signed attestation or
  SkillSpector scan has been produced by this development package.
