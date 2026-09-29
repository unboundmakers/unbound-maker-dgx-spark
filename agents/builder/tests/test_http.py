import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
sys.path.insert(0,str(Path(__file__).parents[1]))
from unbound_builder.service import BuilderService
from unbound_builder.http_api import make_server


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.service=BuilderService({'root':self.tmp.name,'skills_root':str(Path(__file__).parents[3]/'skills'),
            'cpu_python':sys.executable,'assets_root':self.tmp.name,'isaac_python':sys.executable,
            'gpu_lock':self.tmp.name+'/gpu.lock','model':{'base_url':'http://127.0.0.1:1/v1','model':'missing'}})
        self.server=make_server(self.service,'x'*32,port=0)
        self.thread=threading.Thread(target=self.server.serve_forever); self.thread.start()
        self.addCleanup(self.close)
        self.url='http://127.0.0.1:'+str(self.server.server_port)

    def close(self): self.server.shutdown(); self.server.server_close(); self.thread.join()

    def req(self,path,data=None,token='x'*32,raw=None):
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        request=urllib.request.Request(self.url+path,data=raw if raw is not None else (json.dumps(data).encode() if data is not None else None),headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=5) as r: return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            with e: return e.code,json.load(e)

    def test_auth_body_and_routes(self):
        self.assertEqual(self.req('/api/capabilities',token='wrong')[0],401)
        self.assertEqual(self.req('/api/projects',raw=b'x'*65537)[0],413)
        self.assertEqual(self.req('/api/projects',raw=b'{"design":{},"design":{}}')[0],400)
        self.assertEqual(self.req('/api/artifacts/../../etc/passwd')[0],404)
        self.assertEqual(self.req('/api/jobs/'+'0'*32)[0],404)
        status,body=self.req('/api/capabilities')
        self.assertEqual(status,200); self.assertFalse(body['model']['ready'])

    def test_job_idempotency_revisions_cancel(self):
        status,p=self.req('/api/projects',{'design':{}}); self.assertEqual(status,201)
        data={'project_id':p['project_id'],'revision_id':p['revision_id'],'execution_mode':'structured','request_id':'one'}
        _,j=self.req('/api/jobs',data); _,same=self.req('/api/jobs',data)
        self.assertEqual(j['job_id'],same['job_id'])
        self.assertEqual(self.req('/api/jobs/'+j['job_id']+'/cancel',{})[1]['status'],'cancelled')
        route='/api/projects/'+p['project_id']+'/revisions'
        patch={'parent_revision':p['revision_id'],'patch':{'asset':{'scale':1.2}}}
        self.assertEqual(self.req(route,patch)[0],201); self.assertEqual(self.req(route,patch)[0],409)

    def test_single_worker_and_offline_failure(self):
        p=self.service.store.create_project({})
        j=self.service.store.enqueue(p['project_id'],p['revision_id'],'agent','offline','make cat')
        self.service.worker(once=True)
        self.assertEqual(self.service.store.get_job(j['job_id'])['status'],'failed')

    def test_public_binding_and_missing_token_denied(self):
        with self.assertRaises(ValueError): make_server(self.service,'',port=0)
        with self.assertRaises(ValueError): make_server(self.service,'x'*32,host='0.0.0.0',port=0)

    def test_public_ui_shell_does_not_expose_authenticated_data(self):
        try:
            response=urllib.request.urlopen(self.url+'/',timeout=5)
        except urllib.error.HTTPError as error:
            response=error
        with response:
            self.assertEqual(response.status,200)
            self.assertEqual(response.headers.get_content_type(),'text/html')
            self.assertIn("connect-src 'self'",response.headers['Content-Security-Policy'])
            self.assertNotIn(b'x'*32,response.read())
        self.assertEqual(self.req('/api/capabilities',token='')[0],401)
        for route in ('/ui/../builder.py','/ui/%2e%2e/builder.py','/ui/operator.spark.example.json'):
            self.assertEqual(self.req(route)[0],404)
