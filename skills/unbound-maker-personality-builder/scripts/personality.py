"""Manual expression state and a single-writer OpenUSD visual adapter."""
import math

FACE_JOINTS = ('head', 'face_lid_left', 'face_lid_right',
               'face_gaze_left', 'face_gaze_right', 'face_mouth')
EXPRESSIONS = ('natural', 'curious', 'angry')


def validate_profile(value):
    if not isinstance(value, dict) or set(value) - {'schema_version', 'adapter', 'default_expression'}:
        raise ValueError('Profile supports only schema_version, adapter and default_expression.')
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ValueError('schema_version must be integer 1.')
    if value.get('adapter') != 'flyingcat-v1':
        raise ValueError('Only the inspected flyingcat-v1 skeleton is supported.')
    if value.get('default_expression', 'natural') != 'natural':
        raise ValueError('This character must start natural; select other expressions manually at runtime.')
    return {'schema_version': 1, 'adapter': 'flyingcat-v1', 'default_expression': 'natural'}


class PersonalityState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.expression = 'natural'
        self.center()

    def center(self):
        self.yaw = self.tilt = 0.

    def select(self, name):
        if name not in EXPRESSIONS:
            raise ValueError('Select natural, curious or angry explicitly.')
        self.expression = name

    def turn(self, yaw=0., tilt=0.):
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (yaw, tilt)):
            raise ValueError('Head angles must be finite numbers, not booleans.')
        self.yaw = max(-35., min(35., self.yaw + yaw))
        self.tilt = max(-12., min(12., self.tilt + tilt))

    def pose(self):
        angles = {n: [0., 0., 0.] for n in FACE_JOINTS}
        offsets = {n: [0., 0., 0.] for n in FACE_JOINTS}
        scales = {n: [1., 1., 1.] for n in FACE_JOINTS}
        angles['head'] = [0., self.tilt, self.yaw]
        if self.expression == 'natural':
            for side in ('left', 'right'):
                offsets['face_lid_' + side][2] = .006
                scales['face_lid_' + side][2] = .65
            scales['face_mouth'] = [.9, 1., .55]
        elif self.expression == 'curious':
            offsets['face_lid_left'][2] = .017
            offsets['face_lid_right'][2] = .012
            for side in ('left', 'right'):
                offsets['face_gaze_' + side][0] = .004
                scales['face_lid_' + side][2] = .65
            scales['face_mouth'] = [.7, 1., .8]
        else:
            angles['face_lid_left'][1] = 14.
            angles['face_lid_right'][1] = -14.
            scales['face_mouth'] = [1.15, 1., 1.2]
        return dict(angles=angles, translations=offsets, scales=scales,
                    fangs=self.expression == 'angry')


def validate_joints(joints):
    names = [str(j).rsplit('/', 1)[-1] for j in joints]
    if len(names) != len(set(names)) or not set(FACE_JOINTS).issubset(names):
        raise ValueError('Missing or ambiguous face joints.')
    head = str(joints[names.index('head')])
    if any(not str(joints[names.index(n)]).startswith(head + '/') for n in FACE_JOINTS[1:]):
        raise ValueError('Face joints must be children of the head.')
    return names


def compose_pose(joints, translations, rotations, scales, state):
    """Compose onto an UNEXPRESSED body frame, returning fresh arrays, never writing USD."""
    from pxr import Gf, Vt
    names = validate_joints(joints)
    if any(len(a) != len(joints) for a in (translations, rotations, scales)):
        raise ValueError('All pose arrays must match the skeleton joint count.')
    for t, r, s in zip(translations, rotations, scales):
        values = [*t, *s, r.GetReal(), *r.GetImaginary()]
        if not all(math.isfinite(v) for v in values) or any(v <= 0 for v in s) or r.GetLength() < 1e-6:
            raise ValueError('Invalid joint transform.')
    t, r, s = Vt.Vec3fArray(translations), Vt.QuatfArray(rotations), Vt.Vec3hArray(scales)
    face = state.pose()
    for i, name in enumerate(names):
        if name not in FACE_JOINTS:
            continue
        x, y, z = face['angles'][name]
        delta = (Gf.Rotation(Gf.Vec3d(0, 0, 1), z).GetQuat() *
                 Gf.Rotation(Gf.Vec3d(0, 1, 0), y).GetQuat() *
                 Gf.Rotation(Gf.Vec3d(1, 0, 0), x).GetQuat())
        r[i] = r[i] * Gf.Quatf(delta)
        t[i] += Gf.Vec3f(*face['translations'][name])
        s[i] = Gf.Vec3h(*[s[i][k] * face['scales'][name][k] for k in range(3)])
    return t, r, s


