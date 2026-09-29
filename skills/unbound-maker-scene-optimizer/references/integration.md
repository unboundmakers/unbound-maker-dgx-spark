# Builder Agent / Simulation Runner Contract

Version 0.1.0, Python 3.10+, local trusted Scene Builder 0.1.0 outputs only.
No sibling Skill import is needed to execute this CLI. Tests require the three
previously built example packages; set `UNBOUND_SCENE_PACKAGES` to their parent.

## Input and Output

Request accepts only integer `schema_version: 1` and `profile: preserve|preview`.
Duplicate keys, unknown fields, unknown profiles, invalid manifests, changed files,
unlisted dependencies, path traversal, symlink files/directories and output reuse
are rejected. Validation may leave an incomplete new directory on failure; without
the final success manifest it is not a deliverable. Retry into a new directory.

Output:

```text
optimized.usda              stronger overrides, sublayers base/scene.usda
base/                      byte-identical complete input package
scene-config.json          original configuration plus entrypoint/base_package/profile
optimization-report.json   before/after counts, changes, preserved-state hash, limits
manifest.json              produced last, hashes of every other output file
```

The root remains `/World`, Z-up, meters. Absolute prim paths are unchanged.
Character runtime files are now under `base/character/`; the Runner must resolve
them relative to `base_package`, not to its current working directory. Original
source/license records remain under `base/sources.json` and nested source records.
Copy the entire output; entrypoint alone is insufficient.

## Preview Selection

- Meadow: only `/World/Environment/Environment/Tiles/*/Grass` detail selection,
  `near` to `far` when tile-center XY distance to `/World/PreviewCamera` exceeds 12 m.
  Existing `distant` remains distant. A tile spans an area: this is a tile-center
  heuristic, not guaranteed pixel/error tolerance along its edges.
- Space: only `/World/Environment/Planets/*/Visual`, `near` to `far` when distance
  to the original world-aligned visual bounding box exceeds 40 m. Existing geometry
  and material variants choose their authored resolution; textures are not rebaked.
- Moon: no changes. It has no supported visual detail variants in this adapter.

These are static startup choices. Retain near/far variant data in the package;
Runner must implement hysteresis and restore near detail as the player approaches.
No payload unload is authored, and no collidable tile is removed. Opening the USD
does not launch a game or apply renderer-settings JSON.

## Metrics and Proof

- Mesh-point count expands native instance proxies, excludes invisible meshes,
  but does not multiply PointInstancer prototypes by placement count. It is neither
  unique geometry memory nor rendered vertex/triangle workload.
- PointInstancer placements include visible/decorative and physical instancers,
  regardless of visibility/masking. It is not a PhysX shape count.
- Collider prim count expands native proxies but does not multiply PointInstancer
  prototypes. Equal count alone is insufficient; composed shape properties, their
  ancestor transforms and collision-bearing instancer arrays are also fingerprinted.
- Dependency enumeration includes alternate variants. All original variants stay
  available. Moon requires Isaac's `OmniPBR.mdl` and `OmniGlass.mdl`; they are not
  distributed in this package and CPU tests do not compile them.
- Input and output disk sizes do not promise a reduction: base files are retained
  for reversibility. GPU memory, frame time, load time and dynamic contacts remain
  unmeasured until a controlled test in the actual renderer.

Reject a nonzero CLI exit or absent/mismatched success manifest. No automatic
installation, paid asset download, public release, global environment change or
NVIDIA official signature is part of this interface.
