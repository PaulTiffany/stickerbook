"""Generate one staged sheet using the local OpenRouter credential, never log it."""
import argparse
import base64
import json
import os
from pathlib import Path
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'openai/gpt-image-2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('sheet_id', help='Sheet id, or all to resume pending sheets')
    parser.add_argument('--refine', action='store_true', help='Regenerate non-person poses from matching family reference')
    args = parser.parse_args()
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        env = ROOT / '.env.docker-llm-local'
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith('OPENROUTER_API_KEY='):
                    key = line.partition('=')[2].strip().strip('\"\'')
    if not key:
        raise SystemExit('Local OpenRouter credential unavailable')
    manifest_path = ROOT / 'assets/minimax_refresh_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if args.sheet_id == 'all':
        if args.refine:
            archive = ROOT / 'assets/_generated_minimax_refresh/attempts'
            archive.mkdir(exist_ok=True)
            for s in manifest['sheets']:
                if s['family'] == 'people' or s['id'].endswith('_pose_01'):
                    continue
                destination = ROOT / f"assets/_generated_minimax_refresh/sheets/{s['id']}.png"
                if destination.exists() and not s.get('matched_family_reference'):
                    destination.rename(archive / (s['id'] + '_first_attempt.png'))
                    s.setdefault('attempts', []).append({k: s[k] for k in
                        ['status', 'model', 'cost_usd', 'latency_seconds'] if k in s})
                    s['cost_usd'] = None
            manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
        pending = [s for s in manifest['sheets'] if not (ROOT / f"assets/_generated_minimax_refresh/sheets/{s['id']}.png").exists()]
        if args.refine:
            pending = [s for s in pending if s['family'] != 'people']
        # Workers perform inference only. A single writer owns manifest updates.
        with ThreadPoolExecutor(max_workers=3) as executor:
            jobs = {executor.submit(generate, s, key, args.refine): s for s in pending}
            for job in as_completed(jobs):
                sheet = jobs[job]
                try:
                    metadata = job.result()
                    sheet.update(metadata)
                except Exception as exc:
                    metadata = {'status': 'generation-failed', 'error_type': type(exc).__name__}
                    if hasattr(exc, 'code'):
                        metadata['http_status'] = exc.code
                    sheet.update(metadata)
                record(manifest, sheet)
                manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
                print(json.dumps({'sheet': sheet['id'], **{k:v for k,v in metadata.items()
                    if k not in ['generation_prompt', 'reference_path']}}), flush=True)
        return
    sheet = next(s for s in manifest['sheets'] if s['id'] == args.sheet_id)
    sheet.update(generate(sheet, key))
    record(manifest, sheet)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'sheet': sheet['id'], **{k: sheet[k] for k in ['model', 'cost_usd', 'latency_seconds']}}))


def record(manifest, sheet):
    for asset in manifest['assets']:
        if asset['sheet_id'] == sheet['id']:
            asset['generation_settings'] = {'provider': 'OpenRouter', 'model': MODEL,
                'n': 1, 'aspect_ratio': '1:1', 'quality': 'low', 'background': 'opaque',
                'style_reference': sheet.get('reference_path',
                    'assets/_generated_minimax_refresh/sheets/animals_01_pose_01.png')}
            asset['status'] = sheet['status']
            asset['prompt'] = sheet.get('generation_prompt', sheet['prompt'])
    manifest['status'] = 'generation-in-progress'


def generate(sheet, key, refine=False):
    destination = ROOT / f"assets/_generated_minimax_refresh/sheets/{sheet['id']}.png"
    if destination.exists():
        raise SystemExit('Sheet already exists; refusing to overwrite')
    settings = {'model': MODEL, 'n': 1, 'aspect_ratio': '1:1',
                'quality': 'low', 'background': 'opaque'}
    reference = ROOT / 'assets/_generated_minimax_refresh/sheets/animals_01_pose_01.png'
    payload = {**settings, 'prompt': sheet['prompt'] +
        ' No scenery or perches. Pose names describe actual body poses, not labels. '
        'For wings-up raise wings; wings-down lower wings; crouch squat low; hop leap; '
        'land settle; alert raise head. Preserve distinct poses. Reference supplies style only, '
        'not subjects or poses. Keep all four sticker silhouettes inside their own cells.'}
    if refine:
        reference = ROOT / ('assets/_generated_minimax_refresh/sheets/' +
            sheet['id'].rsplit('_pose_',1)[0] + '_pose_01.png')
        payload['prompt'] = sheet['prompt'] + (
            ' The reference is the SAME four subjects in the SAME cell positions. '
            'Keep EXACTLY their designs, colors, markings, facial features, outfits, '
            'proportions, and art style. Change ONLY body pose according to the listed '
            'pose for each cell. Never redesign a subject. Wings-up means wings raised; '
            'wings-down means lowered; crouch squat; hop leap. No scenery, perches, '
            'borders, labels, or sheet grid. Preserve transparent-ready white background.')
    if reference.exists() and sheet['id'] != 'animals_01_pose_01':
        payload['input_references'] = [{'type': 'image_url', 'image_url': {
            'url': 'data:image/png;base64,' + base64.b64encode(reference.read_bytes()).decode()}}]
    request = urllib.request.Request('https://openrouter.ai/api/v1/images',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read(24 * 1024 * 1024 + 1)
    if len(raw) > 24 * 1024 * 1024:
        raise ValueError('Oversized image response')
    result = json.loads(raw)
    image_bytes = base64.b64decode(result['data'][0]['b64_json'], validate=True)
    from PIL import Image
    from io import BytesIO
    image = Image.open(BytesIO(image_bytes))
    image.load()
    if image.width != image.height or image.width % 2 or image.width > 4096:
        raise ValueError('Invalid sheet dimensions')
    image.save(destination, format='PNG')
    cost = result.get('usage', {}).get('cost')
    return {'status': 'generated-awaiting-crop-review', 'model': MODEL,
            'cost_usd': cost, 'latency_seconds': round(time.monotonic()-start, 2),
            'dimensions': list(image.size), 'generation_prompt': payload['prompt'],
            'matched_family_reference': refine, 'reference_path': reference.relative_to(ROOT).as_posix()}


if __name__ == '__main__':
    main()
