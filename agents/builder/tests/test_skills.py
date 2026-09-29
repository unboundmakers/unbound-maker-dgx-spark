import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unbound_builder.config import normalize_design, merge_design
from unbound_builder.store import Store
from unbound_builder.skills import SkillExecutor, inventory, digest, run_process, Cancelled

SKILLS = Path(__file__).resolve().parents[3]/'skills'


class Executors(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.s=Store(self.root/'state')
        self.e=SkillExecutor({'skills_root':str(SKILLS),'cpu_python':sys.executable,'isaac_python':sys.executable,
                              'assets_root':str(self.root),'cpu_env':{},'gpu_lock':str(self.root/'gpu.lock')},self.s)

    def test_fixed_commands_and_dependency_keys(self):
        d=normalize_design({'scene':{'scene_id':'moon'}})
        force=merge_design(d,{'simulation':{'thrust_n':11}})
        blue=merge_design(d,{'asset':{'body_color':'#2867D7'}})
        self.assertEqual(self.e.cache_key('asset',d,{}),self.e.cache_key('asset',force,{}))
        self.assertNotEqual(self.e.cache_key('asset',d,{}),self.e.cache_key('asset',blue,{}))
        inputs={'asset':{'manifest_sha':'a','path':'/trusted/a'}}
        other={'asset':{'manifest_sha':'b','path':'/trusted/a'}}
        self.assertNotEqual(self.e.cache_key('personality',d,inputs),self.e.cache_key('personality',d,other))
        with self.assertRaises(ValueError): self.e.command('shell',self.root,self.root,{},d)
        cmd=self.e.command('asset',self.root/'req',self.root/'out',{},d)
        self.assertEqual(cmd[0],sys.executable); self.assertIn('--request',cmd)
        self.assertNotIn('sh',cmd)

    def test_inventory_tampering_and_escape(self):
        self.root.joinpath('entry.usda').write_text('#usda 1.0')
        p=self.root/'entry.usda'
        m={'skill':'test','skill_version':'0.1.0','status':'succeeded','entrypoint':'entry.usda',
           'files':[{'path':'entry.usda','bytes':p.stat().st_size,'sha256':digest(p)}]}
        (self.root/'manifest.json').write_text(json.dumps(m))
        self.assertEqual(inventory(self.root,'test')['status'],'succeeded')
        p.write_text('tampered')
        with self.assertRaises(ValueError): inventory(self.root,'test')
        m['files'][0]['path']='../escape'
        (self.root/'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError): inventory(self.root,'test')

    def test_timeout_and_cancellation(self):
        t=time.monotonic()
        with self.assertRaises(TimeoutError):
            run_process([sys.executable,'-c','import time; time.sleep(30)'],self.root/'timeout.log',{},.2,lambda:False)
        self.assertLess(time.monotonic()-t,5)
        with self.assertRaises(Cancelled):
            run_process([sys.executable,'-c','import time; time.sleep(30)'],self.root/'cancel.log',{},2,lambda:True)

    def test_nonzero_exit_not_accepted(self):
        with self.assertRaises(RuntimeError):
            run_process([sys.executable,'-c','raise SystemExit(2)'],self.root/'fail.log',{},2,lambda:False)


if __name__=='__main__': unittest.main()
