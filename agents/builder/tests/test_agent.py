import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from unbound_builder.agent import BuilderAgent
from unbound_builder.model import ModelClient, ModelUnavailable
from unbound_builder.store import Store
from unbound_builder.config import STAGES


def call(name,**args): return {'name':name,'arguments':args}


class MockModel:
    identity={'execution_mode':'mock','model':'test-fixture'}
    def __init__(self,actions): self.actions=iter(actions)
    def complete(self,messages,tools): return next(self.actions)


class MockSkills:
    def __init__(self): self.calls=[]
    def run_stage(self,j,s,d,inputs):
        self.calls.append((s,d))
        return {'stage':s,'reused':False,'checks':{'fixture':True}}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=Store(self.tmp.name); p=self.store.create_project({})
        self.job=self.store.enqueue(p['project_id'],p['revision_id'],'agent','first','Blue cat on moon')
        self.skills=MockSkills()

    def agent(self,actions): return BuilderAgent(self.store,self.skills,MockModel(actions))

    def test_model_directed_chain_is_explicit_mock(self):
        actions=[call('configure',patch={'scene':{'scene_id':'moon'},'asset':{'body_color':'#2867D7'}})]
        actions += [call('run_stage',stage=s) for s in STAGES]+[call('finish')]
        result=self.agent(actions).run(self.job)
        self.assertEqual(result['execution_mode'],'mock')
        self.assertEqual(len(self.skills.calls),5)
        self.assertEqual(self.skills.calls[0][1]['scene']['mode'],'experiment')

    def test_spoofed_finish_cannot_succeed(self):
        with self.assertRaises(ValueError): self.agent([call('finish'),call('finish')]).run(self.job)
        self.assertEqual(self.skills.calls,[])

    def test_shell_path_code_stub_denied(self):
        for action in [call('shell',command='true'),call('configure',patch={'code_stub':'print(1)'}),
                       call('run_stage',stage='asset',path='/tmp/escape')]:
            with self.subTest(action=action),self.assertRaises(ValueError):
                self.agent([action,action]).run(self.job)
        self.assertEqual(self.skills.calls,[])

    def test_dependency_and_round_limits(self):
        with self.assertRaises(ValueError):
            self.agent([call('run_stage',stage='runner')]*2).run(self.job)
        with self.assertRaises(RuntimeError): self.agent([call('capabilities')]*12).run(self.job)

    def test_needs_input_without_running(self):
        result=self.agent([call('needs_input',message='Only flyingcat-v1 is available.')]).run(self.job)
        self.assertEqual(result['status'],'needs_input'); self.assertEqual(self.skills.calls,[])

    def test_unavailable_model_does_not_fallback(self):
        class Down(MockModel):
            def complete(self,*a): raise ModelUnavailable('offline')
        with self.assertRaises(ModelUnavailable): BuilderAgent(self.store,self.skills,Down([])).run(self.job)
        self.assertEqual(self.skills.calls,[])

    def test_model_endpoint_confined(self):
        for url in ['http://evil.example/v1','http://127.0.0.1@evil.example/v1','file:///tmp/x']:
            with self.assertRaises(ValueError): ModelClient({'base_url':url,'model':'test'})

