"""Local OpenAI-compatible JSON action adapter; no remote fallback or redirects."""
import urllib.error
import urllib.parse
import urllib.request
from .config import canonical, fields, loads


class ModelUnavailable(RuntimeError): pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


class ModelClient:
    def __init__(self,config):
        fields(config,{'base_url','model','timeout_seconds','reasoning_effort'})
        url=urllib.parse.urlsplit(config['base_url'])
        if (url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1')
            or url.username or url.password or url.query or url.fragment or url.path.rstrip('/')!='/v1'):
            raise ValueError('Model endpoint must be local HTTP /v1')
        self.url=config['base_url'].rstrip('/'); self.name=config['model']
        if not isinstance(self.name,str) or not self.name or len(self.name)>128: raise ValueError('Invalid model name')
        self.timeout=config.get('timeout_seconds',120)
        if type(self.timeout) not in (int,float) or not 1<=self.timeout<=300: raise ValueError('Invalid model timeout')
        self.effort=config.get('reasoning_effort','none')
        if self.effort not in ('none','low','medium','high'): raise ValueError('Invalid reasoning effort')
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        self.identity={'execution_mode':'agent','model':self.name,'provider':'local-openai-compatible'}

    def request(self,path,data=None,timeout=None):
        payload=None if data is None else canonical(data).encode()
        if payload and len(payload)>131072: raise ValueError('Model context body limit exceeded')
        req=urllib.request.Request(self.url+path,data=payload,headers={'Content-Type':'application/json'})
        try:
            with self.opener.open(req,timeout=timeout or self.timeout) as response:
                raw=response.read(1048577)
                if len(raw)>1048576: raise ModelUnavailable('Model response too large')
            return loads(raw.decode())
        except (OSError,urllib.error.URLError,ValueError) as e:
            raise ModelUnavailable('Local model request failed: '+type(e).__name__) from e

    def ready(self):
        try: return any(row.get('id')==self.name for row in self.request('/models',timeout=3).get('data',[]))
        except ModelUnavailable: return False

    def complete(self,messages,tools):
        system={'role':'system','content':'Available actions: '+canonical(tools)+
                '\nReturn ONE JSON object {"name": "action_name", "arguments": {...}}. No prose or code fences.'}
        data=self.request('/chat/completions',{'model':self.name,'messages':[system]+messages,
            'response_format':{'type':'json_object'},'temperature':0,'max_tokens':2048,
            'reasoning_effort':self.effort,'stream':False})
        try:
            choice=data['choices'][0]
            if choice.get('finish_reason')=='length': raise ValueError('Model response truncated')
            return loads(choice['message']['content'])
        except (KeyError,TypeError,IndexError) as e: raise ValueError('Malformed model response') from e

