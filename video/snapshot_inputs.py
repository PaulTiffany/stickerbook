"""Record reproducibility inputs without duplicating the app's asset library."""
import hashlib,json,platform,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    manifest=json.loads((ROOT/'web/static/assets/manifest.json').read_text(encoding='utf-8'))
    paths={ROOT/'web/static/assets/manifest.json',ROOT/'assets/video/audio/im-upping-my-phop.wav',ROOT/'video/lyrics.txt'}
    paths.update((ROOT/'video/input').rglob('*'))
    paths.update(ROOT/'video/data'/name for name in ['audio.json','lyrics.json','timeline.json','proof.json'])
    paths.add(ROOT/'web'/manifest['cover']['variants']['landscape']['src'])
    for page in manifest['pages'].values():paths.add(ROOT/'web'/page['variants']['landscape']['src'])
    for asset in manifest['stickers'].values():paths.update(ROOT/'web'/p for p in asset['sprites'].values())
    data={'python':platform.python_version(),'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],
          'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths) if p.is_file()]}
    (ROOT/'video/data/inputs.json').write_text(json.dumps(data,indent=2),encoding='utf-8',newline='\n')
    print('Recorded',len(data['files']),'reproducibility inputs')

if __name__=='__main__':main()
