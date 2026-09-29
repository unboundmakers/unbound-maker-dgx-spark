"""Source-only publication gate; heuristic checks are not a security certification."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

IMAGE_ALLOWLIST = {
    'docs/essay-images/recruitment.png',
    'docs/essay-images/flying-cat-drawing.jpg',
    'docs/essay-images/meadow-simulation.jpg',
    'docs/essay-images/moon-simulation.jpg',
    'docs/architecture.png',
    'verification/builder-agent/preview.png',
    'verification/builder-agent/structured-moon-preview.png',
}
BINARY = {'.usd','.usda','.usdc','.usdz','.blend','.exr','.hdr','.gguf',
          '.safetensors','.sqlite3','.db','.zip','.mp4','.mov','.bin','.pem','.key'}
PRIVATE_DIRS = {'artifacts','dist','downloads','__pycache__','.git','.venv','node_modules'}
SECRETS = {
    'private-key': re.compile('-----BEGIN '+r'(?:OPENSSH|RSA|EC|DSA|ENCRYPTED) PRIVATE KEY-----'),
    'github-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'service-key': re.compile(r'\b(?:sk-proj-[A-Za-z0-9_-]{35,}|AIza[A-Za-z0-9_-]{35})\b'),
}


def audit(root):
    root=Path(root).resolve()
    findings=[]; inventory=[]
    for p in sorted(root.rglob('*')):
        name=p.relative_to(root).as_posix()
        if p.is_symlink():
            findings.append({'path':name,'rule':'symlink'}); continue
        if not p.is_file(): continue
        private=any(x in PRIVATE_DIRS or x.startswith('builder-state') for x in p.relative_to(root).parts)
        private |= p.name.startswith(('.env','operator.local','operator.spark.qwen25-test'))
        forbidden=private or p.suffix.lower() in BINARY or '.sqlite3' in p.name
        if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp','.gif'} and name not in IMAGE_ALLOWLIST:
            forbidden=True
        if forbidden:
            findings.append({'path':name,'rule':'excluded-asset-or-private-data'})
        raw=p.read_bytes()
        inventory.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        try: text=raw.decode('utf-8')
        except UnicodeDecodeError: continue
        for rule,pattern in SECRETS.items():
            if pattern.search(text): findings.append({'path':name,'rule':rule})
    return {'scope':'source-only heuristic publication gate; not comprehensive security audit',
            'status':'passed' if not findings else 'blocked','file_count':len(inventory),
            'bytes':sum(x['bytes'] for x in inventory),'findings':findings,'files':inventory}


def package(root, output):
    root, output=Path(root).resolve(),Path(output).resolve()
    if output.is_relative_to(root): raise ValueError('Archive output must be outside source tree')
    report=audit(root)
    if report['findings']: raise ValueError('Publication gate blocked')
    output.mkdir(parents=True,exist_ok=False)
    rows=report['files']
    groups={'unbound-maker-source':rows}
    shared=[r for r in rows if r['path'] in ('LICENSE','LICENSING.md','NOTICE','THIRD_PARTY_NOTICES.md')
            or r['path'].startswith('LICENSES/')]
    for skill in sorted((root/'skills').glob('*/SKILL.md')):
        prefix=skill.parent.relative_to(root).as_posix()+'/'
        groups[skill.parent.name]=[r for r in rows if r['path'].startswith(prefix)]+shared
    if (root/'agents/builder').is_dir():
        groups['unbound-maker-builder-agent']=[r for r in rows if r['path'].startswith('agents/builder/')]+shared
    for name, entries in groups.items():
        with zipfile.ZipFile(output/(name+'-0.1.0-rc1.zip'),'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for row in sorted(entries,key=lambda r:r['path']):
                raw=(root/row['path']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=row['sha256']: raise ValueError('Source changed during packaging')
                info=zipfile.ZipInfo(row['path'],(2026,9,29,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o100644 << 16
                archive.writestr(info,raw)
        with zipfile.ZipFile(output/(name+'-0.1.0-rc1.zip')) as archive:
            if archive.testzip(): raise ValueError('Archive CRC check failed')
    (output/'SOURCE-MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    checks=[]
    for f in sorted(output.iterdir()):
        checks.append(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n')
    (output/'SHA256SUMS').write_text(''.join(checks))
    return report


def main():
    p=argparse.ArgumentParser(); p.add_argument('root'); p.add_argument('--report'); p.add_argument('--package')
    a=p.parse_args(); root=Path(a.root).resolve()
    if a.package:
        result=package(root,a.package)
        print(json.dumps({'status':result['status'],'file_count':result['file_count'],'output':a.package})); return
    if not a.report: p.error('--report or --package is required')
    output=Path(a.report).resolve()
    if output.is_relative_to(root): raise ValueError('Report must be outside the inspected tree')
    result=audit(root); output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))
    raise SystemExit(0 if result['status']=='passed' else 1)


if __name__=='__main__': main()
