"""One bounded continuation of the explicitly requested download/test job; no scheduler."""
import argparse
from pathlib import Path
import sys
import time
import signal
import threading
sys.path.insert(0,str(Path(__file__).parents[1]))
from unbound_builder.config import canonical, read
from unbound_builder.model import ModelClient
from unbound_builder.skills import lock, write, run_process


def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True)
    p.add_argument('--wait-seconds',type=int,default=7200); a=p.parse_args()
    if not 1<=a.wait_seconds<=10800: raise ValueError('Wait must be bounded to 1..10800 seconds')
    config=read(a.config); root=Path(config['root']); root.mkdir(parents=True,exist_ok=True)
    path=root/'model-integration-status.json'; model=ModelClient(config['model'])
    stopped=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stopped.set())
    with lock(root/'model-integration.lock'):
        start=time.monotonic()
        while not model.ready():
            value={'status':'waiting_for_download','model':model.name,'elapsed_s':round(time.monotonic()-start)}
            write(path,value)
            if stopped.is_set():
                write(path,dict(value,status='cancelled')); return 2
            if time.monotonic()-start>a.wait_seconds:
                write(path,dict(value,status='timed_out')); return 2
            stopped.wait(30)
        write(path,{'status':'running_real_model_integration','model':model.name})
        print(canonical({'status':'model_registered_starting_test','model':model.name}),flush=True)
        try:
            # All child operations are already bounded; this wrapper adds a generous outer limit.
            run_process([sys.executable,str(Path(__file__).with_name('integration_spark.py')),
                         '--config',a.config,'--mode','agent'],root/'model-integration.log',{},6000,stopped.is_set,
                        termination_grace=180)
            value={'status':'passed','model':model.name}
        except Exception as e:
            value={'status':'failed','model':model.name,'error':type(e).__name__,
                   'note':'Inspect model-integration.log and owned job diagnostics before retrying'}
        write(path,value); print(canonical(value),flush=True)
        return 0 if value['status']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
