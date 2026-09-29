"""Fixed local tools, immutable artifacts and bounded owned subprocesses."""
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
import time
import uuid
import zipfile
from .config import STAGES, canonical, normalize_design, read

NAMES = {s:'unbound-maker-'+({'asset':'asset-builder','personality':'personality-builder','scene':'scene-builder',
                           'optimizer':'scene-optimizer','runner':'simulation-runner'}[s]) for s in STAGES}
SCRIPTS = {s:NAMES[s].replace('unbound-maker-','').replace('-','_')+'.py' for s in STAGES}
PARENTS = {'asset':None,'personality':'asset','scene':'personality','optimizer':'scene','runner':'optimizer'}
SECTIONS = {'runner':'simulation'}


class Cancelled(RuntimeError): pass
class Busy(RuntimeError): pass


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def write(path,data):
    path=Path(path); tmp=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    tmp.write_text(canonical(data)+'\n',encoding='utf-8'); tmp.replace(path)


def safe_file(root,name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name: raise ValueError('Unsafe inventory path')
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or str(p)!=name or name=='.': raise ValueError('Unsafe inventory path')
    f=root/name
    if not f.is_file() or not f.resolve().is_relative_to(root.resolve()): raise ValueError('Missing or escaping file')
    cursor=root
    for part in p.parts:
        cursor=cursor/part
        if cursor.is_symlink(): raise ValueError('Symlink in artifact')
    return f


def inventory(root,skill):
    root=Path(root)
    m=read(safe_file(root,'manifest.json'))
    if m.get('status')!='succeeded' or m.get('skill')!=skill or m.get('skill_version')!='0.1.0':
        raise ValueError('Not a successful supported Skill manifest')
    if not isinstance(m.get('files'),list) or not m['files']: raise ValueError('Missing inventory')
    names=set()
    for row in m['files']:
        f=safe_file(root,row['path'])
        if row['path'] in names or f.stat().st_size!=row['bytes'] or digest(f)!=row['sha256']:
            raise ValueError('Artifact integrity mismatch')
        names.add(row['path'])
    if m['entrypoint'] not in names: raise ValueError('Entry absent from inventory')
    return m


def validate_reports(prepared,run,launch,request_sha):
    checks=run.get('checks')
    if (run.get('status')!='succeeded' or launch.get('status')!='succeeded'
        or launch.get('run_report_valid') is not True or type(launch.get('exit_code')) is not int or launch['exit_code']!=0
        or run.get('job_id')!=prepared['job_id'] or run.get('request_sha256')!=request_sha
        or not isinstance(checks,dict) or not checks or any(v is not True for v in checks.values())):
        raise ValueError('Runner reports did not pass identity/check gates')


def bundle(root,target,skill,cancel):
    root=Path(root); manifest=inventory(root,skill); target=Path(target)
    temporary=target.with_suffix('.partial.zip')
    with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for name in ['manifest.json']+[row['path'] for row in manifest['files']]:
            if cancel(): raise Cancelled('Task cancelled during packaging')
            archive.write(safe_file(root,name),name)
    temporary.replace(target)


@contextmanager
def lock(path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise Busy('Another worker owns this resource')
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)


def run_process(argv,log,env,timeout,cancel,on_cancel=None,termination_grace=8):
    environment=os.environ.copy()
    for k in ('PYTHONPATH','LD_LIBRARY_PATH','PXR_WORK_THREAD_LIMIT'): environment.pop(k,None)
    environment.update(env)
    started=time.monotonic(); stop_at=None; reason=None; process=None
    with Path(log).open('w') as output:
        try:
            process=subprocess.Popen([str(x) for x in argv],stdout=output,stderr=subprocess.STDOUT,
                                     env=environment,start_new_session=True)
            while process.poll() is None:
                if cancel() and reason is None: reason=Cancelled('Task cancelled')
                if time.monotonic()-started>timeout and reason is None: reason=TimeoutError('Tool wall timeout')
                if reason is not None:
                    if stop_at is None:
                        stop_at=time.monotonic()
                        if on_cancel: on_cancel()
                    if not on_cancel or time.monotonic()-stop_at>18:
                        process.terminate() if os.name=='nt' else os.killpg(process.pid,signal.SIGTERM)
                        break
                time.sleep(.1)
            if process.poll() is None:
                try: process.wait(timeout=termination_grace)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL); process.wait()
            if reason is not None: raise reason
            if cancel(): raise Cancelled('Task cancelled')
            if process.returncode: raise RuntimeError('Tool exited %d; inspect %s'%(process.returncode,Path(log).name))
        finally:
            if process is not None and process.poll() is None:
                if on_cancel: on_cancel()
                os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=max(15,termination_grace))
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL); process.wait()


def other_isaac():
    if sys.platform!='linux': return []
    found=[]
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args=p.read_bytes().split(b'\0')
            names=[Path(a.decode(errors='replace')).name for a in args if a]
            if any(n in ('kit','isaac_runtime.py','run_flight.py','lab_preview.py') for n in names): found.append(p.parent.name)
        except (OSError,ValueError): pass
    return found