def inspect_rig(stage, root_path):
    from pxr import Usd, UsdGeom, UsdSkel
    root = stage.GetPrimAtPath(root_path)
    if not root:
        raise ValueError('Character root does not exist.')
    skeletons = [UsdSkel.Skeleton(p) for p in Usd.PrimRange(root) if p.IsA(UsdSkel.Skeleton)]
    if len(skeletons) != 1:
        raise ValueError('Expected exactly one skeleton.')
    skeleton = skeletons[0]
    joints = skeleton.GetJointsAttr().Get()
    validate_joints(joints)
    fangs = [UsdGeom.Imageable(p) for p in Usd.PrimRange(root)
             if p.IsA(UsdGeom.Mesh) and p.GetName().startswith('Fang_')]
    if len(fangs) != 4:
        raise ValueError('Expected four fang meshes including outlines.')
    return skeleton, fangs


class PersonalityController:
    """Standalone preview writer. Hosts with gait should use compose_pose in their sole writer."""
    def __init__(self, stage, root_path, layer=None):
        from pxr import Usd, UsdSkel
        self.stage = stage
        self.layer = layer if layer is not None else stage.GetSessionLayer()
        self.skeleton, self.fangs = inspect_rig(stage, root_path)
        self.joints = self.skeleton.GetJointsAttr().Get()
        self.animation_path = stage.GetPrimAtPath(root_path).GetPath().AppendChild('PersonalityMotion')
        binding = UsdSkel.BindingAPI(self.skeleton.GetPrim())
        owners = binding.GetAnimationSourceRel().GetTargets()
        if owners and owners != [self.animation_path]:
            raise ValueError('Another animation owns this skeleton; use compose_pose in its final writer.')
        self.body_frame = UsdSkel.DecomposeTransforms(self.skeleton.GetRestTransformsAttr().Get())
        self.state = PersonalityState()
        with Usd.EditContext(stage, self.layer):
            self.animation = UsdSkel.Animation.Define(stage, self.animation_path)
            self.animation.CreateJointsAttr(self.joints)
            UsdSkel.BindingAPI.Apply(self.skeleton.GetPrim()).CreateAnimationSourceRel().SetTargets([self.animation_path])
        self.apply_frame(*self.body_frame)

    def apply_frame(self, translations, rotations, scales):
        from pxr import Usd, Vt
        frame = compose_pose(self.joints, translations, rotations, scales, self.state)
        self.body_frame = (Vt.Vec3fArray(translations), Vt.QuatfArray(rotations), Vt.Vec3hArray(scales))
        with Usd.EditContext(self.stage, self.layer):
            self.animation.CreateTranslationsAttr().Set(frame[0])
            self.animation.CreateRotationsAttr().Set(frame[1])
            self.animation.CreateScalesAttr().Set(frame[2])
            for fang in self.fangs:
                fang.CreateVisibilityAttr().Set('inherited' if self.state.pose()['fangs'] else 'invisible')

    def select(self, name):
        self.state.select(name)
        self.apply_frame(*self.body_frame)

    def turn(self, yaw=0., tilt=0.):
        self.state.turn(yaw, tilt)
        self.apply_frame(*self.body_frame)

    def center(self):
        self.state.center()
        self.apply_frame(*self.body_frame)

    def reset(self):
        self.state.reset()
        self.apply_frame(*self.body_frame)
