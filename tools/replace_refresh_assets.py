"""Install visually reviewed crops behind the existing SVG path interface."""
from sprite_refresh_paths import REFRESH_MANIFEST
import argparse
import base64
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reviewed', action='store_true', required=True)
    parser.add_argument('--exclude', nargs='*', default=[])
    args = parser.parse_args()
    path = REFRESH_MANIFEST
    manifest = json.loads(path.read_text())
    groups = {}
    for asset in manifest['assets']:
        groups.setdefault(asset['asset'], []).append(asset)
    installed = 0
    for identifier, frames in groups.items():
        if identifier in args.exclude or any(a['status'] != 'cropped-awaiting-visual-review' for a in frames):
            for asset in frames:
                asset['notes'] += ' Entire sticker kept original: excluded or incomplete pose set.'
            continue
        # Validate the whole character before replacing any of its poses.
        for asset in frames:
            original = ROOT / asset['original_path']
            backup = ROOT / asset['backup_path']
            if hashlib.sha256(original.read_bytes()).hexdigest() != asset['original_sha256']:
                raise ValueError(f'Active asset changed since backup: {original}')
            if hashlib.sha256(backup.read_bytes()).hexdigest() != asset['original_sha256']:
                raise ValueError(f'Invalid backup: {backup}')
            image = Image.open(ROOT / asset['cropped_output_path'])
            image.load()
            if image.mode != 'RGBA' or image.size != (256,256) or image.getchannel('A').getextrema() != (0,255):
                raise ValueError('Crop must be 256px RGBA with real transparent background')
        for asset in frames:
            crop = ROOT / asset['cropped_output_path']
            encoded = base64.b64encode(crop.read_bytes()).decode('ascii')
            # A self-contained SVG avoids new runtime URLs and preserves clip,
            # viewBox, MIME type, filename, and existing renderer contracts.
            wrapper = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -72 144 144">'
                       '<image x="-72" y="-72" width="144" height="144" '
                       'href="data:image/png;base64,' + encoded + '"/></svg>\n')
            (ROOT / asset['original_path']).write_bytes(wrapper.encode('utf-8'))
            asset.update(status='replaced', replacement_succeeded=True,
                         output_sha256=hashlib.sha256(crop.read_bytes()).hexdigest(),
                         notes=asset['notes'] + ' Visually reviewed; embedded PNG in original SVG interface.')
            installed += 1
    manifest['status'] = 'replacement-complete-with-skips' if installed < len(manifest['assets']) else 'replacement-complete'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'replaced_pose_files': installed, 'unchanged_pose_files': len(manifest['assets'])-installed}))


if __name__ == '__main__':
    main()
