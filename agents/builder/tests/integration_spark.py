"""Opt-in REAL Skill/GPU acceptance. Not part of unittest discovery."""
import argparse
from pathlib import Path
import sys
import time
import signal
sys.path.insert(0,str(Path(__file__).parents[1]))
from unbound_builder.config import canonical, read
from unbound_builder.service import BuilderService
from unbound_builder.skills import digest, write


def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True)
    p.add_argument('--mode',choices=('structured','agent'),required=True)
    a=p.parse_args(); svc=BuilderService(read(a.config)); store=svc.store
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:svc.stop())
    baseline={str(f.relative_to(svc.skills.skills)):digest(f) for f in svc.skills.skills.rglob('*')
              if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}
    if a.mode=='agent' and not svc.model.ready(): raise RuntimeError('Configured local model is not installed/ready')
    project=store.create_project({} if a.mode=='agent' else read(Path(__file__).parents[1]/'examples/blue-moon.json'))
    instruction='Create a blue (#2867D7) flying cat, scale 1, in the moon experiment scene. Use mass 2kg, upward thrust 7N and run a 10-second headless smoke test. Keep the natural face.'
    job=store.enqueue(project['project_id'],project['revision_id'],a.mode,'initial',instruction if a.mode=='agent' else '')
    print(canonical({'phase':'started','job_id':job['job_id'],'mode':a.mode}),flush=True)
    svc.worker(once=True); result=store.get_job(job['job_id'])
    print(canonical({'phase':'first-complete','job_id':job['job_id'],'status':result['status'],'detail':result['detail']}),flush=True)
    if result['status']!='succeeded': raise RuntimeError('First build failed: '+job['job_id'])
    revision=store.revise(project['project_id'],result['detail']['revision_id'],{'simulation':{'thrust_n':11}})
    second=store.enqueue(project['project_id'],revision['revision_id'],'structured','force-only')
    svc.worker(once=True); changed=store.get_job(second['job_id'])
    if changed['status']!='succeeded': raise RuntimeError('Force-only build failed: '+second['job_id'])
    reused={s:v['reused'] for s,v in changed['detail']['results'].items()}
    if reused!={'asset':True,'personality':True,'scene':True,'optimizer':True,'runner':False}:
        raise RuntimeError('Incorrect reuse: '+canonical(reused))
    after={str(f.relative_to(svc.skills.skills)):digest(f) for f in svc.skills.skills.rglob('*')
           if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}
    if baseline!=after: raise RuntimeError('Skill sources changed during integration')
    report={'status':'succeeded','mode':a.mode,'time':time.time(),'first_job':job['job_id'],
            'force_job':second['job_id'],'force_reuse':reused,'skill_sources_unchanged':True,
            'model':svc.model.identity if a.mode=='agent' else None,'human_ui_tested':False,'trained_policy':False}
    write(store.root/('integration-'+a.mode+'-'+job['job_id']+'.json'),report)
    print(canonical(report),flush=True)


if __name__=='__main__': main()