class SkillExecutor:
    def __init__(self,operator,store):
        self.op=operator; self.store=store
        self.skills=Path(operator['skills_root']).resolve()

    def skill_path(self,stage):
        if stage not in NAMES: raise ValueError('Unknown tool')
        return self.skills/NAMES[stage]

    def request(self,stage,design): return dict(schema_version=1,**design[SECTIONS.get(stage,stage)])

    def cache_key(self,stage,design,inputs):
        parent=PARENTS[stage]; skill=self.skill_path(stage)
        hashes=[(str(p.relative_to(skill)),digest(p)) for p in sorted(skill.rglob('*'))
                if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
        material=['artifact-contract-2',stage,self.request(stage,design),hashes,inputs[parent]['manifest_sha'] if parent else None]
        return hashlib.sha256(canonical(material).encode()).hexdigest()

    def command(self,stage,request,output,inputs,design):
        script=self.skill_path(stage)/'scripts'/SCRIPTS[stage]
        args=[self.op['cpu_python'],str(script)]
        if stage=='asset': args+=['build','--request',str(request)]
        elif stage=='personality': args+=['build','--profile',str(request),'--asset',inputs['asset']['path']]
        elif stage=='scene': args+=['build','--request',str(request),'--assets',self.op['assets_root'],'--character',inputs['personality']['path']]
        elif stage=='optimizer': args+=['optimize','--request',str(request),'--input',inputs['scene']['path']]
        else: raise ValueError('Runner uses supervised launch')
        return args+['--output',str(output)]

    def checked_result(self,value,stage):
        p=Path(value['path']).resolve()
        if not p.is_relative_to(self.store.root/'jobs'): raise ValueError('Cached output outside job storage')
        inventory(p,NAMES[stage])
        if digest(p/'manifest.json')!=value['manifest_sha']: raise ValueError('Cached manifest changed')
        return value

    def run_stage(self,job_id,stage,design,inputs):
        design=normalize_design(design); self.skill_path(stage)
        parent=PARENTS[stage]
        if parent:
            if parent not in inputs: raise ValueError('Missing dependency: '+parent)
            self.checked_result(inputs[parent],parent)
        cancelled=lambda:self.store.get_job(job_id)['cancel_requested']
        if cancelled(): raise Cancelled('Task cancelled')
        key=self.cache_key(stage,design,inputs)
        if stage!='runner':
            hit=self.store.cache_get(key)
            if hit:
                self.checked_result(hit,stage)
                self.store.event(job_id,dict(stage=stage,status='reused',cache_key=key))
                return dict(hit,reused=True)
        directory=self.store.jobdir(job_id)/(stage+'-'+uuid.uuid4().hex[:8]); directory.mkdir()
        request=directory/'request.json'; output=directory/'output'
        write(request,self.request(stage,design))
        self.store.set_state(job_id,'validating' if stage=='runner' else 'building',{'stage':stage})
        self.store.event(job_id,dict(stage=stage,status='running'))
        if stage=='runner':
            result=self.run_simulation(job_id,directory,request,output,inputs,cancelled)
        else:
            run_process(self.command(stage,request,output,inputs,design),directory/'tool.log',self.op.get('cpu_env',{}),
                        self.op.get('cpu_timeout_seconds',600),cancelled)
            manifest=inventory(output,NAMES[stage])
            result=dict(stage=stage,path=str(output),entrypoint=manifest['entrypoint'],manifest_sha=digest(output/'manifest.json'),reused=False)
            result['artifacts']={'manifest.json':self.store.register_artifact(job_id,output/'manifest.json')}
            if stage=='optimizer':
                archive=directory/'scene.zip'; bundle(output,archive,NAMES[stage],cancelled)
                result['artifacts']['scene.zip']=self.store.register_artifact(job_id,archive)
            self.store.cache_put(key,result)
        self.store.event(job_id,dict(stage=stage,status='passed',reused=False))
        return result

    def run_simulation(self,j,directory,request,output,inputs,cancel):
        script=self.skill_path('runner')/'scripts'/SCRIPTS['runner']
        run_process([sys.executable,str(script),'prepare','--input',inputs['optimizer']['path'],'--request',request,'--output',output],
                    directory/'prepare.log',{},120,cancel)
        timeout=self.op.get('gpu_timeout_seconds',240)
        supervisor=Path(__file__).with_name('runner_supervisor.py')
        with lock(self.op['gpu_lock']):
            if other_isaac(): raise Busy('An existing Isaac process is running; not owned or stopped by this Agent')
            argv=[sys.executable,str(supervisor),'--script',str(script),'launch','--job',str(output),
                  '--isaac-python',self.op['isaac_python'],'--timeout-seconds',str(timeout)]
            run_process(argv,directory/'launch.log',{},timeout+30,cancel,
                        lambda:write(output/'STOP',{'requested_by':'builder-agent'}))
        prepared=read(output/'job.json'); run=read(output/'run-report.json'); launch=read(output/'launch-report.json')
        validate_reports(prepared,run,launch,digest(output/'request.json'))
        for f in prepared['files']:
            p=safe_file(output,f['path'])
            if p.stat().st_size!=f['bytes'] or digest(p)!=f['sha256']: raise ValueError('Prepared job mutated')
        artifacts={name:self.store.register_artifact(j,output/name) for name in ('preview.png','run-report.json','trajectory.json','launch-report.json')}
        return dict(stage='runner',path=str(output),job_id=run['job_id'],checks=run['checks'],artifacts=artifacts,
                    simulated_s=run['simulated_s'],reused=False,trained_policy=False)
