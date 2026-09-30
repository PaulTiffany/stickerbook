"""Verify backups, installed raster interfaces, and optional live static serving."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
from PIL import Image
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'assets/minimax_refresh_manifest.json').read_text())
    canonical = ROOT / manifest['source_manifest']
    assert canonical.read_bytes() == (ROOT / manifest['source_manifest_backup']).read_bytes()
    installed = 0
    for asset in manifest['assets']:
        backup = ROOT / asset['backup_path']
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == asset['original_sha256']
        original = ROOT / asset['original_path']
        if asset['replacement_succeeded']:
            svg = ET.parse(original).getroot()
            assert svg.get('viewBox') == '-72 -72 144 144'
            im = svg.find('{http://www.w3.org/2000/svg}image')
            prefix = 'data:image/png;base64,'
            assert im.get('href').startswith(prefix)
            data = base64.b64decode(im.get('href')[len(prefix):], validate=True)
            assert data == (ROOT / asset['cropped_output_path']).read_bytes()
            image = Image.open(BytesIO(data))
            image.load()
            assert image.mode == 'RGBA' and image.size == (256,256)
            assert image.getchannel('A').getextrema() == (0,255)
            installed += 1
        else:
            assert original.read_bytes() == backup.read_bytes()
    source = json.loads(canonical.read_text())
    for identifier, definition in source['stickers'].items():
        for clip in definition['clips'].values():
            assert all(frame in definition['sprites'] for frame in clip['frames'])
    urls = [a['original_path'].removeprefix('web/') for a in manifest['assets']]
    if args.base_url:
        def fetch(relative):
            with urllib.request.urlopen(args.base_url.rstrip('/')+'/'+relative, timeout=20) as response:
                assert response.status == 200
                assert response.headers.get_content_type() == 'image/svg+xml'
                assert response.read() == (ROOT / 'web' / relative).read_bytes()
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(fetch, urls))
    print(json.dumps({'backups_verified': len(manifest['assets']), 'installed_rasters_verified': installed,
                      'unchanged_pose_files': len(manifest['assets'])-installed,
                      'live_image_urls_verified': len(urls) if args.base_url else 0,
                      'canonical_manifest_unchanged': True}))


if __name__ == '__main__':
    main()
