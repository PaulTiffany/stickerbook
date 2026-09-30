"""Optional local vocal timing pass; renderer consumes the saved JSON only."""
import json,sys
from pathlib import Path
import soundfile as sf
from scipy.signal import resample_poly
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.stickerbook-runtime/video-deps'))
from faster_whisper import WhisperModel
model=WhisperModel('small.en',device='cpu',compute_type='int8',download_root=str(ROOT/'.stickerbook-runtime/video-models'))
audio,sr=sf.read(ROOT/'assets/video/audio/im-upping-my-phop.wav')
audio=resample_poly(audio.mean(axis=1),16000,sr).astype(np.float32)
segments,info=model.transcribe(audio,beam_size=5,word_timestamps=True,vad_filter=False,initial_prompt="StickerBook. I'm upping my P-hop, P-doom. Omega, Jev, OpenShell. Ray, Aubrey, David, Eagleman, Natasha, Max, Ben, Eliezer.")
out=[]
for s in segments:
 row={'start':s.start,'end':s.end,'text':s.text,'words':[{'text':w.word,'start':w.start,'end':w.end} for w in s.words]}
 out.append(row);print(f'{s.start:.2f} {s.end:.2f} {s.text}',flush=True)
 (ROOT/'video/data/transcription.json').write_text(json.dumps(out,indent=2),encoding='utf-8',newline='\n')
