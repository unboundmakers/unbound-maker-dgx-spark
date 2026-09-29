"""Pure control laws and LOD policy; SI units, no trained gait or aerodynamics."""
import math

FRAME_DT = 1/30
PHYSICS_DT = 1/120


def frame_count(duration):
    return round(duration/FRAME_DT)


def hit_distance(hit):
    if isinstance(hit,dict):
        body,collision,distance = hit.get('rigidBody',''),hit.get('collision',''),hit['distance']
    else:
        body,collision,distance = hit.rigid_body,hit.collision,hit.distance
    if str(body).startswith('/World/Character') or str(collision).startswith('/World/Character'):
        return None
    return float(distance)


def detail_for(scene,distance,current):
    if scene=='space':
        return 'far' if distance>(120 if current=='near' else 90) else 'near'
    if distance<21:
        return 'near'
    if distance>52 or (current=='distant' and distance>=42):
        return 'distant'
    if distance>27 or current=='distant':
        return 'far'
    return current


def control_force(request,held,velocity):
    mass,speed = request['mass_kg'],request['speed_m_s']
    x,y = int('RIGHT' in held)-int('LEFT' in held),int('UP' in held)-int('DOWN' in held)
    if request['scene_id']=='space':
        z = int('A' in held)-int('Z' in held)
        norm = max(1.,math.sqrt(x*x+y*y+z*z))
        target = (0,0,0) if 'SPACE' in held else (speed*x/norm,speed*y/norm,speed*z/norm)
        acceleration = [(7 if 'SPACE' in held else 3)*(a-b) for a,b in zip(target,velocity)]
        divisor = max(1.,math.sqrt(sum(v*v for v in acceleration))/12)
        return tuple(mass*v/divisor for v in acceleration)
    norm = max(1.,math.hypot(x,y))
    ax,ay = 4*(speed*x/norm-velocity[0]),4*(speed*y/norm-velocity[1])
    divisor = max(1.,math.hypot(ax,ay)/14.)
    lift = request['thrust_n'] if 'A' in held else 0.
    return mass*ax/divisor,mass*ay/divisor,lift-mass*1.5*velocity[2]


def smoke_keys(t,duration):
    q = t/duration
    if .2<=q<.5:
        return {'A','RIGHT'}
    if .5<=q<.65:
        return {'UP'}
    if .65<=q<.8:
        return {'LEFT'}
    return set()
