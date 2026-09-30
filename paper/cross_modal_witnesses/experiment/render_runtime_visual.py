from __future__ import annotations
import hashlib, html, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TRACES=ROOT/'runtime_evidence'/'traces'
OUT=ROOT/'runtime_evidence'/'stimuli'/'visual'; OUT.mkdir(parents=True,exist_ok=True)
PAGE_Y={'farm':170,'beach':230,'playground':290,'school':350,'space':410,'theater':470,None:530}
def esc(x): return html.escape(str(x))

def render(d):
    W,H=1200,620
    sid=hashlib.sha256(d['trace_id'].encode()).hexdigest()[:10]
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker></defs>',
           f'<text x="40" y="45" font-family="sans-serif" font-size="28" font-weight="700">StickerBook runtime witness · {sid}</text>',
           '<text x="40" y="75" font-family="sans-serif" font-size="15">observed runtime evidence · ground-truth label withheld from participant-facing use</text>']
    for page,y in PAGE_Y.items():
        if page is None: continue
        parts += [f'<line x1="150" y1="{y}" x2="1150" y2="{y}" stroke="#c9c9c9" stroke-width="1"/>',
                  f'<text x="40" y="{y+5}" font-family="sans-serif" font-size="16">{esc(page)}</text>']
    evs=d['events']; max_t=max((e['t'] for e in evs),default=1.0) or 1.0
    for i,e in enumerate(evs):
        x=230+(e['t']/max_t)*610 if len(evs)>1 else 450
        y=PAGE_Y.get(e.get('page'),530)
        rec=e.get('receipt'); acc=None if rec is None else rec.get('accepted')
        dash='' if acc is not False else ' stroke-dasharray="7 5"'
        parts.append(f'<circle cx="{x}" cy="{y}" r="14" fill="white" stroke="#222" stroke-width="3"{dash}/>')
        parts.append(f'<text x="{x+22}" y="{y-20}" font-family="monospace" font-size="13">{esc(e["event"])}</text>')
        verdict='no receipt' if acc is None else ('accepted receipt' if acc else 'rejected receipt')
        parts.append(f'<text x="{x+22}" y="{y}" font-family="sans-serif" font-size="12">{verdict}</text>')
        if rec:
            prov=f'LLM={rec.get("translatedBy") or "none"} · selector={rec.get("selectedBy") or "none"}'
            parts.append(f'<text x="{x+22}" y="{y+18}" font-family="monospace" font-size="10">{esc(prov)}</text>')
        for j,delta in enumerate(e.get('state_delta',[])):
            target=delta.get('page',e.get('page')); ty=PAGE_Y.get(target,y); tx=x+130+j*70
            parts.append(f'<line x1="{x}" y1="{y}" x2="{tx}" y2="{ty}" stroke="#333" stroke-width="2" marker-end="url(#a)"/>')
            label=delta.get('op','state')
            if 'object' in delta: label += ':'+str(delta['object'])
            parts.append(f'<text x="{tx+4}" y="{ty-5}" font-family="sans-serif" font-size="11">Δ {esc(label)}</text>')
    parts.append('</svg>'); return ''.join(parts)

for p in sorted(TRACES.glob('*.json')):
    d=json.loads(p.read_text())
    (OUT/(p.stem+'.svg')).write_text(render(d),encoding='utf-8')
print(f'rendered {len(list(TRACES.glob("*.json")))} observed runtime SVG witnesses')
