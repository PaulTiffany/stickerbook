"""Measure master clock, spectral-flux onsets, beat grid and lyric alignment."""
import hashlib,json,re
from difflib import SequenceMatcher
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import stft,find_peaks,correlate,resample_poly

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'video/data'
AUDIO=ROOT/'assets/video/audio/im-upping-my-phop.wav'

def tokens(text):
    return re.findall(r'[a-z0-9]+',text.lower().replace('jev','jev').replace('p-hop','phop').replace('p-doom','pdoom').replace('l-l-m','llm'))

def main():
    y,sr=sf.read(AUDIO); duration=len(y)/sr
    mono=resample_poly(y.mean(axis=1),1,4); rate=sr/4
    _,times,z=stft(mono,fs=rate,nperseg=1024,noverlap=768)
    power=np.abs(z); flux=np.maximum(np.diff(np.log1p(power*100),axis=1),0).mean(axis=0)
    onset_times=times[1:]; flux/=max(flux.max(),1e-9)
    dt=float(times[1]-times[0]); ac=correlate(flux-flux.mean(),flux-flux.mean(),mode='full')[len(flux)-1:]
    lags=np.arange(round(60/120/dt),round(60/90/dt)+1)
    lag=int(lags[np.argmax(ac[lags])]); bpm=60/(lag*dt)
    # Refine tempo and phase against measured onset energy across the song.
    best=(-1,None,None)
    for tempo in np.linspace(bpm-2,bpm+2,161):
        interval=60/tempo
        for phase in np.linspace(0,interval,80,endpoint=False):
            grid=np.arange(phase,duration,interval)
            score=np.interp(grid,onset_times,flux).mean()
            if score>best[0]:best=(score,float(tempo),float(phase))
    _,bpm,phase=best
    grid=np.arange(phase,duration,60/bpm)
    peaks,_=find_peaks(flux,distance=round(.12/dt),prominence=.035)
    beat={'duration':duration,'sample_rate':sr,'sample_count':len(y),'audio_sha256':hashlib.sha256(AUDIO.read_bytes()).hexdigest(),
          'bpm':bpm,'phase':phase,'beats':[round(float(t),5) for t in grid],
          'onsets':[{'time':round(float(onset_times[p]),5),'strength':round(float(flux[p]),5)} for p in peaks],
          'method':'STFT positive spectral flux; autocorrelation constrained to 90-120 BPM, global tempo/phase grid refinement. Beat grid is an estimate, vocal words control lyric cues.'}
    DATA.mkdir(exist_ok=True)
    (DATA/'audio.json').write_text(json.dumps(beat,indent=2),encoding='utf-8',newline='\n')
    if not (DATA/'transcription.json').exists():print(json.dumps({'duration':duration,'bpm':bpm,'awaiting':'transcription'}));return
    segments=json.loads((DATA/'transcription.json').read_text())
    observed=[]
    for s in segments:
        for w in s['words']:
            for token in tokens(w['text']):observed.append((token,w['start'],w['end']))
    lines=[]; section=''
    for text in (ROOT/'video/lyrics.txt').read_text().splitlines():
        if text.startswith('['):section=text.strip('[]');continue
        if text.strip():lines.append({'text':text,'section':section,'tokens':tokens(text)})
    expected=[tok for line in lines for tok in line['tokens']]
    matched={}
    for block in SequenceMatcher(None,expected,[w[0] for w in observed],autojunk=False).get_matching_blocks():
        for k in range(block.size):matched[block.a+k]=observed[block.b+k][1:]
    anchors=sorted(matched)
    assert len(anchors)>len(expected)*.45, 'Transcription too different for automatic alignment'
    starts=np.interp(np.arange(len(expected)),anchors,[matched[a][0] for a in anchors])
    ends=np.interp(np.arange(len(expected)),anchors,[matched[a][1] for a in anchors])
    offset=0
    for i,line in enumerate(lines):
        n=len(line.pop('tokens'));word_matches=sum(j in matched for j in range(offset,offset+n))
        line.update(start=round(float(starts[offset]),3),end=round(float(ends[offset+n-1]),3),
                    alignment_confidence=round(word_matches/n,3),alignment='ASR token match/interpolation',id=i)
        offset+=n
    # Final hard HOP cue never expands beyond the master.
    lines[-1]['end']=duration
    (DATA/'lyrics.json').write_text(json.dumps(lines,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps({'duration':duration,'bpm':bpm,'matched_tokens':len(matched),'total_tokens':len(expected),'lines':len(lines)}))

if __name__=='__main__':main()
