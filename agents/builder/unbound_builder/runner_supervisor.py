"""Turn supervisor termination into Python cleanup of its nested Isaac group."""
import argparse
import importlib.util
import signal
import sys


def stop(signum,frame): raise SystemExit(128+signum)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--script',required=True)
    args,remaining=parser.parse_known_args()
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    spec=importlib.util.spec_from_file_location('owned_runner',args.script)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    sys.argv=[args.script,*remaining]
    sys.exit(module.main())
