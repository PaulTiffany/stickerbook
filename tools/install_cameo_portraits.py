"""Install supplied cameo sheets without inventing likenesses or clip names."""
from sprite_refresh_paths import REFRESH_MANIFEST
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
# Cell order: top left, top right, bottom left, bottom right.
SHEETS = [
    ('DavidOrban', 'david-orban', {'rest':0,'explain':1,'point':2,'wave':3}),
    ('BenGoertzel', 'ben-goertzel', {'rest':0,'gesture':1,'think':2,'celebrate':3}),
    ('AubreyDeGray', 'aubrey-de-grey', {'rest':3,'wave':0,'explain':1,'think':2}),
    ('RayKurzweil', 'ray-kurzweil', {'rest':0,'present':1,'point':2,'think':0}),
    ('DavidEagleman', 'david-eagleman', {'rest':0,'explain':1,'present':3,'think':2}),
    ('NicholasBostrom', 'nick-bostrom', {'rest':2,'explain':1,'think':0,'present':3}),
    ('MaxMore', 'max-more', {'rest':0,'wave':1,'present':2,'think':3}),
    ('NatashaVitaMore', 'natasha-vita-more', {'rest':0,'wave':1,'present':2,'think':3}),
    ('EliezerYudkowsky', 'eliezer-yudkowsky', {'rest':0,'explain':1,'think':2,'present':3}),
]


def extract(source):
    image = Image.open(source).convert('RGBA')
    rgba = np.array(image)
    opaque = rgba[:,:,3].min()==255
    # On opaque sheets, dark outlines separate portraits even where their pale
    # drop shadows touch. Enclosed light shirts/skin remain inside the mask.
    core = ((np.min(rgba[:,:,:3],axis=2)<210) if opaque else
            (rgba[:,:,3]>128))
    labels, count = ndimage.label(core)
    sizes = np.bincount(labels.ravel())
    major = np.argsort(sizes[1:])[-4:]+1
    assert len(major)==4 and min(sizes[major])>image.width*image.height*.05
    boxes = ndimage.find_objects(labels)
    pieces = {}
    for label in major:
        box = boxes[label-1]
        cx, cy = (box[1].start+box[1].stop)/2, (box[0].start+box[0].stop)/2
        cell = int(cx>image.width/2)+2*int(cy>image.height/2)
        assert cell not in pieces, 'Ambiguous sheet layout; inspect before installing'
        mask = labels==label
        if opaque:
            mask = ndimage.binary_fill_holes(mask)
        mask = ndimage.binary_dilation(mask, iterations=10 if opaque else 2)
        pixels = rgba.copy()
        pixels[~mask,3] = 0
        portrait = Image.fromarray(pixels)
        pieces[cell] = portrait.crop(portrait.getbbox())
    assert set(pieces)=={0,1,2,3}
    longest = max(max(p.size) for p in pieces.values())
    canvases = {}
    for cell, portrait in pieces.items():
        scale = 240/longest
        portrait = portrait.resize(tuple(round(n*scale) for n in portrait.size), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA',(256,256))
        canvas.alpha_composite(portrait, ((256-portrait.width)//2,8))
        canvases[cell] = canvas
    return canvases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    path = REFRESH_MANIFEST
    manifest = json.loads(path.read_text())
    prepared = []
    # Preflight every sheet before changing any active files.
    for filename, identifier, mapping in SHEETS:
        source = args.directory / (filename+'.png')
        entries = [a for a in manifest['assets'] if a['asset']==identifier]
        assert {a['pose'] for a in entries}==set(mapping)
        for entry in entries:
            original, backup = ROOT / entry['original_path'], ROOT / entry['backup_path']
            assert original.read_bytes()==backup.read_bytes(), 'Original changed; review before replacing'
            assert hashlib.sha256(backup.read_bytes()).hexdigest()==entry['original_sha256']
        prepared.append((source,identifier,mapping,entries,extract(source)))
    review = Image.new('RGB',(1024,9*280),'#dbe3eb')
    draw = ImageDraw.Draw(review)
    for row, (source,identifier,mapping,entries,canvases) in enumerate(prepared):
        sheet_id = identifier+'_user_portraits'
        sheet = ROOT / f'assets/_generated_sprite_refresh/sheets/{sheet_id}.png'
        assert not sheet.exists(), 'Supplied sheet already installed'
        shutil.copy2(source,sheet)
        archive = ROOT / f'assets/_generated_sprite_refresh/attempts/{identifier}_rejected_crops'
        archive.mkdir(parents=True,exist_ok=True)
        for cell, canvas in canvases.items():
            review.paste(canvas,(cell*256,row*280),canvas)
            draw.text((cell*256+5,row*280+258),identifier+' cell '+str(cell),fill='black')
        for entry in entries:
            cell = mapping[entry['pose']]
            output = ROOT / entry['cropped_output_path']
            if output.exists():
                shutil.copy2(output,archive / output.name)
            canvases[cell].save(output)
            raw = output.read_bytes()
            wrapper = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -72 144 144">'
                '<image x="-72" y="-72" width="144" height="144" href="data:image/png;base64,'+
                base64.b64encode(raw).decode('ascii')+'"/></svg>\n')
            (ROOT / entry['original_path']).write_bytes(wrapper.encode())
            note = 'User-supplied portraits; existing frame names/clips retained. Source alpha preserved or opaque background isolated using portrait outlines.'
            if identifier=='ray-kurzweil':
                note += ' No thinking portrait supplied: think uses calm cell 0; celebration cell 3 staged separately.'
            entry.update(generated_sheet_path=sheet.relative_to(ROOT).as_posix(),
                sheet_id=sheet_id,cell=cell,prompt=None,
                generation_settings={'provider':'user-supplied artwork','model':None},
                status='replaced',replacement_succeeded=True,
                output_sha256=hashlib.sha256(raw).hexdigest(),notes=note)
        if identifier=='ray-kurzweil':
            canvases[3].save(ROOT / 'assets/_generated_sprite_refresh/cropped/ray-kurzweil/celebration-unused.png')
        manifest.setdefault('supplied_sheets',[]).append({
            'id':sheet_id,'path':sheet.relative_to(ROOT).as_posix(),'source_filename':source.name,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'provenance':'User-supplied cameo artwork; no new inference','cell_to_pose':mapping})
        manifest['summary']['retained_stickers'].remove(identifier)
    manifest['summary']['replaced_stickers'] += len(prepared)
    manifest['summary']['replaced_pose_files'] += len(prepared)*4
    path.write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
    review.save(ROOT / 'assets/_generated_sprite_refresh/review/supplied-cameos.png')
    print(json.dumps({'installed_stickers':len(prepared),'installed_poses':len(prepared)*4,'new_inference_cost':0}))


if __name__=='__main__':
    main()
