import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unbound_builder.config import normalize_design, merge_design
from unbound_builder.store import Store, Conflict


class Contracts(unittest.TestCase):
    def test_defaults_and_ranges(self):
        d = normalize_design({'scene': {'scene_id': 'moon'}})
        self.assertEqual([d['simulation'][k] for k in ('mass_kg','thrust_n','duration_s')], [2,7,10])
        self.assertEqual(d['personality']['default_expression'], 'natural')
        self.assertEqual(d['scene']['mode'], 'experiment')
        for v in ({'asset': {'scale': True}}, {'asset': {'scale': float('nan')}},
                  {'simulation': {'environment': 'earth'}}, {'code_stub': 'touch x'},
                  {'asset': {'path': '/tmp/a'}}, {'personality': {'default_expression': 'angry'}}):
            with self.subTest(v=v), self.assertRaises(ValueError): normalize_design(v)

    def test_patch_preserves_old_and_rejects_unknown(self):
        a = normalize_design({})
        b = merge_design(a, {'asset': {'body_color': '#123456'}})
        self.assertNotIn('body_color', a['asset'])
        self.assertEqual(b['asset']['body_color'], '#123456')
        with self.assertRaises(ValueError): merge_design(a, {'shell': 'echo hi'})

    def test_scene_change_clears_only_implicit_old_physics(self):
        a = normalize_design({'scene': {'scene_id':'moon'}})
        b = merge_design(a, {'scene': {'scene_id':'space'}})
        self.assertNotIn('mass_kg', b['simulation'])
        self.assertEqual(b['scene']['mode'], 'story')


class Storage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name))
        self.p = self.s.create_project({})

    def test_revision_conflict_and_immutable_parent(self):
        r = self.s.revise(self.p['project_id'], self.p['revision_id'], {'asset':{'scale':1.5}})
        self.assertEqual(self.s.revision(self.p['revision_id'])['design']['asset']['scale'], 1)
        self.assertEqual(r['design']['asset']['scale'],1.5)
        with self.assertRaises(Conflict): self.s.revise(self.p['project_id'],self.p['revision_id'],{})

    def test_idempotency_and_cancel(self):
        args = (self.p['project_id'],self.p['revision_id'],'structured','request-1')
        j = self.s.enqueue(*args)
        self.assertEqual(self.s.enqueue(*args)['job_id'],j['job_id'])
        with self.assertRaises(Conflict): self.s.enqueue(*args[:-2],'agent','request-1',instruction='hello')
        self.s.cancel(j['job_id'])
        self.assertEqual(self.s.get_job(j['job_id'])['status'],'cancelled')
        self.assertIsNone(self.s.claim())

    def test_recovery_and_path_registry(self):
        j = self.s.enqueue(self.p['project_id'],self.p['revision_id'],'structured','r')
        self.s.claim(); self.s.recover()
        self.assertEqual(self.s.get_job(j['job_id'])['status'],'interrupted')
        with self.assertRaises(ValueError): self.s.register_artifact(j['job_id'],Path('/etc/hosts'))
        with self.assertRaises(ValueError): self.s.get_job('../../etc')


if __name__ == '__main__': unittest.main()
