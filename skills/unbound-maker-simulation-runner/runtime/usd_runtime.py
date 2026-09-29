"""Session-layer adaptation of the existing flying-cat animation and scene LOD."""
import math
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, Vt
from personality import PersonalityController
from character_motion import MotionPlayer
from runner_core import detail_for


def configure_character(stage,mass):
    if stage.GetEditTarget().GetLayer()!=stage.GetSessionLayer():
        raise ValueError('Runtime edits must use the session layer.')
    actor = stage.GetPrimAtPath('/World/Character')
    visual = stage.GetPrimAtPath('/World/Character/Pose/Visual')
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render']).ComputeLocalBound(visual).ComputeAlignedRange()
    height = max(.5,float(bounds.GetSize()[2])*.55)
    radius = height*.18
    UsdPhysics.RigidBodyAPI.Apply(actor)
    UsdPhysics.MassAPI.Apply(actor).CreateMassAttr(mass)
    capsule = UsdGeom.Capsule.Define(stage,'/World/Character/RunnerCollider')
    capsule.CreateAxisAttr('Z')
    capsule.CreateRadiusAttr(radius)
    capsule.CreateHeightAttr(height-2*radius)
    capsule.AddTranslateOp().Set(Gf.Vec3d(0,0,height/2))
    capsule.CreateVisibilityAttr('invisible')
    UsdPhysics.CollisionAPI.Apply(capsule.GetPrim())
    camera = UsdGeom.Camera.Define(stage,'/World/Character/RunnerCamera')
    camera.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(3,-7,3),Gf.Vec3d(0,0,height*.6),Gf.Vec3d(0,0,1)).GetInverse())
    camera.CreateFocalLengthAttr(21)
    camera.CreateClippingRangeAttr(Gf.Vec2f(.05,12000))
    return {'height':height,'radius':radius}


class Motion:
    def __init__(self,stage):
        self.controller = PersonalityController(stage,'/World/Character/Pose/Visual')
        self.rest = self.controller.body_frame
        self.names = [str(j).rsplit('/',1)[-1] for j in self.controller.joints]
        self.player = MotionPlayer()

    def reset(self):
        self.player.reset()
        self.controller.reset()
        self.update((0,0,0),0,0,0)

    def update(self,velocity,clearance,yaw,dt):
        c,s = math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
        pose = self.player.update(c*velocity[0]+s*velocity[1],-s*velocity[0]+c*velocity[1],clearance,dt)
        t,r,scale = Vt.Vec3fArray(self.rest[0]),Vt.QuatfArray(self.rest[1]),Vt.Vec3hArray(self.rest[2])
        for i,name in enumerate(self.names):
            x,y,z = pose['angles'].get(name,(0,0,0))
            delta = Gf.Rotation(Gf.Vec3d(0,0,1),z).GetQuat()*Gf.Rotation(Gf.Vec3d(0,1,0),y).GetQuat()*Gf.Rotation(Gf.Vec3d(1,0,0),x).GetQuat()
            r[i] = r[i]*Gf.Quatf(delta)
            if name=='pelvis':
                t[i] += Gf.Vec3f(0,0,pose['bob'])
        self.controller.apply_frame(t,r,scale)
        return pose['state']


def update_lod(stage,scene,eye):
    cache = UsdGeom.XformCache()
    updates = []
    for p in stage.Traverse():
        path = str(p.GetPath())
        if scene=='meadow' and path.startswith('/World/Environment/Environment/Tiles/') and p.GetName()=='Grass':
            center = cache.GetLocalToWorldTransform(p).ExtractTranslation()
            distance = math.hypot(center[0]-eye[0],center[1]-eye[1])
        elif scene=='space' and path.startswith('/World/Environment/Planets/') and p.GetName()=='Visual':
            center = cache.GetLocalToWorldTransform(p).ExtractTranslation()
            distance = math.sqrt(sum((center[i]-eye[i])**2 for i in range(3)))
        else:
            continue
        variant = p.GetVariantSet('detail')
        old = variant.GetVariantSelection()
        new = detail_for(scene,distance,old)
        if new!=old and new in variant.GetVariantNames():
            updates.append((path,new))
    for path,new in updates:
        p = stage.GetPrimAtPath(path)
        p.GetVariantSet('detail').SetVariantSelection(new)
        if scene=='meadow':
            UsdGeom.Imageable(p).CreateVisibilityAttr('invisible' if new=='distant' else 'inherited')
    return len(updates)
