import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SKILL/'scripts'),str(SKILL/'runtime')]


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = Path(os.environ.get('UNBOUND_SCENE_PACKAGES',str(SKILL.parents[1]/'artifacts')))

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('simulation_runner'))
        import simulation_runner
        return simulation_runner

    def source(self, scene='space', optimized=False):
        p = self.artifacts/(('optimized-' if optimized else 'scene-')+scene+'-v0.1.0')
        self.assertTrue(p.is_dir())
        return p

    def test_defaults_and_experiment_contract(self):
        m = self.module()
        r = m.validate_request({'schema_version':1},'moon')
        self.assertEqual(r['duration_s'],10)
        self.assertEqual(r['environment'],'moon')
        self.assertEqual(r['gravity_m_s2'],1.62)
        self.assertEqual(m.validate_request({'schema_version':1,'environment':'earth'},'moon')['gravity_m_s2'],9.81)
        for patch in [{'schema_version':True},{'mass_kg':float('nan')},{'mass_kg':0},
                      {'thrust_n':51},{'duration_s':7},{'headless':'yes'},{'run_kind':'code'},
                      {'environment':[]},{'exec':'x'},{'session_seconds':99999}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                m.validate_request({'schema_version':1,**patch},'moon')
        with self.assertRaises(ValueError):
            m.validate_request({'schema_version':1,'environment':'moon'},'meadow')

    def test_capabilities_without_usd(self):
        self.module()
        p = subprocess.run([sys.executable,'-S',str(SKILL/'scripts/simulation_runner.py'),'capabilities'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['experiment_durations_s'],[5,10,20])

    def test_prepare_both_inputs_all_scenes_preserves_sources(self):
        m = self.module()
        for scene in ('meadow','space','moon'):
            for optimized in (False,True):
                with self.subTest(scene=scene,optimized=optimized):
                    source = self.source(scene,optimized)
                    old = m.digest(source/'manifest.json')
                    output = self.root/(scene+str(optimized))
                    job = m.prepare(source,{'schema_version':1},output)
                    self.assertEqual(job['status'],'prepared')
                    moved = self.root/(output.name+'-moved')
                    output.rename(moved)
                    m.verify_job(moved)
                    self.assertEqual(m.digest(source/'manifest.json'),old)
                    self.assertTrue((moved/job['scene_entry']).is_file())
                    self.assertTrue((moved/'runtime/isaac_runtime.py').is_file())

    def test_hash_and_output_reuse_rejected(self):
        m = self.module()
        out = self.root/'job'
        m.prepare(self.source(),{'schema_version':1},out)
        with self.assertRaises(ValueError):
            m.prepare(self.source(),{'schema_version':1},out)
        (out/'runtime/isaac_runtime.py').write_text('print("tampered")')
        with self.assertRaises(ValueError):
            m.verify_job(out)
        with self.assertRaises(ValueError):
            m.prepare(self.source(),{'schema_version':1},self.source()/'nested')

    def test_stop_is_job_local_and_prevents_launch(self):
        m = self.module()
        job = self.root/'job'
        m.prepare(self.source(),{'schema_version':1},job)
        m.request_stop(job)
        self.assertTrue((job/'STOP').is_file())
        self.assertEqual(m.status(job)['status'],'stop_requested')
        with self.assertRaises(ValueError):
            m.launch(job,Path(sys.executable),1)

    def test_fast_zero_exit_without_report_is_failure(self):
        m = self.module()
        job = self.root/'job'
        m.prepare(self.source(),{'schema_version':1},job)
        # /usr/bin/true ignores arguments: models Kit fastShutdown exit=0 with no report.
        result = m.launch(job,Path('/usr/bin/true'),2)
        self.assertEqual(result['status'],'failed')
        self.assertIn('report',result['error'].lower())
        with self.assertRaises(ValueError):
            m.launch(job,Path('/usr/bin/true'),2)

    def test_running_status_preserves_job_identity(self):
        m = self.module()
        job = self.root/'job'
        prepared = m.prepare(self.source(),{'schema_version':1},job)
        m.write(job/'state.json',{'status':'running','job_id':prepared['job_id']})
        self.assertEqual(m.status(job)['job_id'],prepared['job_id'])

    def test_timeout_terminates_only_owned_process(self):
        m = self.module()
        job = self.root/'job'
        m.prepare(self.source(),{'schema_version':1},job)
        result = m.launch(job,SKILL/'tests/fixtures/wait-runtime.sh',1)
        self.assertEqual(result['status'],'timed_out')
        self.assertLess(result['elapsed_wall_s'],8)
        pid = int((job/'child.pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid,0)

    def test_live_stop_exits_without_success_report(self):
        import threading
        import time
        m = self.module()
        job = self.root/'job'
        m.prepare(self.source(),{'schema_version':1},job)
        def stop_when_ready():
            for _ in range(100):
                if (job/'child.pid').exists():
                    m.request_stop(job)
                    return
                time.sleep(.05)
        thread = threading.Thread(target=stop_when_ready)
        thread.start()
        try:
            result = m.launch(job,SKILL/'tests/fixtures/wait-runtime.sh',15)
        finally:
            thread.join()
        self.assertEqual(result['status'],'stopped')
        self.assertFalse(result['run_report_valid'])

    def test_control_force_and_lod_hysteresis(self):
        self.module()
        from runner_core import control_force, detail_for
        from simulation_runner import validate_request
        r = validate_request({'schema_version':1},'meadow')
        force = control_force(r,{'UP','RIGHT','A'},(0,0,0))
        self.assertGreater(force[0],0); self.assertGreater(force[1],0)
        self.assertGreater(force[2],r['mass_kg']*r['gravity_m_s2'])
        self.assertLessEqual(math.hypot(*force[:2]),r['mass_kg']*14)
        self.assertEqual(detail_for('meadow',24,'near'),'near')
        self.assertEqual(detail_for('meadow',24,'far'),'far')
        self.assertEqual(detail_for('space',20,'far'),'near')
        moon = validate_request({'schema_version':1,'environment':'earth','thrust_n':0},'moon')
        self.assertEqual(control_force(moon,{'A'},(0,0,0))[2],0)
        space = validate_request({'schema_version':1},'space')
        self.assertLess(control_force(space,{'Z'},(0,0,0))[2],0)

    def test_raycast_object_and_dict_compatibility(self):
        self.module()
        from runner_core import hit_distance
        class Hit:
            rigid_body = '/World/Environment/Ground'
            collision = '/World/Environment/Ground/Collider'
            distance = 1.25
        self.assertEqual(hit_distance(Hit()),1.25)
        self.assertEqual(hit_distance({'rigidBody':'/World/Ground','distance':2}),2)
        self.assertIsNone(hit_distance({'rigidBody':'/World/Character','distance':.1}))
        Hit.rigid_body = '/World/Character'
        self.assertIsNone(hit_distance(Hit()))

    def test_frame_budget_matches_physics_ticks(self):
        self.module()
        from runner_core import FRAME_DT, PHYSICS_DT, frame_count
        for duration in (5,10,20):
            self.assertAlmostEqual(frame_count(duration)*FRAME_DT,duration)
            self.assertAlmostEqual(frame_count(duration)*FRAME_DT/PHYSICS_DT,duration*120)

    def test_runtime_edits_are_session_only_and_single_writer(self):
        self.module()
        from pxr import Usd, UsdGeom, UsdPhysics, UsdSkel
        from usd_runtime import configure_character, Motion, update_lod
        source = self.source('space',True)
        stage = Usd.Stage.Open(str(source/'optimized.usda'))
        before = stage.GetRootLayer().ExportToString()
        stage.SetEditTarget(stage.GetSessionLayer())
        c = configure_character(stage,2)
        self.assertTrue(stage.GetPrimAtPath('/World/Character').HasAPI(UsdPhysics.RigidBodyAPI))
        self.assertGreater(c['height'],0)
        self.assertTrue(UsdGeom.Camera.Get(stage,'/World/Character/RunnerCamera'))
        motion = Motion(stage)
        motion.controller.select('angry')
        motion.update((1,0,1),2,0,1/30)
        skeleton = motion.controller.skeleton
        targets = UsdSkel.BindingAPI(skeleton).GetAnimationSourceRel().GetTargets()
        self.assertEqual(len(targets),1)
        self.assertTrue(all(f.GetVisibilityAttr().Get()=='inherited' for f in motion.controller.fangs))
        motion.controller.select('natural')
        self.assertTrue(all(f.GetVisibilityAttr().Get()=='invisible' for f in motion.controller.fangs))
        before_collisions = sum(p.HasAPI(UsdPhysics.CollisionAPI) for p in stage.Traverse())
        self.assertGreater(update_lod(stage,'space',(0,80,25)),0)
        self.assertEqual(sum(p.HasAPI(UsdPhysics.CollisionAPI) for p in stage.Traverse()),before_collisions)
        self.assertEqual(stage.GetRootLayer().ExportToString(),before)


if __name__=='__main__':
    unittest.main()
