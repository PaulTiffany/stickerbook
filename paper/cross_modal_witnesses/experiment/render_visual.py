from __future__ import annotations
import html, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "fixtures"
OUT = ROOT / "stimuli" / "visual"
OUT.mkdir(parents=True, exist_ok=True)

PAGE_Y = {"farm":170, "beach":230, "playground":290, "school":350, "space":410, "theater":470, None:530}

def esc(s): return html.escape(str(s))

def render(data):
    W,H=1200,620
    import hashlib
    stim_id=hashlib.sha256(data['trace_id'].encode()).hexdigest()[:10]
    title=f"StickerBook trace witness · {stim_id}"
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="40" y="45" font-family="sans-serif" font-size="28" font-weight="700">{esc(title)}</text>',
           '<text x="40" y="75" font-family="sans-serif" font-size="15">synthetic calibration stimulus</text>']
    # lanes
    for page,y in PAGE_Y.items():
        if page is None: continue
        parts += [f'<line x1="150" y1="{y}" x2="1150" y2="{y}" stroke="#c9c9c9" stroke-width="1"/>',
                  f'<text x="40" y="{y+5}" font-family="sans-serif" font-size="16">{esc(page)}</text>']
    events=data['events']
    if not events: return ''
    max_t=max(e['t'] for e in events) or 1.0
    for i,e in enumerate(events):
        x=210 + (e['t']/max_t)*760 if max_t>0 else 210+i*200
        if len(events)==1: x=450
        y=PAGE_Y.get(e.get('page'),530)
        acc = None if e.get('receipt') is None else e['receipt'].get('accepted')
        stroke = '#222222' if acc is not False else '#777777'
        dash = '' if acc is not False else ' stroke-dasharray="7 5"'
        parts.append(f'<circle cx="{x}" cy="{y}" r="14" fill="white" stroke="{stroke}" stroke-width="3"{dash}/>' )
        parts.append(f'<text x="{x+22}" y="{y-18}" font-family="monospace" font-size="13">{esc(e["event"])}</text>')
        sel=e.get('selected_key') or '—'
        parts.append(f'<text x="{x+22}" y="{y+2}" font-family="monospace" font-size="12">{esc(sel)}</text>')
        verdict='no receipt' if acc is None else ('accepted' if acc else 'rejected')
        parts.append(f'<text x="{x+22}" y="{y+20}" font-family="sans-serif" font-size="12">{esc(verdict)}</text>')
        legal=', '.join(e.get('legal_keys', [])) or '—'
        parts.append(f'<text x="{x+22}" y="{y+37}" font-family="monospace" font-size="10">legal: {esc(legal)}</text>')
        # state delta arrows to target pages
        for j,d in enumerate(e.get('state_delta', [])):
            target=d.get('page', e.get('page'))
            ty=PAGE_Y.get(target,y)
            tx=x+120+j*55
            parts.append(f'<line x1="{x}" y1="{y}" x2="{tx}" y2="{ty}" stroke="#333" stroke-width="2" marker-end="url(#a)"/>')
            parts.append(f'<text x="{tx+4}" y="{ty-5}" font-family="sans-serif" font-size="11">Δ {esc(d.get("op","state"))}</text>')
    parts.insert(2,'<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker></defs>')
    parts.append('</svg>')
    return ''.join(parts)

for path in sorted(FIX.glob('*.json')):
    data=json.loads(path.read_text())
    (OUT / (path.stem+'.svg')).write_text(render(data), encoding='utf-8')
print(f"rendered {len(list(FIX.glob('*.json')))} SVG witnesses")
