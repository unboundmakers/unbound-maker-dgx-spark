"""One durable queue, one worker, separate HTTP lifecycle."""
from pathlib import Path
import threading
from .agent import BuilderAgent, summary
from .config import STAGES, capabilities, fields
from .model import ModelClient
from .skills import Cancelled, SkillExecutor, lock, write
from .store import Store


class BuilderService:
    def __init__(self,operator):
        fields(operator,{'root','skills_root','cpu_python','assets_root','isaac_python','gpu_lock','cpu_env',
                         'cpu_timeout_seconds','gpu_timeout_seconds','model'})
        for key in ('root','skills_root','cpu_python','assets_root','isaac_python','gpu_lock'):
            if not isinstance(operator.get(key),str) or not Path(operator[key]).is_absolute():
                raise ValueError('Operator must supply an absolute '+key)
        for key,default,high in [('cpu_timeout_seconds',600,1800),('gpu_timeout_seconds',240,600)]:
            val=operator.get(key,default)
            if type(val) is not int or not 1<=val<=high: raise ValueError('Invalid '+key)
        env=fields(operator.get('cpu_env',{}),{'PYTHONPATH','LD_LIBRARY_PATH','PXR_WORK_THREAD_LIMIT'})
        if any(not isinstance(v,str) for v in env.values()): raise ValueError('CPU environment must contain strings')
        self.store=Store(operator['root']); self.skills=SkillExecutor(operator,self.store)
        self.model=ModelClient(operator['model']); self.stop_event=threading.Event(); self.active=None
        self.worker_error=None

    def capabilities(self):
        return dict(capabilities(),model={**self.model.identity,'ready':self.model.ready()},worker_error=self.worker_error)

    def stop(self):
        self.stop_event.set()
        if self.active: self.store.cancel(self.active)

    def worker(self,once=False):
        with lock(self.store.root/'worker.lock'):
            self.store.recover()
            while not self.stop_event.is_set():
                job=self.store.claim()
                if job is None:
                    if once: return
                    self.stop_event.wait(.3); continue
                self.active=job['job_id']
                self.store.jobdir(self.active).mkdir(exist_ok=True)
                try:
                    if self.stop_event.is_set(): self.store.cancel(self.active)
                    if job['execution_mode']=='agent': result=BuilderAgent(self.store,self.skills,self.model).run(job)
                    else:
                        design=self.store.revision(job['revision_id'])['design']; outputs={}
                        for stage in STAGES: outputs[stage]=self.skills.run_stage(self.active,stage,design,outputs)
                        result={'status':'succeeded','execution_mode':'structured','revision_id':job['revision_id'],
                                'design':design,'results':{s:summary(v) for s,v in outputs.items()}}
                    if self.store.get_job(self.active)['cancel_requested']: raise Cancelled('Task cancelled')
                    write(self.store.jobdir(self.active)/'result.json',result)
                    result_id=self.store.register_artifact(self.active,self.store.jobdir(self.active)/'result.json')
                    self.store.set_state(self.active,result['status'],dict(result,result_artifact=result_id))
                except Cancelled as e: self.store.set_state(self.active,'cancelled',{'error':str(e)})
                except Exception as e:
                    # Tool diagnostics are retained locally; API errors do not leak arbitrary paths or credentials.
                    write(self.store.jobdir(self.active)/'error.json',{'type':type(e).__name__,'message':str(e)})
                    self.store.set_state(self.active,'failed',{'error':type(e).__name__,'message':'Build failed; inspect local job diagnostics.'})
                finally: self.active=None
                if once: return

    def background_worker(self):
        try: self.worker()
        except Exception as e: self.worker_error=type(e).__name__; self.stop_event.set()

