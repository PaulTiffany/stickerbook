from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TRACES=ROOT/'runtime_evidence'/'traces'
REQ_TRACE={'schema_version','trace_id','fixture_kind','invariant','condition','ground_truth','events','source'}
REQ_EVENT={'t','event','page','principal','revision_before','route','legal_keys','selected_key','receipt','state_delta'}
errors=[]
for p in sorted(TRACES.glob('*.json')):
    d=json.loads(p.read_text())
    miss=REQ_TRACE-d.keys()
    if miss: errors.append(f'{p.name}: missing {sorted(miss)}')
    if d.get('fixture_kind')!='runtime-observation': errors.append(f'{p.name}: wrong fixture_kind')
    if d.get('condition')!='aligned': errors.append(f'{p.name}: observed evidence currently expected aligned-only')
    if not d.get('ground_truth',{}).get('invariant_satisfied',False): errors.append(f'{p.name}: ground truth must be true for current observations')
    for i,e in enumerate(d.get('events',[])):
        m=REQ_EVENT-e.keys()
        if m: errors.append(f'{p.name} event {i}: missing {sorted(m)}')
        r=e.get('receipt')
        if r and r.get('accepted') is False and e.get('state_delta'):
            errors.append(f'{p.name} event {i}: rejected receipt with state delta')
if errors: raise SystemExit('\n'.join(errors))
print(f'validated {len(list(TRACES.glob("*.json")))} observed runtime traces')
