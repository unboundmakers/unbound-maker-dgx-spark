"""Opt-in Spark cancellation test with real Runner and process cleanup check."""
import argparse
from pathlib import Path
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).parents[1]))
from unbound_builder.config import canonical, read
from unbound_builder.service import BuilderService
from unbound_builder.skills import other_isaac, write


def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); a=p.parse_args()
    service=BuilderService(read(a.config)); store=service.store
    if other_isaac(): raise RuntimeError('Unrelated Isaac session present; do not touch it')
    project=store.create_project(read(Path(__file__).parents[1]/'examples/blue-moon.json'))
    job=store.enqueue(project['project_id'],project['revision_id'],'structured','cancel-test')
    thread=threading.Thread(target=lambda:service.worker(once=True)); thread.start()
    deadline=time.monotonic()+240; reached=False
    try:
        while time.monotonic()<deadline:
            current=store.get_job(job['job_id'])
            if other_isaac(): reached=True; break
            if current['status'] in ('failed','succeeded','cancelled'): break
            time.sleep(.3)
        if not reached: raise RuntimeError('Real Isaac process was not observed')
        time.sleep(2); store.cancel(job['job_id']); thread.join(timeout=60)
        if thread.is_alive(): raise RuntimeError('Worker did not stop in bounded time')
        status=store.get_job(job['job_id'])['status']; remaining=other_isaac()
        if status!='cancelled' or remaining: raise RuntimeError('Cleanup failed: '+canonical([status,remaining]))
        report={'status':'passed','job_id':job['job_id'],'real_isaac_observed':True,'remaining_isaac_pids':remaining}
        write(store.root/('cancel-'+job['job_id']+'.json'),report); print(canonical(report),flush=True)
    finally:
        service.stop(); thread.join(timeout=180)


if __name__=='__main__': main()
