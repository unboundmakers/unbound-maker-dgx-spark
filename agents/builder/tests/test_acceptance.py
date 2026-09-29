from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from unbound_builder.config import canonical, normalize_design
from unbound_builder.skills import SkillExecutor, digest, validate_reports, lock, Busy, bundle
from unbound_builder.store import Store


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.store=Store(self.root/'state')

    def test_report_truth_types_and_identity(self):
        prepared={'job_id':'fresh'}; run={'status':'succeeded','job_id':'fresh','request_sha256':'sha','checks':{'a':True}}
        launch={'status':'succeeded','exit_code':0,'run_report_valid':True}
        validate_reports(prepared,run,launch,'sha')
        for changed in [dict(run,job_id='old'),dict(run,checks={'a':'false'}),dict(run,checks={}),dict(run,request_sha256='old')]:
            with self.assertRaises(ValueError): validate_reports(prepared,changed,launch,'sha')
        with self.assertRaises(ValueError): validate_reports(prepared,run,dict(launch,exit_code=1),'sha')

    def test_real_cache_lookup_and_tamper_refusal(self):
        skills=Path(__file__).parents[3]/'skills'
        executor=SkillExecutor({'skills_root':str(skills),'cpu_python':sys.executable},self.store)
        project=self.store.create_project({})
        job=self.store.enqueue(project['project_id'],project['revision_id'],'structured','cache')
        design=normalize_design({}); root=self.store.jobdir(job['job_id'])/'fixture'; root.mkdir()
        entry=root/'asset.usda'; entry.write_text('#usda 1.0')
        manifest={'status':'succeeded','skill':'unbound-maker-asset-builder','skill_version':'0.1.0','entrypoint':'asset.usda',
            'files':[{'path':'asset.usda','sha256':digest(entry),'bytes':entry.stat().st_size}]}
        (root/'manifest.json').write_text(canonical(manifest))
        self.store.cache_put(executor.cache_key('asset',design,{}),{'path':str(root),'manifest_sha':digest(root/'manifest.json')})
        with patch('unbound_builder.skills.run_process',side_effect=AssertionError('Cache must not execute')):
            self.assertTrue(executor.run_stage(job['job_id'],'asset',design,{})['reused'])
        entry.write_text('changed')
        with self.assertRaises(ValueError): executor.run_stage(job['job_id'],'asset',design,{})

    def test_exclusive_resource_lock(self):
        with lock(self.root/'exclusive'):
            with self.assertRaises(Busy):
                with lock(self.root/'exclusive'): pass

    def test_portable_bundle_contains_only_verified_inventory(self):
        root=self.root/'source'; root.mkdir(); (root/'entry.usda').write_text('#usda 1.0')
        (root/'secret').write_text('not part of asset')
        m={'status':'succeeded','skill':'test','skill_version':'0.1.0','entrypoint':'entry.usda',
           'files':[{'path':'entry.usda','bytes':9,'sha256':digest(root/'entry.usda')}]}
        (root/'manifest.json').write_text(canonical(m))
        bundle(root,self.root/'scene.zip','test',lambda:False)
        with zipfile.ZipFile(self.root/'scene.zip') as z:
            self.assertEqual(set(z.namelist()),{'manifest.json','entry.usda'})
