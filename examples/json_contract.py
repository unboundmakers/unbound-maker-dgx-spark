"""Generic JSON helpers extracted from the Unbound Maker Builder.

Copyright 2026 Unbound Maker contributors
SPDX-License-Identifier: Apache-2.0
Modified for this standalone example: retained only generic validation helpers.
"""

import json
import math


def object_pairs(pairs):
    out = {}
    for k,v in pairs:
        if k in out: raise ValueError('Duplicate JSON key: '+k)
        out[k] = v
    return out


def loads(text):
    return json.loads(text,object_pairs_hook=object_pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


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
