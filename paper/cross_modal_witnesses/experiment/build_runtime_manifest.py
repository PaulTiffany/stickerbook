from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent; R=ROOT/'runtime_evidence'; T=R/'traces'; V=R/'stimuli'/'visual'; S=R/'stimuli'/'sonic'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
source=json.loads((R/'source.json').read_text())
items=[]
for p in sorted(T.glob('*.json')):
    d=json.loads(p.read_text()); stem=p.stem; v=V/(stem+'.svg'); s=S/(stem+'.wav')
    items.append({'trace_id':d['trace_id'],'invariant':d['invariant'],'condition':d['condition'],
                  'trace_sha256':sha(p),'visual_sha256':sha(v),'sonic_sha256':sha(s),
                  'trace_file':str(p.relative_to(ROOT)),'visual_file':str(v.relative_to(ROOT)),'sonic_file':str(s.relative_to(ROOT)),
                  'source_proof_id':d['source']['proof_id']})
out={'manifest_version':'0.1','fixture_kind':'runtime-observation','source':source,'items':items}
(R/'manifest.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(f'manifested {len(items)} observed runtime trace/stimulus triplets')
