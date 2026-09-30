from __future__ import annotations
import json, math, struct, wave
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FIX=ROOT/'fixtures'; OUT=ROOT/'stimuli'/'sonic'; OUT.mkdir(parents=True, exist_ok=True)
SR=48000
PAGE_BASE={'farm':220.0,'beach':246.94,'playground':261.63,'school':293.66,'space':329.63,'theater':349.23,None:196.0}

def action_offset(event):
    s=(event.get('selected_key') or '')+' '+(event.get('receipt') or {}).get('action','')
    if 'MOVE' in s or 'move' in s: return 0
    if 'ANIMATE' in s or 'animate' in s: return 5
    if 'FACE' in s or 'facing' in s: return 9
    if 'NOOP' in s or 'noop' in s: return -5
    return 2

def tone(freq, dur, amp=.18, harmonic=0.18, decay=True):
    n=int(SR*dur); out=[]
    for i in range(n):
        t=i/SR
        env=(1-i/n) if decay else 1.0
        v=amp*env*(math.sin(2*math.pi*freq*t)+harmonic*math.sin(2*math.pi*2*freq*t))
        out.append(v)
    return out

def add(buf, start, sig):
    for i,v in enumerate(sig):
        if start+i < len(buf): buf[start+i]+=v

def render(data, path):
    events=data['events']; slot=1.1; total=max(1.8, len(events)*slot+0.8)
    buf=[0.0]*int(total*SR)
    for idx,e in enumerate(events):
        t0=idx*slot+0.12
        base=PAGE_BASE.get(e.get('page'),196.0)
        freq=base*2**(action_offset(e)/12)
        add(buf,int(t0*SR),tone(freq,0.42))
        # Legal-table membership cue: an out-of-set selected key gets a brief high buzz.
        selected=e.get('selected_key')
        legal=e.get('legal_keys',[])
        if selected is not None and e.get('selected_key_source') in {'host-table','rederived-host-table'} and selected not in legal:
            add(buf,int((t0+.08)*SR),tone(base*2.8,0.16,amp=.12,harmonic=.75))
        # receipt marker: accepted resolves upward; reject cuts downward/noisy interruption
        rec=e.get('receipt')
        if rec:
            if rec.get('accepted'):
                add(buf,int((t0+.48)*SR),tone(base*1.5,0.22,amp=.14,harmonic=.08))
            else:
                add(buf,int((t0+.48)*SR),tone(base*.75,0.12,amp=.14,harmonic=.5))
        # stale response: ghosted late onset retaining originating page timbre
        if e.get('authority_expired'):
            add(buf,int((t0+.72)*SR),tone(base,0.18,amp=.07,harmonic=.3))
        # cross-page delta: foreign page timbre sounds within same slot
        for d in e.get('state_delta',[]):
            p=d.get('page')
            if p and p != e.get('page'):
                add(buf,int((t0+.25)*SR),tone(PAGE_BASE.get(p,392.0),0.35,amp=.13,harmonic=.22))
    # normalize conservatively
    peak=max(max(abs(x) for x in buf),1e-9); scale=min(0.85/peak,1.0)
    pcm=b''.join(struct.pack('<h', max(-32767,min(32767,int(x*scale*32767)))) for x in buf)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)

for p in sorted(FIX.glob('*.json')):
    render(json.loads(p.read_text()), OUT/(p.stem+'.wav'))
print(f"rendered {len(list(FIX.glob('*.json')))} WAV witnesses at {SR} Hz")
