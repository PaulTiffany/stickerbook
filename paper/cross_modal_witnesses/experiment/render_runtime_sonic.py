from __future__ import annotations
import json, math, struct, wave
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TRACES=ROOT/'runtime_evidence'/'traces'; OUT=ROOT/'runtime_evidence'/'stimuli'/'sonic'; OUT.mkdir(parents=True,exist_ok=True)
SR=48000
PAGE={'farm':220.0,'beach':246.94,'playground':261.63,'school':293.66,'space':329.63,'theater':349.23,None:196.0}
def tone(freq,dur,amp=.17,harm=.18):
    n=int(SR*dur); out=[]
    for i in range(n):
        env=1-i/n; t=i/SR
        out.append(amp*env*(math.sin(2*math.pi*freq*t)+harm*math.sin(2*math.pi*2*freq*t)))
    return out
def add(buf,start,sig):
    for i,v in enumerate(sig):
        if start+i<len(buf): buf[start+i]+=v
def render(d,path):
    evs=d['events']; slot=1.15; total=max(1.8,len(evs)*slot+.8); buf=[0.0]*int(total*SR)
    for i,e in enumerate(evs):
        t=.12+i*slot; base=PAGE.get(e.get('page'),196.0)
        rec=e.get('receipt'); route=e.get('route','')
        # Page identity is always directly encoded from canonical trace.
        add(buf,int(t*SR),tone(base,.40))
        # Direct human route: octave marker; Omega-language route: major-sixth marker.
        if 'double-tap' in route or 'pointer' in route or 'child' in route:
            add(buf,int((t+.10)*SR),tone(base*2,.14,amp=.10,harm=.05))
        elif 'omega' in route:
            add(buf,int((t+.10)*SR),tone(base*2**(9/12),.14,amp=.10,harm=.05))
        # Receipt/provenance marker.
        if rec:
            if rec.get('translatedBy') is None:
                add(buf,int((t+.30)*SR),tone(base*1.25,.15,amp=.10,harm=.05))
            if rec.get('selectedBy'):
                add(buf,int((t+.47)*SR),tone(base*1.5,.20,amp=.12,harm=.08))
            if rec.get('accepted'):
                add(buf,int((t+.68)*SR),tone(base*2,.18,amp=.12,harm=.04))
        # Page-local state assertions sound in the asserted page's timbre.
        for delta in e.get('state_delta',[]):
            p=delta.get('page'); op=delta.get('op','')
            if p and p != e.get('page'):
                add(buf,int((t+.24)*SR),tone(PAGE.get(p,392.0),.28,amp=.12,harm=.20))
            if op=='assert-empty':
                add(buf,int((t+.52)*SR),tone(base*.5,.12,amp=.07,harm=.0))
            if op=='stop-motion':
                add(buf,int((t+.50)*SR),tone(base*.75,.10,amp=.12,harm=.5))
    peak=max(max((abs(x) for x in buf),default=0),1e-9); s=min(.85/peak,1.0)
    pcm=b''.join(struct.pack('<h',max(-32767,min(32767,int(x*s*32767)))) for x in buf)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
for p in sorted(TRACES.glob('*.json')):
    render(json.loads(p.read_text()),OUT/(p.stem+'.wav'))
print(f'rendered {len(list(TRACES.glob("*.json")))} observed runtime WAV witnesses at {SR} Hz')
