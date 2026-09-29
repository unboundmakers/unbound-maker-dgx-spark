#!/usr/bin/env python3
"""Run `python3 builder.py --help`. Configuration is operator-owned."""
import argparse
import os
import signal
import threading
from unbound_builder.config import canonical, read
from unbound_builder.service import BuilderService
from unbound_builder.http_api import make_server


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--config',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('capabilities')
    a=sub.add_parser('project'); a.add_argument('--design',required=True)
    a=sub.add_parser('revise'); a.add_argument('--project',required=True); a.add_argument('--parent',required=True); a.add_argument('--patch',required=True)
    a=sub.add_parser('submit'); a.add_argument('--project',required=True); a.add_argument('--revision',required=True)
    a.add_argument('--mode',choices=('structured','agent'),required=True); a.add_argument('--request-id',required=True); a.add_argument('--instruction',default='')
    for name in ('status','cancel'):
        a=sub.add_parser(name); a.add_argument('--job',required=True)
    a=sub.add_parser('worker'); a.add_argument('--once',action='store_true')
    a=sub.add_parser('serve'); a.add_argument('--port',type=int,default=8765)
    a.add_argument('--preview-html',help='Optional local concept HTML, sandboxed and not redistributed')
    args=p.parse_args(); service=BuilderService(read(args.config)); store=service.store
    if args.command=='capabilities': result=service.capabilities()
    elif args.command=='project': result=store.create_project(read(args.design))
    elif args.command=='revise': result=store.revise(args.project,args.parent,read(args.patch))
    elif args.command=='submit': result=store.enqueue(args.project,args.revision,args.mode,args.request_id,args.instruction)
    elif args.command=='status': result=store.get_job(args.job)
    elif args.command=='cancel': result=store.cancel(args.job)
    elif args.command=='worker':
        for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda *_:service.stop())
        service.worker(once=args.once); return
    else:
        server=make_server(service,os.environ.get('UNBOUND_BUILDER_TOKEN',''),port=args.port,preview_html=args.preview_html)
        thread=threading.Thread(target=service.background_worker,name='builder-worker'); thread.start()
        def shutdown(*_):
            service.stop(); threading.Thread(target=server.shutdown,daemon=True).start()
        for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,shutdown)
        try: server.serve_forever()
        finally: service.stop(); server.server_close(); thread.join()
        return
    print(canonical(result))


if __name__=='__main__': main()
