"""Verify real evidence, deterministic rendering and the final media contract."""
import hashlib,json,math,subprocess
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image
import render

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def check_sources():
    inputs=json.loads((HERE/'data/inputs.json').read_text())
    for record in inputs['files']:
        assert hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()==record['sha256'], record['path']
    audio=json.loads((HERE/'data/audio.json').read_text())
    assert hashlib.sha256((ROOT/'assets/video/audio/im-upping-my-phop.wav').read_bytes()).hexdigest()==audio['audio_sha256']
    timeline=json.loads((HERE/'data/timeline.json').read_text())
    assert all(timeline[i]['start']<=timeline[i+1]['start'] for i in range(len(timeline)-1))
    source=[line for line in (HERE/'lyrics.txt').read_text().splitlines() if line and not line.startswith('[')]
    assert [s['lyric'] for s in timeline]==source
    assert all(0<=s['start']<=s['end']<=audio['duration'] for s in timeline)
    assert set(s['world'] for s in timeline)==set(render.PAGES)
    proof=json.loads((HERE/'data/proof.json').read_text())
    double=next(p for p in proof['proofs'] if p['id']=='double-tap')
    accepted=[e for e in double['audit']['events'] if e['kind']=='receipt' and e['receipt']['accepted']]
    assert any(e['receipt']['action']=='move-sticker' for e in accepted)
    assert any(e['receipt']['action']=='animate-own-sticker' for e in accepted)
    assert all(e['receipt']['translatedBy'] is None for e in accepted)
    assert all(e['receipt']['selectedBy']=='agent:jev-visual-1' for e in accepted)
    human=next(p for p in proof['proofs'] if p['id']=='human-hand')
    assert human['move']['receipt']['accepted']
    assert any(e['kind']=='stop' and e['reason']=='child-grabbed' for e in human['audit']['events'])
    isolation=next(p for p in proof['proofs'] if p['id']=='page-isolation')
    assert isolation['space']['state']['stickers']==[]
    assert isolation['farm']['stickers']==isolation['restored']['state']['stickers']
    language=next(p for p in proof['proofs'] if p['id']=='language')
    assert language['response']['ok'] and language['response']['jev']['goal']['subject']==double['subject']
    hashes={}
    for t in [.8,47.6,76.5,92.8,102.7,152.4,179.65]:
        a=render.render(t);b=render.render(t)
        assert a.size==(1920,1080) and a.tobytes()==b.tobytes()
        hashes[str(t)]=hashlib.sha256(a.tobytes()).hexdigest()
    return audio,hashes,accepted,inputs

def main():
    audio,hashes,accepted,inputs=check_sources()
    path=HERE/'output/stickerbook-phop.mp4'
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    a=next(s for s in info['streams'] if s['codec_type']=='audio')
    assert v['codec_name']=='h264' and (v['width'],v['height'])==(1920,1080) and v['r_frame_rate']=='30/1'
    assert a['codec_name']=='aac'
    for duration in [v['duration'],a['duration'],info['format']['duration']]:assert abs(float(duration)-audio['duration'])<.00002
    subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True)
    encoded_frame_error={}
    for t in [47.6,76.5,92.8,102.7,152.4]:
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-c:v','png','-f','image2pipe','pipe:1'])
        decoded=np.asarray(Image.open(BytesIO(raw)).convert('RGB'),dtype=np.float32)
        reference=np.asarray(render.render(t),dtype=np.float32)
        rmse=float(np.sqrt(np.mean((decoded-reference)**2)))
        assert rmse<8, f'Encoded frame differs from scene at {t}: {rmse}'
        encoded_frame_error[str(t)]=round(rmse,4)
    report={'status':'passed','duration_seconds':audio['duration'],'resolution':[1920,1080],
            'fps':v['r_frame_rate'],'video_frames':int(v['nb_frames']),'video_codec':v['codec_name'],'audio_codec':a['codec_name'],
            'mp4_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'accepted_double_tap_receipts':len(accepted),
            'real_proof_moments':4,'reproducibility_inputs_verified':len(inputs['files']),'deterministic_frame_sha256':hashes,'full_decode':'passed',
            'encoded_frame_rmse':encoded_frame_error,
            'source_lyrics':'unchanged user supplied text','uncertain_timing':'editorial windows marked in timeline'}
    (HERE/'data/verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
