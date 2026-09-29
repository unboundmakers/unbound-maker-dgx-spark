"""Visual animation only: no joint forces, balance controller or learned policy."""
import math

JOINTS = ('pelvis', 'left_thigh', 'left_shin', 'left_foot',
          'right_thigh', 'right_shin', 'right_foot', 'tail')


def motion_pose(vx, vy, clearance, phase):
    angles = {name: [0., 0., 0.] for name in JOINTS}
    lifts = {'left': 0., 'right': 0.}
    state = 'idle'
    bob = .002 * math.sin(phase * math.tau)
    if clearance > .18:
        state, bob = 'fly', 0.
        for side in lifts:
            angles[side + '_thigh'][0] = -22
            angles[side + '_shin'][0] = 55
            angles[side + '_foot'][0] = -18
    elif math.hypot(vx, vy) > .08:
        strength = min(1., math.hypot(vx, vy) / .5)
        if abs(vx) > abs(vy) * 1.2:
            state = 'side_right' if vx > 0 else 'side_left'
            lead, follow = ('left', 'right') if vx > 0 else ('right', 'left')
            direction = 1 if vx > 0 else -1
            # First half: lead foot opens. Second half: trailing foot gathers.
            for side, offset in ((lead, 0.), (follow, .5)):
                p = (phase - offset) % 1.
                lift = max(0., math.sin(math.tau * p))
                lifts[side] = lift
                spread = 18 * math.sin(math.pi * phase) ** 2
                side_sign = 1 if side == 'left' else -1
                angles[side + '_thigh'] = [-10 * lift, 0., -side_sign * spread]
                angles[side + '_shin'][0] = 27 * lift
                angles[side + '_foot'] = [-17 * lift, 0., -angles[side + '_thigh'][2]]
        else:
            state = 'forward' if vy < 0 else 'backward'
            direction = 1 if vy < 0 else -1
            for side, offset in (('left', 0.), ('right', .5)):
                p = (phase + offset) % 1.
                lift = max(0., math.sin(math.tau * p))
                lifts[side] = lift
                swing = -direction * 24 * math.sin(math.tau * p)
                angles[side + '_thigh'][0] = swing
                angles[side + '_shin'][0] = 32 * lift
                angles[side + '_foot'][0] = -swing - 25 * lift
        for name in angles:
            angles[name] = [a * strength for a in angles[name]]
        bob = .007 * strength * (1 - math.cos(phase * 2 * math.tau))
    # Tail has its own pivot: hang behind the hips on land, trail in flight.
    wave = math.sin(phase * math.tau)
    angles['tail'] = ([4*wave, 10+3*wave, 65+5*wave] if state == 'fly'
                      else [0., 80., 3*wave])
    return dict(state=state, angles=angles, lifts=lifts, bob=bob)


class MotionPlayer:
    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = 0.
        self.pose = motion_pose(0, 0, 0, 0)

    def update(self, vx, vy, clearance, dt):
        speed = math.hypot(vx, vy)
        rate = .5 if speed < .08 else min(3.5, max(.8, speed / .30))
        self.phase = (self.phase + max(0., dt) * rate) % 1.
        target = motion_pose(vx, vy, clearance, self.phase)
        alpha = 1 - math.exp(-max(0., dt) * 14)
        angles = {name: [a + (b-a)*alpha for a, b in zip(self.pose['angles'][name], target['angles'][name])]
                  for name in JOINTS}
        target['angles'] = angles
        target['bob'] = self.pose['bob'] + (target['bob']-self.pose['bob'])*alpha
        self.pose = target
        return target
