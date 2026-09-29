"""Bounded standalone Isaac runner. All scene mutations stay in the session layer."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback


def write(path,value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def run(job):
    data = json.loads((job/'job.json').read_text())
    request = json.loads((job/'request.json').read_text())
    config = json.loads((job/data['scene_config']).read_text())
    base = dict(job_id=data['job_id'],request_sha256=hashlib.sha256((job/'request.json').read_bytes()).hexdigest(),
                scene_id=request['scene_id'],request=request,trained_policy=False,keyboard_pipeline_tested=False)
    app = None
    input_api = keyboard = subscription = None
    started = time.monotonic()
    try:
        from isaacsim import SimulationApp
        app = SimulationApp({'headless':request['headless'],'width':960,'height':640,
            'renderer':'RayTracedLighting','anti_aliasing':3,
            'extra_args':['--/app/runLoops/main/rateLimitEnabled=true','--/app/runLoops/main/rateLimitFrequency=30']})
        import numpy as np
        import carb
        import carb.input
        import omni.appwindow
        import omni.usd
        import omni.physx
        from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdPhysics
        from isaacsim.core.api import World
        from isaacsim.core.prims import RigidPrim
        from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
        from runner_core import control_force, smoke_keys, hit_distance, FRAME_DT, PHYSICS_DT, frame_count
        from usd_runtime import configure_character, Motion, update_lod

        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        source_layer = Sdf.Layer.FindOrOpen(str(job/data['scene_entry']))
        if source_layer is None:
            raise RuntimeError('Failed to open scene source layer.')
        stage.GetRootLayer().subLayerPaths = [source_layer.identifier]
        stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
        UsdGeom.SetStageUpAxis(stage,'Z')
        UsdGeom.SetStageMetersPerUnit(stage,1.)
        for _ in range(20):
            app.update()
        stage = context.get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        original_layer_hash = hashlib.sha256(source_layer.ExportToString().encode()).hexdigest()
        shape = configure_character(stage,request['mass_kg'])
        physics = UsdPhysics.Scene.Get(stage,'/World/Physics')
        physics.CreateGravityDirectionAttr(Gf.Vec3f(0,0,-1))
        physics.CreateGravityMagnitudeAttr(request['gravity_m_s2'])
        scene_api = PhysxSchema.PhysxSceneAPI.Apply(physics.GetPrim())
        scene_api.CreateEnableGPUDynamicsAttr(False)
        scene_api.CreateBroadphaseTypeAttr('MBP')
        scene_api.CreateEnableCCDAttr(True)
        body = stage.GetPrimAtPath('/World/Character')
        body_api = PhysxSchema.PhysxRigidBodyAPI.Apply(body)
        body_api.CreateEnableCCDAttr(True)
        body.CreateAttribute('physxRigidBody:lockedRotAxis',Sdf.ValueTypeNames.Int).Set(7)
        world = World(stage_units_in_meters=1.,physics_dt=PHYSICS_DT,rendering_dt=FRAME_DT,
                      physics_prim_path='/World/Physics',set_defaults=False)
        rigid = world.scene.add(RigidPrim(prim_paths_expr='/World/Character',name='runner-character'))
        motion = Motion(stage)
        pose = UsdGeom.Xformable(stage.GetPrimAtPath('/World/Character/Pose'))
        pitch_op = pose.AddRotateXOp(opSuffix='runnerFlight')
        settings = carb.settings.get_settings()
        allowed_settings = {'/rtx/background/source/type','/rtx/background/source/color','/rtx/fog/enabled',
            '/rtx/fog/fogColor','/rtx/fog/fogColorIntensity','/rtx/fog/fogHeightDensity',
            '/rtx/fog/fogStartDist','/rtx/fog/fogEndDist','/rtx/fog/fogDistanceDensity'}
        for key,value in config.get('renderer_settings',{}).items():
            if key in allowed_settings:
                settings.set(key,value)
        viewport = get_active_viewport()
        if viewport is None:
            raise RuntimeError('No viewport available for evidence capture.')
        previous_camera = str(viewport.camera_path)
        previous_prim = stage.GetPrimAtPath(previous_camera)
        previous_transform = str(UsdGeom.Xformable(previous_prim).GetLocalTransformation()) if previous_prim else None
        follow = '/World/Character/RunnerCamera'
        viewport.camera_path = follow
        for _ in range(30):
            app.update()
        world.reset()
        spawn = np.array([config['spawn_world']],dtype=np.float32)
        spawn[0,2] += .15 if request['scene_id']!='space' else 0
        heading = math.radians(config['request'].get('heading_degrees',0))/2
        orientation = np.array([[math.cos(heading),0,0,math.sin(heading)]],dtype=np.float32)
        held = set()
        pending = {'reset':False,'quit':False,'camera':False}
        trial_time = 0.
        pitch = 0.
        physics_ticks = 0
        lod_changes = 0
        resets = 0
        query = omni.physx.get_physx_scene_query_interface()

        def reset():
            nonlocal trial_time,pitch,resets
            held.clear()
            rigid.set_world_poses(positions=spawn,orientations=orientation)
            rigid.set_velocities(np.zeros((1,6),dtype=np.float32))
            motion.reset()
            pitch = trial_time = 0.
            pitch_op.Set(0.)
            resets += 1

        def clearance_at(position):
            if request['scene_id']=='space':
                return 2.
            hits = []
            def hit_callback(hit):
                distance = hit_distance(hit)
                if distance is not None:
                    hits.append(distance)
                return True
            query.raycast_all(tuple(float(v) for v in (position+np.array([0,0,.05]))),(0.,0.,-1.),5000.,hit_callback)
            return max(0.,min(hits)-.05) if hits else 1000.

        def force_tick(dt):
            nonlocal physics_ticks
            velocity = rigid.get_velocities()[0][:3]
            rigid.apply_forces(np.array([control_force(request,held,velocity)],dtype=np.float32))
            physics_ticks += 1

        reset()
        world.add_physics_callback('unbound-runner-force',force_tick)

        def key_event(event,*unused):
            name = getattr(event.input,'name',str(event.input))
            if event.type==carb.input.KeyboardEventType.KEY_PRESS:
                if name=='R': pending['reset']=True
                elif name=='ESCAPE': pending['quit']=True
                elif name=='C': pending['camera']=True
            return name not in {'UP','DOWN','LEFT','RIGHT','A','Z','R','C','SPACE'}

        label = None
        if not request['headless']:
            import omni.ui as ui
            input_api = carb.input.acquire_input_interface()
            keyboard = omni.appwindow.get_default_app_window().get_keyboard()
            subscription = input_api.subscribe_to_keyboard_events(keyboard,key_event)
            hud = ui.Window('Unbound Maker | '+request['scene_id'],width=390,height=310)
            with hud.frame:
                with ui.VStack(spacing=7,style={'margin':12,'font_size':17,'color':0xffeeeeee,'background_color':0xff343434}):
                    ui.Label('ARROWS move | A lift | Z descend (space)')
                    ui.Label('R reset | C switch camera | Esc stop')
                    ui.Label('Gravity %.2f m/s2 | Mass %.1f kg | Thrust %.1f N' % (request['gravity_m_s2'],request['mass_kg'],request['thrust_n']))
                    with ui.HStack(spacing=5):
                        for expression in ('natural','curious','angry'):
                            ui.Button(expression.title(),clicked_fn=lambda e=expression:motion.controller.select(e),style={'background_color':0xffc67a32})
                    with ui.HStack(spacing=5):
                        ui.Button('Look left',clicked_fn=lambda:motion.controller.turn(10,0))
                        ui.Button('Look right',clicked_fn=lambda:motion.controller.turn(-10,0))
                        ui.Button('Tilt',clicked_fn=lambda:motion.controller.turn(0,4))
                        ui.Button('Center',clicked_fn=motion.controller.center)
                    ui.Button('Reset / Start trial',clicked_fn=lambda:pending.update(reset=True),style={'background_color':0xff3261d9})
                    label = ui.Label('Click viewport to use keyboard.',word_wrap=True)
                    if request['warnings']:
                        ui.Label('\n'.join(request['warnings']),word_wrap=True)

        write(job/'state.json',{'status':'running','updated_at':time.time(),'job_id':data['job_id']})
        print('UNBOUND_RUNNER_READY',data['job_id'],flush=True)
        trace = []
        dt = FRAME_DT
        limit = request['duration_s'] if request['run_kind']=='smoke' else request['session_seconds']
        total = frame_count(limit)
        outcome = 'succeeded'
        run_started = time.monotonic()
        captured = False
        frame = 0
        for step in range(total):
            if not app.is_running() or pending['quit'] or (job/'STOP').exists():
                outcome = 'stopped'
                break
            t = step*dt
            if pending['reset']:
                reset(); pending['reset']=False
            if pending['camera']:
                viewport.camera_path = config['preview_camera'] if str(viewport.camera_path)==follow else follow
                pending['camera']=False
            held.clear()
            if request['run_kind']=='smoke':
                held.update(smoke_keys(t,limit))
            elif keyboard is not None:
                for key in ('UP','DOWN','LEFT','RIGHT','A','Z','SPACE'):
                    if input_api.get_keyboard_value(keyboard,getattr(carb.input.KeyboardInput,key))>0:
                        held.add(key)
                if request['scene_id']=='moon' and trial_time>=request['duration_s']:
                    held.clear()
            if not world.is_playing():
                held.clear()
                raise RuntimeError('Timeline paused externally. Prepare a fresh run instead of advancing a stopped simulation.')
            # One rendered World.step advances FRAME_DT / PHYSICS_DT substeps.
            world.step(render=True)
            trial_time += dt
            position = rigid.get_world_poses()[0][0]
            velocity = rigid.get_velocities()[0][:3]
            if not np.all(np.isfinite(position)) or not np.all(np.isfinite(velocity)):
                raise RuntimeError('Nonfinite physics state.')
            boundary = {'meadow':69.,'moon':175.,'space':500.}[request['scene_id']]
            if max(abs(float(position[0])),abs(float(position[1])))>boundary or position[2]<-100:
                if request['run_kind']=='smoke':
                    raise RuntimeError('Smoke trajectory left supported bounds.')
                reset()
            clearance = clearance_at(position)
            motion_state = motion.update(velocity,clearance,config['request'].get('heading_degrees',0),dt)
            target_pitch = 82*min(1.,max(0.,(clearance-.12)/.75))
            pitch += (target_pitch-pitch)*(1-math.exp(-dt*7))
            pitch_op.Set(pitch)
            trace.append([round(t,4),*map(float,position),*map(float,velocity),clearance])
            frame += 1
            if step%15==0:
                active = stage.GetPrimAtPath(str(viewport.camera_path))
                eye = UsdGeom.XformCache().GetLocalToWorldTransform(active).ExtractTranslation()
                lod_changes += update_lod(stage,request['scene_id'],eye)
                write(job/'state.json',{'status':'running','updated_at':time.time(),'sim_time_s':round(t,2)})
                if label:
                    label.text = 'Time %.1f / %.1f s | Height %.2f m\n%s | LOD changes %d%s' % (
                        trial_time,request['duration_s'] if request['scene_id']=='moon' else limit,clearance,motion_state,lod_changes,
                        '\nTrial finished. R starts again.' if request['scene_id']=='moon' and trial_time>=request['duration_s'] else '')
            if not captured and t>=limit*.45:
                capture_viewport_to_file(viewport,str(job/'preview.png'))
                captured = True
            if request['run_kind']=='interactive':
                time.sleep(max(0.,frame/30-(time.monotonic()-run_started)))
        held.clear()
        p_before_reset = rigid.get_world_poses()[0][0].copy()
        reset()
        reset_ok = bool(np.linalg.norm(rigid.get_world_poses()[0][0]-spawn[0])<.01)
        world.stop()
        for _ in range(15):
            if app.is_running(): app.update()
        values = np.asarray(trace)
        checks = dict(finite_trajectory=bool(len(trace) and np.all(np.isfinite(values))),
            force_callback_ran=physics_ticks>0,reset_returns_to_spawn=reset_ok,
            gravity_matches_request=abs(physics.GetGravityMagnitudeAttr().Get()-request['gravity_m_s2'])<1e-5,
            source_root_layer_unchanged=hashlib.sha256(source_layer.ExportToString().encode()).hexdigest()==original_layer_hash,
            preview_image_written=(job/'preview.png').is_file() and (job/'preview.png').stat().st_size>1000)
        if previous_prim and previous_transform is not None:
            checks['previous_camera_transform_unchanged'] = str(UsdGeom.Xformable(previous_prim).GetLocalTransformation())==previous_transform
        if request['run_kind']=='smoke' and outcome=='succeeded':
            checks['physics_duration_matches_request'] = abs(physics_ticks*PHYSICS_DT-limit)<PHYSICS_DT*2
            settled = values[(values[:,0]>=limit*.1)&(values[:,0]<limit*.2)]
            flying = values[(values[:,0]>=limit*.35)&(values[:,0]<limit*.5)]
            checks['horizontal_input_moves_actor'] = float(np.max(values[:,1])-np.min(values[:,1]))>.25
            if request['thrust_n']>request['mass_kg']*request['gravity_m_s2'] or request['scene_id']=='space':
                checks['lift_moves_actor_up'] = bool(len(flying) and len(settled) and np.max(flying[:,3])>np.mean(settled[:,3])+.15)
            if request['scene_id']!='space':
                checks['spawn_contacts_ground'] = bool(len(settled) and np.max(np.abs(settled[:,3]-config['spawn_world'][2]))<.25)
        if outcome=='succeeded' and not all(checks.values()):
            outcome='failed'
        write(job/'trajectory.json',trace)
        report = dict(base,status=outcome,checks=checks,simulated_s=round(physics_ticks*PHYSICS_DT,3),
            physics_ticks=physics_ticks,lod_changes=lod_changes,final_before_reset=list(map(float,p_before_reset)),
            runtime_wall_s=round(time.monotonic()-started,3),gravity_m_s2=request['gravity_m_s2'],
            scope='Capsule force control and visual skeleton animation; no articulated balance or aerodynamic model.',
            gpu_memory='unmeasured',all_rocks_contact_tested=False,manual_ui_tested=False)
        write(job/'run-report.json',report)
        write(job/'state.json',{'status':outcome,'updated_at':time.time()})
        print('UNBOUND_RUNNER_RESULT',json.dumps(report),flush=True)
        return 0 if outcome in ('succeeded','stopped') else 2
    except BaseException as exc:
        traceback.print_exc()
        write(job/'run-report.json',dict(base,status='failed',error=str(exc),traceback=traceback.format_exc()))
        write(job/'state.json',{'status':'failed','updated_at':time.time()})
        return 2
    finally:
        if subscription is not None:
            input_api.unsubscribe_to_keyboard_events(keyboard,subscription)
        if app is not None:
            app.close()


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job',required=True,type=Path)
    args = parser.parse_args()
    sys.argv = [sys.argv[0]]
    sys.exit(run(args.job.resolve()))
