# Optimization Recipes

Choose only techniques that address the measured bottleneck. Check APIs against the installed USD/Kit release before coding.

| Situation | Useful approach | Important boundary |
| --- | --- | --- |
| Repeated editable assets | References to a shared asset library | References alone do not guarantee shared runtime geometry. |
| Repeated identical hierarchies | Native `instanceable` instances | Descendant instance proxies cannot be individually edited normally; overrides/variants can split sharing. |
| Dense grass, pebbles or decorative scatter | `UsdGeomPointInstancer` with a small prototype set | Instances still incur rendering and potentially physics costs. Check target consumer support. |
| A small play area should feel spacious | Repeat compatible tiles; use simplified distant scenery | State actual play bounds. Do not call a backdrop an infinite world. |
| Geometry/detail too expensive at distance | LOD variants, density reduction, lower-detail prototypes | Author a runtime selector with hysteresis and a stable camera. Variants alone do not implement distance LOD. |
| Large portions unnecessary during play | Separate payloads and explicit load/unload policy | Payloads organize optional working sets; they do not automatically stream or unload. GPU resources may not be released immediately. |
| Texture-heavy assets | Share materials; reduce resolution by on-screen footprint | Inspect close views; keep correct UVs, color space and normal-map convention. File compression is not a GPU-memory metric. |
| Contact on overly complex meshes | Separate simple analytic/convex collision proxies | Validate shape error, transforms and contact behavior. Use triangle meshes only where supported and appropriate. |
| Too many expensive effects | Reduce unnecessary shadow, transparency or effect cost | Preserve agreed appearance; measure at fixed renderer settings. |

## Reusable Layout

An optional starting shape, not a required conversion:

```text
scene.usda                 # units, lighting, camera, composition
assets/library.usdc        # shared prototypes
assets/textures/            # relative texture paths
layers/near.usda            # interactive environment
layers/distant.usda         # simplified noninteractive backdrop
runtime/                   # explicit LOD/loading controller if needed
```

Keep authoring layers editable; use binary geometry layers where useful. Flattening is not a default optimization: it can discard useful composition boundaries and payload control.

## PCG and Materials

- Use a stored random seed and explicit bounds. Vary rotation, scale and a small number of material/prototype choices rather than making every object unique.
- Verify tile seam heights/normals, UV repetition, scatter clipping and travel corridors. Hide obvious repetition with restrained variation and distant silhouettes.
- Start with modest texture resolutions appropriate to screen coverage; 1K PBR and 2K HDRI worked for the small meadow, but are not universal limits.
- PBR is a material workflow, not a file extension. Check base color, roughness, metallic where relevant, normals and renderer-compatible shader bindings. Blender procedural nodes may require baking or conversion.
- Keep light contribution and camera-visible sky configurable separately; renderer-specific fog/background settings may not survive a USD-only export.

## LOD, Loading and Physics

Use separate enter/exit thresholds to avoid oscillation. Reevaluate at a bounded interval, not necessarily every frame. Preserve near-object identities where possible to reduce popping. Log variant/load transitions during tests.

Keep colliders stable beneath the player when visual detail changes. If physics tiles must unload, define a separate safety radius, retain occupied/contacting tiles, and validate before enabling this policy. Decorative grass/trees do not need collision unless the requested gameplay needs it.

For collision failures, compare a simple non-instanced shape with referenced and instanced variants in an isolated fixture. A raycast hit is not proof that a dynamic body contacts the surface. Do not mask tunneling by snapping the actor's transform to a computed height.

## Primary References

- [OpenUSD performance and working sets](https://openusd.org/release/maxperf.html)
- [Scenegraph instancing and editability](https://openusd.org/release/api/_usd__page__scenegraph_instancing.html)
- [PointInstancer](https://openusd.org/release/api/class_usd_geom_point_instancer.html)
- [Stage load rules and variant selections](https://openusd.org/release/api/class_usd_stage.html)

Read version-matched Isaac Sim documentation for consumer-specific rendering and physics behavior. These links explain USD mechanisms, not guaranteed Isaac Sim performance.
