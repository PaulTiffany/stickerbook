"""Install reviewed, referenced four-pose sheets generated with image_gen.

Input is a JSON list of {id, source, prompt}; references are a separate JSON
list of {id, page, image_url}. Preflight all originals and crops before writes.
"""
import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np
from scipy import ndimage
from install_cameo_portraits import extract, ROOT

POSES = {
    'anders-sandberg': ['rest', 'wave', 'present', 'think'],
    'david-pearce': ['rest', 'gesture', 'think', 'present'],
    'fm-2030': ['rest', 'wave', 'present', 'think'],
    'giulio-prisco': ['rest', 'cosmic', 'book', 'think'],
    'hans-moravec': ['rest', 'explain', 'think', 'present'],
    'k-eric-drexler': ['rest', 'explain', 'point', 'think'],
    'martine-rothblatt': ['rest', 'wave', 'present', 'celebrate'],
    'robert-ettinger': ['rest', 'present', 'think', 'point'],
    'vernor-vinge': ['rest', 'wave', 'think', 'present'],
}


def extract_quadrants(source):
    """Separate a reviewed 2x2 sheet where neighboring white borders touch."""
    image = Image.open(source).convert('RGBA')
    pieces = {}
    for cell in range(4):
        x, y = cell % 2, cell // 2
        part = image.crop((x*image.width//2, y*image.height//2,
                           (x+1)*image.width//2, (y+1)*image.height//2))
        pixels = np.array(part)
        labels, _ = ndimage.label(pixels[:, :, 3] > 128)
        sizes = np.bincount(labels.ravel())
        major = int(np.argmax(sizes[1:]))+1
        assert sizes[major] > part.width*part.height*.2
        mask = ndimage.binary_dilation(labels == major, iterations=2)
        pixels[~mask, 3] = 0
        portrait = Image.fromarray(pixels)
        pieces[cell] = portrait.crop(portrait.getbbox())
    longest = max(max(p.size) for p in pieces.values())
    canvases = {}
    for cell, portrait in pieces.items():
        portrait = portrait.resize(tuple(round(n*240/longest) for n in portrait.size), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (256, 256))
        canvas.alpha_composite(portrait, ((256-portrait.width)//2, 8))
        canvases[cell] = canvas
    return canvases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('specs', type=Path)
    parser.add_argument('references', type=Path)
    args = parser.parse_args()
    specs = json.loads(args.specs.read_text())
    refs = {r['id']: r for r in json.loads(args.references.read_text())}
    assert len(specs) == 9 and {s['id'] for s in specs} == set(POSES)
    path = ROOT / 'assets/minimax_refresh_manifest.json'
    manifest = json.loads(path.read_text())
    prepared = []
    for spec in specs:
        identifier = spec['id']
        entries = [a for a in manifest['assets'] if a['asset'] == identifier]
        assert {a['pose'] for a in entries} == set(POSES[identifier])
        for entry in entries:
            original, backup = ROOT / entry['original_path'], ROOT / entry['backup_path']
            assert original.read_bytes() == backup.read_bytes(), 'Original changed; review first'
            assert hashlib.sha256(backup.read_bytes()).hexdigest() == entry['original_sha256']
        sheet = ROOT / f'assets/_generated_minimax_refresh/sheets/{identifier}_builtin_portraits.png'
        assert not sheet.exists(), 'Sheet already installed'
        # Giulio's neighboring white die-cut edges touch at the bottom gutter;
        # its subjects/props are separate and the reviewed quadrant split is safe.
        extractor = extract_quadrants if identifier == 'giulio-prisco' else extract
        prepared.append((spec, entries, sheet, extractor(Path(spec['source']))))
    review = Image.new('RGB', (1024, 9*280), '#dbe3eb')
    draw = ImageDraw.Draw(review)
    for row, (spec, entries, sheet, canvases) in enumerate(prepared):
        identifier = spec['id']
        shutil.copy2(spec['source'], sheet)
        mapping = {pose: cell for cell, pose in enumerate(POSES[identifier])}
        archive = ROOT / f'assets/_generated_minimax_refresh/attempts/{identifier}_rejected_crops'
        archive.mkdir(parents=True, exist_ok=True)
        for cell, canvas in canvases.items():
            review.paste(canvas, (cell*256, row*280), canvas)
            draw.text((cell*256+5, row*280+258), identifier+' '+POSES[identifier][cell], fill='black')
        settings = {'provider': 'built-in image_gen', 'model': 'not exposed by tool',
                    'transparent_background': True, 'layout': '2x2 four poses of one person',
                    'reported_cost_usd': None}
        for entry in entries:
            cell = mapping[entry['pose']]
            output = ROOT / entry['cropped_output_path']
            if output.exists():
                assert not (archive / output.name).exists()
                shutil.copy2(output, archive / output.name)
            canvases[cell].save(output)
            raw = output.read_bytes()
            wrapper = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -72 144 144">'
                       '<image x="-72" y="-72" width="144" height="144" href="data:image/png;base64,'+
                       base64.b64encode(raw).decode('ascii')+'"/></svg>\n')
            (ROOT / entry['original_path']).write_bytes(wrapper.encode())
            entry.update(generated_sheet_path=sheet.relative_to(ROOT).as_posix(),
                         sheet_id=sheet.stem, cell=cell, prompt=spec['prompt'],
                         generation_settings=settings, status='replaced', replacement_succeeded=True,
                         output_sha256=hashlib.sha256(raw).hexdigest(),
                         notes='Referenced built-in generation, visually reviewed. Existing pose names/clips retained; source alpha and a shared four-pose scale preserved. Historical reference resolution limits exact likeness.')
        manifest.setdefault('builtin_generated_sheets', []).append({
            'id': sheet.stem, 'asset': identifier, 'path': sheet.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(sheet.read_bytes()).hexdigest(), 'prompt': spec['prompt'],
            'generation_settings': settings, 'identity_reference': {
                'page': refs[identifier]['page'], 'image_url': refs[identifier]['image_url']},
            'style_reference': 'assets/_generated_minimax_refresh/sheets/david-orban_user_portraits.png',
            'cell_to_pose': mapping})
    manifest['summary'].update(replaced_stickers=76, replaced_pose_files=304, retained_stickers=[],
                               builtin_generated_sheet_count=9, builtin_generation_cost_usd=None)
    manifest['status'] = 'replacement-complete'
    path.write_bytes((json.dumps(manifest, indent=2)+'\n').encode())
    review.save(ROOT / 'assets/_generated_minimax_refresh/review/builtin-cameos.png')
    print(json.dumps({'installed_stickers': 9, 'installed_poses': 36, 'total_pose_files': 304}))


if __name__ == '__main__':
    main()
