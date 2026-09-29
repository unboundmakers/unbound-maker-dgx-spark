"""Prepare and supervise single-use, bounded Isaac Sim jobs on a trusted host."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import sys
import time
import uuid

SKILL = Path(__file__).resolve().parents[1]
GRAVITY = {'earth':9.81,'moon':1.62,'zero':0.}
VERSION = '0.1.0'


def pairs(items):
    result = {}
    for key,value in items:
        if key in result:
            raise ValueError('Duplicate JSON key: '+key)
        result[key] = value
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=pairs)


def write(path,data):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    temporary.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            result.update(block)
    return result.hexdigest()


def local(root,name):
    if not isinstance(name,str) or not name or ':' in name or '\\' in name:
        raise ValueError('Unsafe package path.')
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or str(p)!=name or name=='.':
        raise ValueError('Unsafe package path.')
    result = root/name
    if not result.is_file() or not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('Missing or escaping file: '+name)
    cursor = root
    for part in p.parts:
        cursor = cursor/part
        if cursor.is_symlink():
            raise ValueError('Symlink in input.')
    return result


def checked(root,entries):
    if not isinstance(entries,list) or not entries:
        raise ValueError('Missing file inventory.')
    result = {}
    for item in entries:
        if not isinstance(item,dict) or not {'path','sha256','bytes'}.issubset(item):
            raise ValueError('Malformed file inventory.')
        name = item['path']
        path = local(root,name)
        if name in result or digest(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
            raise ValueError('File integrity mismatch: '+name)
        result[name] = path
    return result


def validate_request(value,scene):
    fields = {'schema_version','run_kind','headless','environment','mass_kg','thrust_n','duration_s','session_seconds'}
    if not isinstance(value,dict) or set(value)-fields or type(value.get('schema_version')) is not int or value['schema_version']!=1:
        raise ValueError('Unsupported runner request.')
    if scene not in ('meadow','space','moon'):
        raise ValueError('Unsupported scene.')
    kind = value.get('run_kind','smoke')
    headless = value.get('headless',kind=='smoke')
    if kind not in ('smoke','interactive') or type(headless) is not bool or (kind=='interactive' and headless):
        raise ValueError('Choose smoke or interactive; interactive needs a window.')
    environment = value.get('environment',{'meadow':'earth','space':'zero','moon':'moon'}[scene])
    if not isinstance(environment,str) or environment not in GRAVITY:
        raise ValueError('Unknown gravity environment.')
    if scene!='moon' and set(value)&{'environment','mass_kg','thrust_n','duration_s'}:
        raise ValueError('Physics parameters are read-only for story presets.')
    def number(name,default,low,high):
        n = value.get(name,default)
        if type(n) not in (int,float) or not math.isfinite(n) or not low<=n<=high:
            raise ValueError(name+' is outside its finite numeric range.')
        return float(n)
    mass = number('mass_kg',2,.5,10)
    thrust = number('thrust_n',7 if scene=='moon' else mass*(GRAVITY[environment]+2.5),0,50)
    duration = value.get('duration_s',10)
    if type(duration) is not int or duration not in (5,10,20):
        raise ValueError('duration_s must be 5, 10 or 20.')
    session = number('session_seconds',60,5,300)
    return dict(schema_version=1,scene_id=scene,mode='experiment' if scene=='moon' else 'story',
                run_kind=kind,headless=headless,environment=environment,gravity_m_s2=GRAVITY[environment],
                mass_kg=mass,thrust_n=thrust,duration_s=duration,session_seconds=session,
                speed_m_s=6. if scene=='space' else 2.5,
                warnings=['Thrust does not exceed weight: holding A cannot launch from rest.']
                if scene=='moon' and thrust<=mass*GRAVITY[environment] else [])


def scene_inventory(source):
    m = read(local(source,'manifest.json'))
    if not isinstance(m,dict) or m.get('status')!='succeeded' or m.get('skill_version')!=VERSION:
        raise ValueError('Expected a successful v0.1.0 scene package.')
    expected = {'unbound-maker-scene-builder':'scene.usda','unbound-maker-scene-optimizer':'optimized.usda'}
    if m.get('skill') not in expected or m.get('entrypoint')!=expected[m['skill']]:
        raise ValueError('Only Scene Builder and Scene Optimizer outputs are supported.')
    files = checked(source,m.get('files'))
    if 'manifest.json' in files:
        raise ValueError('Reserved manifest entry.')
    for name in (m['entrypoint'],'scene-config.json'):
        if name not in files:
            raise ValueError('Scene entry/config absent from inventory.')
    config = read(files['scene-config.json'])
    if not isinstance(config,dict) or not isinstance(config.get('request'),dict):
        raise ValueError('Invalid scene configuration.')
    scene = config['request'].get('scene_id')
    if scene not in ('meadow','space','moon') or config.get('character_prim')!='/World/Character' or config.get('visual_prim')!='/World/Character/Pose/Visual':
        raise ValueError('Unsupported scene paths.')
    if config['request'].get('mode')!=('experiment' if scene=='moon' else 'story'):
        raise ValueError('Unexpected scene mode.')
    files['manifest.json'] = source/'manifest.json'
    return m,config,files


def prepare(source,request,output):
    source,output = Path(source).resolve(),Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.resolve().is_relative_to(source):
        raise ValueError('Use a new output directory outside input, with an existing parent.')
    manifest,config,files = scene_inventory(source)
    request = validate_request(request,config['request']['scene_id'])
    expected = {name:digest(path) for name,path in files.items()}
    output.mkdir()
    for name,path in files.items():
        destination = output/'scene'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
        if digest(destination)!=expected[name]:
            raise ValueError('Source changed during copy.')
    shutil.copytree(SKILL/'runtime',output/'runtime',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    write(output/'request.json',request)
    job = dict(schema_version=1,skill='unbound-maker-simulation-runner',skill_version=VERSION,
               status='prepared',job_id=uuid.uuid4().hex,scene_entry='scene/'+manifest['entrypoint'],
               scene_config='scene/scene-config.json',source_manifest_sha256=expected['manifest.json'],
               request=request,files=[dict(path=str(p.relative_to(output)),sha256=digest(p),bytes=p.stat().st_size)
                                      for p in sorted(output.rglob('*')) if p.is_file()])
    write(output/'job.json',job)
    return job


def verify_job(job):
    job = Path(job).resolve()
    data = read(local(job,'job.json'))
    if not isinstance(data,dict) or data.get('skill')!='unbound-maker-simulation-runner' or data.get('skill_version')!=VERSION:
        raise ValueError('Unsupported job.')
    files = checked(job,data.get('files'))
    if data.get('scene_entry') not in files or 'runtime/isaac_runtime.py' not in files or 'request.json' not in files:
        raise ValueError('Incomplete job inventory.')
    if read(job/'request.json')!=data.get('request'):
        raise ValueError('Job request changed.')
    return data


def status(job):
    job = Path(job).resolve()
    data = read(local(job,'job.json'))
    state = read(job/'launch-report.json') if (job/'launch-report.json').is_file() else (
        read(job/'state.json') if (job/'state.json').is_file() else {'status':'prepared'})
    if (job/'STOP').exists() and state['status'] not in ('succeeded','failed','stopped','timed_out'):
        state['status'] = 'stop_requested'
    return {**state,'job_id':data['job_id']}


def request_stop(job):
    job = Path(job).resolve()
    read(local(job,'job.json'))
    write(job/'STOP',{'requested_at':time.time()})
    return status(job)


def launch(job,isaac_python,timeout_seconds=240):
    job,executable = Path(job).resolve(),Path(isaac_python).resolve()
    data = verify_job(job)
    if (job/'STOP').exists() or (job/'launch.lock').exists() or (job/'run-report.json').exists():
        raise ValueError('Job is stopped or already used. Prepare a new job.')
    if not executable.is_file() or not os.access(executable,os.X_OK):
        raise ValueError('Provide the installed executable Isaac Python launcher.')
    if type(timeout_seconds) not in (float,int) or not math.isfinite(timeout_seconds) or not 1<=timeout_seconds<=600:
        raise ValueError('Wall timeout must be within 1..600 seconds.')
    with (job/'launch.lock').open('x') as f:
        f.write(data['job_id'])
    started = time.monotonic()
    environment = os.environ.copy()
    # CPU USD verification paths are incompatible with Kit's bundled runtime.
    for name in ('PYTHONPATH','LD_LIBRARY_PATH','PXR_WORK_THREAD_LIMIT'):
        environment.pop(name,None)
    write(job/'state.json',{'status':'starting','updated_at':time.time()})
    process = None
    outcome = None
    try:
        with (job/'runtime.log').open('w') as log:
            process = subprocess.Popen([str(executable),str(job/'runtime/isaac_runtime.py'),'--job',str(job)],
                cwd=str(executable.parent),env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            stop_since = None
            while process.poll() is None:
                elapsed = time.monotonic()-started
                if (job/'STOP').exists():
                    stop_since = stop_since or time.monotonic()
                if elapsed>timeout_seconds or (stop_since is not None and time.monotonic()-stop_since>8):
                    outcome = 'stopped' if stop_since is not None else 'timed_out'
                    os.killpg(process.pid,signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL)
                        process.wait()
                    break
                time.sleep(.2)
        report = read(job/'run-report.json') if (job/'run-report.json').is_file() else {}
        valid = report.get('job_id')==data['job_id'] and report.get('request_sha256')==digest(job/'request.json')
        if outcome is None:
            outcome = report.get('status','failed') if valid and process.returncode==0 else 'failed'
        result = dict(status=outcome,exit_code=process.returncode,elapsed_wall_s=round(time.monotonic()-started,3),
                      run_report_valid=valid)
        if not valid:
            result['error'] = 'Missing or mismatched fresh run report; exit code alone is insufficient.'
        write(job/'launch-report.json',result)
        return result
    except BaseException as exc:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
        write(job/'launch-report.json',{'status':'failed','error':str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('capabilities')
    p = sub.add_parser('prepare')
    for name in ('input','request','output'):
        p.add_argument('--'+name,required=True,type=Path)
    for name in ('status','stop','launch'):
        p = sub.add_parser(name)
        p.add_argument('--job',type=Path,required=True)
        if name=='launch':
            p.add_argument('--isaac-python',type=Path,required=True)
            p.add_argument('--timeout-seconds',type=float,default=240)
    a = parser.parse_args()
    try:
        if a.command=='capabilities':
            result = dict(skill='unbound-maker-simulation-runner',version=VERSION,scenes=['meadow','space','moon'],
                          experiment_durations_s=[5,10,20],gravity_presets=GRAVITY,mass_kg=[.5,10],thrust_n=[0,50],
                          preview_is_bounded=True,trained_policy=False)
        elif a.command=='prepare':
            result = prepare(a.input,read(a.request),a.output)
        elif a.command=='status':
            result = status(a.job)
        elif a.command=='stop':
            result = request_stop(a.job)
        else:
            result = launch(a.job,a.isaac_python,a.timeout_seconds)
        print(json.dumps(result,allow_nan=False))
        return 0 if result.get('status') not in ('failed','timed_out') else 2
    except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)}))
        return 2


if __name__=='__main__':
    sys.exit(main())
