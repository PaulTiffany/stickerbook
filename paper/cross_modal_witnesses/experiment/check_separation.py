from __future__ import annotations
import hashlib, json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FIX=ROOT/'fixtures'; VIS=ROOT/'stimuli'/'visual'; SON=ROOT/'stimuli'/'sonic'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
by=defaultdict(dict)
for p in FIX.glob('*.json'):
    d=json.loads(p.read_text()); by[d['invariant']][d['condition']]=p.stem
rows=[]
for inv,pair in sorted(by.items()):
    a,v=pair['aligned'],pair['violation']
    row={'invariant':inv,
         'visual_separated':sha(VIS/(a+'.svg')) != sha(VIS/(v+'.svg')),
         'sonic_separated':sha(SON/(a+'.wav')) != sha(SON/(v+'.wav'))}
    rows.append(row)
report={'report_version':'0.1','note':'Byte-level separation only; this is not evidence of human perceptual discriminability.','pairs':rows}
(ROOT/'separation_report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if not all(r['visual_separated'] and r['sonic_separated'] for r in rows):
    raise SystemExit('one or more fixture pairs collide in a renderer')
print(f"all {len(rows)} aligned/violation pairs are byte-distinct in both renderers")
