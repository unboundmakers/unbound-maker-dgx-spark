from contextlib import contextmanager
import hashlib
from pathlib import Path
import re
import sqlite3
import time
import uuid
from .config import canonical, loads, normalize_design, merge_design

TERMINAL = {'succeeded','failed','cancelled','interrupted','needs_input'}


class Conflict(ValueError): pass


def ident(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value): raise ValueError('Invalid ID')
    return value


class Store:
    def __init__(self,root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/'jobs').mkdir(exist_ok=True)
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, head TEXT);
            CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY, project TEXT, parent TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project TEXT, revision TEXT, mode TEXT,
              request TEXT, signature TEXT, instruction TEXT, status TEXT, cancel INTEGER DEFAULT 0,
              created REAL, detail TEXT DEFAULT '{}', UNIQUE(project,request));
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, job TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, job TEXT, path TEXT, sha TEXT);
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, data TEXT);
            ''')

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.root/'builder.sqlite3',timeout=30)
        c.row_factory = sqlite3.Row
        try:
            with c: yield c
        finally: c.close()

    def create_project(self,design):
        normalized = normalize_design(design)
        p,r = uuid.uuid4().hex,uuid.uuid4().hex
        value = dict(project_id=p,revision_id=r,parent_revision=None,design=normalized,
                     source_fields=design,applied_defaults=normalized,unsupported_requests=[])
        with self.db() as c:
            c.execute('INSERT INTO projects VALUES(?,?)',(p,r))
            c.execute('INSERT INTO revisions VALUES(?,?,?,?)',(r,p,None,canonical(value)))
        return value

    def revision(self,r):
        with self.db() as c: row = c.execute('SELECT data FROM revisions WHERE id=?',(ident(r),)).fetchone()
        if row is None: raise KeyError('Revision not found')
        return loads(row['data'])

    def revise(self,p,parent,patch):
        ident(p); ident(parent)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT head FROM projects WHERE id=?',(p,)).fetchone()
            if row is None: raise KeyError('Project not found')
            if row['head']!=parent: raise Conflict('Parent revision is no longer current')
            old = loads(c.execute('SELECT data FROM revisions WHERE id=?',(parent,)).fetchone()['data'])
            r = uuid.uuid4().hex
            value = dict(project_id=p,revision_id=r,parent_revision=parent,design=merge_design(old['design'],patch),
                         source_fields=patch,applied_defaults={},unsupported_requests=[])
            c.execute('INSERT INTO revisions VALUES(?,?,?,?)',(r,p,parent,canonical(value)))
            c.execute('UPDATE projects SET head=? WHERE id=?',(r,p))
        return value

    def enqueue(self,p,r,mode,request_id,instruction=''):
        ident(p); rev = self.revision(r)
        if rev['project_id']!=p: raise ValueError('Revision belongs to another project')
        if mode not in ('structured','agent'): raise ValueError('Unknown execution mode')
        if not isinstance(instruction,str) or len(instruction)>8000 or (mode=='agent' and not instruction.strip()): raise ValueError('Agent needs a bounded instruction')
        if not isinstance(request_id,str) or not 1<=len(request_id)<=128: raise ValueError('Request ID required')
        sig = canonical([r,mode,instruction])
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT id,signature FROM jobs WHERE project=? AND request=?',(p,request_id)).fetchone()
            if old:
                if old['signature']!=sig: raise Conflict('Request ID already used for different inputs')
                jid = old['id']
            else:
                jid = uuid.uuid4().hex
                c.execute('INSERT INTO jobs(id,project,revision,mode,request,signature,instruction,status,created) VALUES(?,?,?,?,?,?,?,?,?)',
                          (jid,p,r,mode,request_id,sig,instruction,'queued',time.time()))
        self.jobdir(jid).mkdir(exist_ok=True)
        return self.get_job(jid)

    def jobdir(self,j): return self.root/'jobs'/ident(j)

    def get_job(self,j):
        with self.db() as c:
            row = c.execute('SELECT * FROM jobs WHERE id=?',(ident(j),)).fetchone()
            if row is None: raise KeyError('Job not found')
            events = [loads(x['data']) for x in c.execute('SELECT data FROM events WHERE job=? ORDER BY seq',(j,))]
            artifacts = [dict(x) for x in c.execute('SELECT id,sha FROM artifacts WHERE job=?',(j,))]
        return dict(job_id=j,project_id=row['project'],revision_id=row['revision'],execution_mode=row['mode'],
                    instruction=row['instruction'],status=row['status'],cancel_requested=bool(row['cancel']),
                    detail=loads(row['detail']),events=events,artifacts=artifacts)

    def claim(self):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute("SELECT id FROM jobs WHERE status='queued' AND cancel=0 ORDER BY created LIMIT 1").fetchone()
            if row is None: return None
            c.execute("UPDATE jobs SET status='planning' WHERE id=?",(row['id'],))
        return self.get_job(row['id'])

    def set_state(self,j,state,detail=None):
        if state not in TERMINAL|{'queued','planning','building','validating'}: raise ValueError('Unknown state')
        with self.db() as c:
            c.execute('UPDATE jobs SET status=?,detail=? WHERE id=?',(state,canonical(detail or {}),ident(j)))

    def event(self,j,value):
        with self.db() as c: c.execute('INSERT INTO events(job,data) VALUES(?,?)',(ident(j),canonical(dict(time=time.time(),**value))))

    def cancel(self,j):
        self.get_job(j)
        with self.db() as c:
            c.execute("UPDATE jobs SET cancel=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=?",(j,))
        return self.get_job(j)

    def recover(self):
        with self.db() as c:
            c.execute("UPDATE jobs SET status='interrupted' WHERE status IN ('planning','building','validating')")

    def register_artifact(self,j,path):
        path = Path(path).resolve()
        if not path.is_file() or not path.is_relative_to(self.jobdir(j)): raise ValueError('Artifact outside job')
        a = uuid.uuid4().hex
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.db() as c: c.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(a,j,str(path.relative_to(self.root)),h))
        return a

    def artifact(self,a):
        with self.db() as c: row = c.execute('SELECT * FROM artifacts WHERE id=?',(ident(a),)).fetchone()
        if row is None: raise KeyError('Artifact not found')
        path = (self.root/row['path']).resolve()
        if not path.is_file() or not path.is_relative_to(self.root/'jobs'): raise ValueError('Artifact escaped storage')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha']: raise ValueError('Artifact changed')
        return path

    def cache_get(self,key):
        with self.db() as c: row = c.execute('SELECT data FROM cache WHERE key=?',(key,)).fetchone()
        return loads(row['data']) if row else None

    def cache_put(self,key,value):
        with self.db() as c: c.execute('INSERT OR REPLACE INTO cache VALUES(?,?)',(key,canonical(value)))
