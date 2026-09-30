"""Install Paul's supplied four-portrait sheet without generating new likenesses."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    manifest_path = ROOT / 'assets/minimax_refresh_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = [a for a in manifest['assets'] if a['asset']=='paul-tiffany']
    for entry in entries:
        original, backup = ROOT / entry['original_path'], ROOT / entry['backup_path']
        assert original.read_bytes() == backup.read_bytes(), 'Original changed; review before replacing'
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == entry['original_sha256']
    image = Image.open(args.source).convert('RGBA')
    rgba = np.array(image)
    labels, count = ndimage.label(rgba[:,:,3] > 128)
    sizes = np.bincount(labels.ravel())
    major = np.argsort(sizes[1:])[-4:]+1
    assert len(major)==4 and min(sizes[major])>image.width*image.height*.05
    pieces = {}
    boxes = ndimage.find_objects(labels)
    for label in major:
        box = boxes[label-1]
        cx, cy = (box[1].start+box[1].stop)/2, (box[0].start+box[0].stop)/2
        cell = int(cx > image.width/2)+2*int(cy > image.height/2)
        # Preserve source edge alpha, excluding disconnected background flecks.
        mask = ndimage.binary_dilation(labels==label, iterations=2)
        pixels = rgba.copy()
        pixels[~mask,3] = 0
        portrait = Image.fromarray(pixels)
        pieces[cell] = portrait.crop(portrait.getbbox())
    assert set(pieces)=={0,1,2,3}
    sheet_path = ROOT / 'assets/_generated_minimax_refresh/sheets/paul-tiffany_user_portraits.png'
    assert not sheet_path.exists(), 'Supplied sheet already installed'
    shutil.copy2(args.source, sheet_path)
    archive = ROOT / 'assets/_generated_minimax_refresh/attempts/paul-tiffany_rejected_crops'
    archive.mkdir(parents=True, exist_ok=True)
    longest = max(max(p.size) for p in pieces.values())
    mapping = {'rest':0, 'explain':1, 'chalkboard':2, 'poster':3}
    for entry in entries:
        cell = mapping[entry['pose']]
        portrait = pieces[cell]
        scale = 240/longest
        portrait = portrait.resize(tuple(round(n*scale) for n in portrait.size), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA',(256,256))
        canvas.alpha_composite(portrait, ((256-portrait.width)//2,8))
        output = ROOT / entry['cropped_output_path']
        if output.exists():
            shutil.copy2(output, archive / output.name)
        canvas.save(output)
        raw = output.read_bytes()
        encoded = base64.b64encode(raw).decode('ascii')
        wrapper = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -72 144 144">'
            '<image x="-72" y="-72" width="144" height="144" href="data:image/png;base64,'+
            encoded+'"/></svg>\n')
        (ROOT / entry['original_path']).write_bytes(wrapper.encode())
        entry.update(generated_sheet_path=sheet_path.relative_to(ROOT).as_posix(),
            sheet_id='paul-tiffany_user_portraits', cell=cell, prompt=None,
            generation_settings={'provider':'user-supplied artwork','model':None},
            status='replaced', replacement_succeeded=True,
            output_sha256=hashlib.sha256(raw).hexdigest(),
            notes='User-supplied Paul portraits. rest=neutral; explain=open hands; chalkboard=thinking/notebook; poster=wave. Legacy pose names/clips preserved; source alpha retained with disconnected flecks removed.')
    manifest['supplied_sheets'] = manifest.get('supplied_sheets',[])+[{
        'id':'paul-tiffany_user_portraits', 'path':sheet_path.relative_to(ROOT).as_posix(),
        'source_filename':args.source.name, 'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'provenance':'Supplied by Paul for Paul Tiffany stickers; no new inference', 'cell_to_pose':mapping}]
    summary = manifest['summary']
    summary['replaced_stickers'] += 1
    summary['replaced_pose_files'] += 4
    summary['retained_stickers'].remove('paul-tiffany')
    manifest_path.write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
    print(json.dumps({'installed':'paul-tiffany','poses':mapping,'new_inference_cost':0}))


if __name__ == '__main__':
    main()
