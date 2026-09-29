"""Authenticated single-user loopback adapter. No public binding or CORS."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
from .config import canonical, fields, loads
from .store import Conflict


def make_server(service,token,host='127.0.0.1',port=8765,preview_html=None):
    if host!='127.0.0.1': raise ValueError('Only 127.0.0.1 may be bound')
    if not isinstance(token,str) or len(token)<32 or not token.isascii(): raise ValueError('Use an ASCII API token of at least 32 characters')
    web=Path(__file__).parents[1]/'web'
    preview=None
    if preview_html is not None:
        source=Path(preview_html)
        if source.suffix.lower()!='.html' or not source.is_file() or source.stat().st_size>1048576:
            raise ValueError('Preview must be an operator-selected HTML file up to 1 MiB')
        preview=source.read_text(encoding='utf-8')
        bridge='<script src="/ui/concept-bridge.js"></script>'
        preview=(preview.replace('</body>',bridge+'</body>') if '</body>' in preview else preview+bridge).encode()

    class Handler(BaseHTTPRequestHandler):
        server_version='UnboundMaker/0.1'
        def setup(self):
            super().setup(); self.connection.settimeout(10)
        def log_message(self,*args): pass
        def reply(self,status,value):
            body=canonical(value).encode(); self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
        def handle_request(self):
            static={'/':('index.html','text/html'),'/ui/app.js':('app.js','text/javascript'),
                    '/ui/style.css':('style.css','text/css'),'/ui/concept-bridge.js':('concept-bridge.js','text/javascript')}
            if self.command=='GET' and (self.path in static or self.path=='/concept-preview'):
                if self.path=='/concept-preview':
                    body=preview or b'<!doctype html><html lang="en"><body><p>No external concept preview configured.</p></body></html>'
                    mime='text/html'; policy="default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; frame-ancestors 'self'; form-action 'none'; base-uri 'none'"
                else:
                    filename,mime=static[self.path]; body=(web/filename).read_bytes()
                    policy="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; form-action 'none'; base-uri 'none'"
                self.send_response(200); self.send_header('Content-Type',mime+'; charset=utf-8')
                self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store')
                self.send_header('Content-Security-Policy',policy); self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Referrer-Policy','no-referrer'); self.end_headers(); self.wfile.write(body); return
            authorization=self.headers.get('Authorization','').encode('utf-8')
            if not hmac.compare_digest(authorization,('Bearer '+token).encode()): return self.reply(401,{'error':'Unauthorized'})
            data={}
            if self.command=='POST':
                length=self.headers.get('Content-Length','0')
                if self.headers.get('Transfer-Encoding') or not length.isdecimal(): return self.reply(400,{'error':'Invalid body framing'})
                length=int(length)
                if length>65536: return self.reply(413,{'error':'Body too large'})
                if self.headers.get_content_type()!='application/json': return self.reply(415,{'error':'Use application/json'})
                raw=self.rfile.read(length)
                if len(raw)!=length: raise ValueError('Truncated body')
                data=loads(raw.decode()) if raw else {}
                fields(data,set(data) if isinstance(data,dict) else set())
            path=self.path; store=service.store
            if self.command=='GET' and path=='/api/capabilities': return self.reply(200,service.capabilities())
            if self.command=='POST' and path=='/api/projects':
                fields(data,{'design'}); return self.reply(201,store.create_project(data.get('design',{})))
            match=re.fullmatch('/api/projects/([0-9a-f]{32})/revisions',path)
            if self.command=='POST' and match:
                fields(data,{'parent_revision','patch'})
                return self.reply(201,store.revise(match[1],data.get('parent_revision'),data.get('patch')))
            if self.command=='POST' and path=='/api/jobs':
                fields(data,{'project_id','revision_id','execution_mode','request_id','instruction'})
                return self.reply(202,store.enqueue(data.get('project_id'),data.get('revision_id'),data.get('execution_mode'),data.get('request_id'),data.get('instruction','')))
            match=re.fullmatch('/api/jobs/([0-9a-f]{32})(/cancel)?',path)
            if match and self.command=='GET' and not match[2]: return self.reply(200,store.get_job(match[1]))
            if match and self.command=='POST' and match[2]:
                fields(data,set()); return self.reply(200,store.cancel(match[1]))
            match=re.fullmatch('/api/artifacts/([0-9a-f]{32})',path)
            if match and self.command=='GET':
                file=store.artifact(match[1]); self.send_response(200)
                content_type={'.png':'image/png','.json':'application/json'}.get(file.suffix,'application/octet-stream')
                self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(file.stat().st_size))
                self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store')
                self.send_header('Content-Disposition','attachment; filename="'+match[1]+file.suffix+'"'); self.end_headers()
                with file.open('rb') as f: shutil.copyfileobj(f,self.wfile)
                return
            self.reply(404,{'error':'Not found'})
        def dispatch(self):
            try: self.handle_request()
            except Conflict: self.reply(409,{'error':'Revision or request ID conflict'})
            except KeyError: self.reply(404,{'error':'Not found'})
            except (ValueError,TypeError): self.reply(400,{'error':'Invalid request or artifact integrity failure'})
            except (BrokenPipeError,ConnectionResetError,TimeoutError): pass
            except Exception: self.reply(500,{'error':'Internal error'})
        do_GET=dispatch
        do_POST=dispatch
    return ThreadingHTTPServer((host,port),Handler)
