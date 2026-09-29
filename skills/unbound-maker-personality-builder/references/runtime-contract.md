# Runtime Contract v0.1.0

## Input and Output

The only supported source is an intact Asset Builder 0.1.0 `flyingcat-v1` output. The source mesh hash is pinned in the builder; recolor and scale overrides are preserved. User-authored USD composition, other skeletons and modified source meshes are rejected. This is a compatibility boundary, not universal character generation.

Profile fields: integer `schema_version=1`, `adapter=flyingcat-v1`, optional `default_expression=natural`. Unknown fields, duplicate JSON keys, non-natural defaults and other adapters fail. Output must be a new directory under an existing parent.

Output contains `personality.usda`, `personality.json`, `runtime/personality.py`, `base/` (complete original package), `validation.json`, `manifest.json`. All USD references are relative. Runtime has no dependency on the Skill folder or source scene. `base/provenance.json` preserves character attribution and license status. Hashes detect changes, not authorship.

## State and Pose Composer (For Moving Hosts)

`PersonalityState()` starts natural, yaw 0, tilt 0. `select(name)` accepts natural/curious/angry. `turn(yaw, tilt)` adds degrees and clamps yaw to +/-35, tilt to +/-12. Invalid values reject atomically. These are visual design limits for this template, NOT robot motor safety limits. `center()` preserves expression, `reset()` returns natural and centers head.

`compose_pose(joints, translations, rotations, scales, state)` returns three fresh OpenUSD arrays. Input must be the current body frame BEFORE facial deltas; never feed back the previous composed frame. Pelvis, legs and tail are unchanged. Face offsets are local rig units and inherit the asset's outer scale. Yaw is local Z rotation; tilt is local Y rotation, following the existing rig adapter.

```python
from personality import PersonalityState, compose_pose

expression = PersonalityState()
# UI callbacks can call expression.select('curious'), expression.turn(5, 0), etc.
# In the host's existing final animation writer, every frame:
t, r, s = compose_pose(joints, body_t, body_r, body_s, expression)
animation.GetTranslationsAttr().Set(t)
animation.GetRotationsAttr().Set(r)
animation.GetScalesAttr().Set(s)
for fang in fang_meshes:
    fang.CreateVisibilityAttr().Set('inherited' if expression.pose()['fangs'] else 'invisible')
```

`fang_meshes` are UsdGeom.Imageable wrappers around the four `Fang_` meshes under this character; do not alter teeth belonging to other characters. The host owns input mapping and its full-body animation source. Remove the host's old facial-delta application when replacing it with this composer; otherwise expressions will be applied twice. Do not overwrite character_motion or apply transforms to the physics root.

## Standalone Preview Controller

```python
from personality import PersonalityController
controller = PersonalityController(stage, '/FlyingCat')
controller.select('curious')
controller.turn(yaw=15, tilt=4)
controller.center()
controller.reset()
```

The caller supplies an already loaded trusted stage and the character's actual prim path. Controller defaults to the stage's session layer, restoring the caller's edit target after each operation. It writes `PersonalityMotion` plus skeleton animation binding and fang visibility only. An existing different animation owner is rejected. Create only one controller per character. There is no timer, key capture or automatic emotion detection.

`apply_frame(t,r,s)` supplies a fresh full-body frame; selecting an expression or centering/resetting the head retains that frame. Constructor initially uses skeleton rest transforms and therefore is not a drop-in replacement for a live gait writer. For a character already driven by CharacterAnimation, use the composer path instead.

## Deployment and Verification

Build requires Python 3.10+ and compatible pxr. Tests additionally require the sibling Asset Builder skill to generate real input fixtures. The packaged runtime imports pxr only in USD methods; state and capabilities can run without it.

CPU tests cover real USD arrays, composed skeleton transforms and rigid skin bindings, not GPU appearance, rendered screenshots, widget interaction or physical dynamics. Safety boundary: this is a local file builder, not a sandbox against hostile native USD parser inputs; run only locally trusted packages in a restricted worker. No third-party scene is downloaded or executed.
