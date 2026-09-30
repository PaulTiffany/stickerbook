"""Split reviewed-layout sheets; isolate only background connected to cell edges."""
import json
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]


def isolate(image):
    rgba = np.array(image.convert('RGBA'))
    white = np.min(rgba[:, :, :3], axis=2) >= 240
    border = np.zeros(white.shape, dtype=bool)
    # Seed beyond faint sheet guides, which can otherwise enclose a white box.
    border[:24, :] = border[-24:, :] = True
    border[:, :24] = border[:, -24:] = True
    exterior = ndimage.binary_propagation(border & white, mask=white)
    rgba[exterior, 3] = 0
    # Some generations draw faint cell guides. Remove tiny disconnected marks,
    # while retaining the large connected sticker and enclosed white details.
    labels, count = ndimage.label(rgba[:, :, 3] > 0)
    sizes = np.bincount(labels.ravel())
    if count:
        keep = sizes >= max(100, sizes[1:].max() * .005)
        keep[0] = False
        for label, box in enumerate(ndimage.find_objects(labels), 1):
            if box and (box[0].start < 12 or box[1].start < 12 or
                        box[0].stop > image.height-12 or box[1].stop > image.width-12):
                if label == int(np.argmax(sizes[1:])) + 1:
                    if box[0].start == 0 or box[1].start == 0 or box[0].stop == image.height or box[1].stop == image.width:
                        raise ValueError('Main silhouette is clipped at cell boundary; requires manual review')
                    continue
                keep[label] = False
        rgba[~keep[labels], 3] = 0
    result = Image.fromarray(rgba)
    bbox = result.getbbox()
    if not bbox or np.count_nonzero(rgba[:, :, 3]) < image.width * image.height * .025:
        raise ValueError('Empty or implausibly small sticker')
    if not (bbox[0] > 0 and bbox[1] > 0 and bbox[2] < image.width and bbox[3] < image.height):
        raise ValueError('Silhouette touches cell boundary; requires manual review')
    return result, bbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true', help='Leave manifest unchanged during generation')
    parser.add_argument('--only', help='Restage a single asset without rebuilding review montages')
    args = parser.parse_args()
    path = ROOT / 'assets/minimax_refresh_manifest.json'
    manifest = json.loads(path.read_text())
    prepared = {}
    for asset in manifest['assets']:
        if args.only and asset['asset'] != args.only:
            continue
        sheet = ROOT / asset['generated_sheet_path']
        if not sheet.exists():
            continue
        try:
            image = Image.open(sheet).convert('RGBA')
            side = image.width // 2
            x, y = asset['cell'] % 2 * side, asset['cell'] // 2 * side
            # Generated poses occasionally extend into the otherwise empty
            # inter-cell gutter. Include a bounded gutter; component filtering
            # rejects fragments of neighboring subjects at its outer boundary.
            gutter = 80 if asset['asset'] == 'rocket' else 48
            result, bbox = isolate(image.crop((max(0,x-gutter), max(0,y-gutter),
                min(image.width,x+side+gutter), min(image.height,y+side+gutter))))
            prepared.setdefault(asset['asset'], []).append((asset, result, bbox))
        except (ValueError, OSError) as exc:
            asset.update(status='crop-failed', notes=str(exc))
    for identifier, frames in prepared.items():
        # Shared union bounds and padding keep the body aligned between poses.
        bounds = [min(f[2][0] for f in frames), min(f[2][1] for f in frames),
                  max(f[2][2] for f in frames), max(f[2][3] for f in frames)]
        for asset, image, _ in frames:
            pad = 12
            output = image.crop((bounds[0]-pad, bounds[1]-pad, bounds[2]+pad, bounds[3]+pad))
            output.thumbnail((240, 240), Image.Resampling.LANCZOS)
            canvas = Image.new('RGBA', (256, 256))
            canvas.alpha_composite(output, ((256-output.width)//2, (256-output.height)//2))
            destination = ROOT / asset['cropped_output_path']
            destination.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(destination)
            asset.update(status='cropped-awaiting-visual-review', crop_union_bounds=bounds,
                         notes='Exterior white removed; interior whites and sticker outline retained. Shared pose bounds.')
    review = ROOT / 'assets/_generated_sprite_refresh/review'
    review.mkdir(exist_ok=True)
    if args.only:
        prepared = {}
    for pose in range(4):
        assets = [frames[pose][0] for frames in prepared.values() if len(frames)>pose]
        for offset in range(0, len(assets), 16):
            montage = Image.new('RGB', (800, 880), '#dbe3eb')
            draw = ImageDraw.Draw(montage)
            for index, asset in enumerate(assets[offset:offset+16]):
                im = Image.open(ROOT / asset['cropped_output_path']).convert('RGBA')
                im.thumbnail((190, 190))
                x, y = (index%4)*200, (index//4)*220
                montage.paste(im, (x+5,y+5), im)
                draw.text((x+5,y+198), asset['asset'], fill='black')
                draw.text((x+5,y+210), asset['pose'], fill='black')
            montage.save(review / f'pose_{pose+1}_{offset//16+1:02d}.jpg')
    if not args.preview:
        path.write_text(json.dumps(manifest, indent=2)+'\n')
    from collections import Counter
    print(json.dumps(Counter(a['status'] for a in manifest['assets'])))


if __name__ == '__main__':
    main()
