import copy
import json
import math
import re
from pathlib import Path

STAGES = ('asset','personality','scene','optimizer','runner')
PHYSICS = {'environment','mass_kg','thrust_n','duration_s'}


def object_pairs(pairs):
    out = {}
    for k,v in pairs:
        if k in out: raise ValueError('Duplicate JSON key: '+k)
        out[k] = v
    return out


def loads(text):
    return json.loads(text,object_pairs_hook=object_pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def read(path): return loads(Path(path).read_text(encoding='utf-8'))


def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False)


def fields(value,allowed):
    if not isinstance(value,dict) or set(value)-set(allowed):
        raise ValueError('Unsupported fields; expected '+','.join(sorted(allowed)))
    return value


def number(value,low,high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('Expected finite number within %s..%s'%(low,high))
    return value


def choice(value,allowed):
    if not isinstance(value,str) or value not in allowed: raise ValueError('Expected one of '+','.join(allowed))
    return value


def normalize_design(value):
    fields(value,{'schema_version','asset','personality','scene','optimizer','simulation'})
    if type(value.get('schema_version',1)) is not int or value.get('schema_version',1)!=1:
        raise ValueError('schema_version must be integer 1')
    a = fields(value.get('asset',{}),{'template_id','body_color','scale'})
    p = fields(value.get('personality',{}),{'adapter','default_expression'})
    s = fields(value.get('scene',{}),{'scene_id','mode','spawn_id','heading_degrees'})
    o = fields(value.get('optimizer',{}),{'profile'})
    r = fields(value.get('simulation',{}),{'run_kind','headless','session_seconds'}|PHYSICS)
    scene = choice(s.get('scene_id','meadow'),('meadow','space','moon'))
    mode = 'experiment' if scene=='moon' else 'story'
    if s.get('mode',mode)!=mode or s.get('spawn_id','start')!='start': raise ValueError('Scene/mode/spawn mismatch')
    asset = dict(template_id=choice(a.get('template_id','flyingcat-v1'),('flyingcat-v1',)),scale=number(a.get('scale',1.),.5,2))
    if 'body_color' in a:
        if not isinstance(a['body_color'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',a['body_color']): raise ValueError('Expected #RRGGBB')
        asset['body_color'] = a['body_color'].upper()
    personality = dict(adapter=choice(p.get('adapter','flyingcat-v1'),('flyingcat-v1',)),
                       default_expression=choice(p.get('default_expression','natural'),('natural',)))
    kind = choice(r.get('run_kind','smoke'),('smoke','interactive'))
    headless = r.get('headless',kind=='smoke')
    if type(headless) is not bool or (kind=='interactive' and headless): raise ValueError('Interactive requires a window')
    simulation = dict(run_kind=kind,headless=headless,session_seconds=number(r.get('session_seconds',60),5,300))
    if scene!='moon' and PHYSICS&set(r): raise ValueError('Story physics fields are read-only')
    if scene=='moon':
        duration = r.get('duration_s',10)
        if type(duration) is not int or duration not in (5,10,20): raise ValueError('Duration must be 5, 10 or 20 seconds')
        simulation.update(environment=choice(r.get('environment','moon'),('earth','moon','zero')),
                          mass_kg=number(r.get('mass_kg',2),.5,10),thrust_n=number(r.get('thrust_n',7),0,50),duration_s=duration)
    return dict(schema_version=1,asset=asset,personality=personality,
                scene=dict(scene_id=scene,mode=mode,spawn_id='start',heading_degrees=number(s.get('heading_degrees',0),-180,180)),
                optimizer=dict(profile=choice(o.get('profile','preserve'),('preserve','preview'))),simulation=simulation)


def merge_design(base,patch):
    fields(patch,{'asset','personality','scene','optimizer','simulation'})
    out = copy.deepcopy(base)
    old_scene = out['scene']['scene_id']
    for k,v in patch.items():
        if not isinstance(v,dict): raise ValueError('Each patch section must be an object')
        out[k].update(v)
    if out['scene']['scene_id']!=old_scene:
        if 'mode' not in patch.get('scene',{}): out['scene'].pop('mode',None)
        if out['scene']['scene_id']!='moon':
            for k in PHYSICS:
                if k not in patch.get('simulation',{}): out['simulation'].pop(k,None)
    if 'run_kind' in patch.get('simulation',{}) and 'headless' not in patch['simulation']:
        out['simulation']['headless'] = out['simulation']['run_kind']=='smoke'
    return normalize_design(out)


def capabilities():
    return dict(version='0.1.0',stages=list(STAGES),template_ids=['flyingcat-v1'],scenes={'meadow':'story','space':'story','moon':'experiment'},
                scale=[.5,2],mass_kg=[.5,10],thrust_n=[0,50],duration_s=[5,10,20],
                gravity={'earth':9.81,'moon':1.62,'zero':0},default_expression='natural',trained_policy=False)
