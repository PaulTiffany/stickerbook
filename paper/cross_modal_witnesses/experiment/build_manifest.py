from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
items=[]
for fixture in sorted((ROOT/'fixtures').glob('*.json')):
    stem=fixture.stem; vis=ROOT/'stimuli'/'visual'/(stem+'.svg'); son=ROOT/'stimuli'/'sonic'/(stem+'.wav')
    data=json.loads(fixture.read_text())
    items.append({
        'trace_id':data['trace_id'],'invariant':data['invariant'],'condition':data['condition'],
        'fixture_sha256':sha(fixture),'visual_sha256':sha(vis),'sonic_sha256':sha(son),
        'visual_file':str(vis.relative_to(ROOT)),'sonic_file':str(son.relative_to(ROOT))
    })
manifest={'manifest_version':'0.1','fixture_kind':'synthetic-calibration','items':items}
(ROOT/'stimulus_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(f"manifested {len(items)} trace/stimulus triplets")
