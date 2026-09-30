"""Container-owned image inference returns raster drafts, never commands."""
import base64
from io import BytesIO
import json
import os
from threading import Lock
import urllib.error
import urllib.request

IMAGE_MODEL = 'openai/gpt-image-1-mini'
GATE = Lock()


def available():
    return bool(os.environ.get('OPENROUTER_API_KEY', '').strip())


def _png(image):
    buffer = BytesIO(); image.save(buffer, format='PNG')
    raw = buffer.getvalue()
    if len(raw) > 3 * 1024 * 1024:
        raise ValueError('image-draft-too-large')
    return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')


def _generate(prompt, *, transparent=False, ratio='1:1', reference=None):
    from PIL import Image
    body = {'model': IMAGE_MODEL, 'prompt': prompt, 'n': 1,
            'aspect_ratio': ratio, 'quality': 'medium', 'output_format': 'png',
            'background': 'transparent' if transparent else 'opaque'}
    if reference:
        body['input_references'] = [{'type': 'image_url', 'image_url': {'url': reference}}]
    request = urllib.request.Request('https://openrouter.ai/api/v1/images',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY']})
    with urllib.request.urlopen(request, timeout=150) as response:
        raw = response.read(24 * 1024 * 1024 + 1)
    if len(raw) > 24 * 1024 * 1024:
        raise ValueError('image-provider-response-too-large')
    result = json.loads(raw)
    image = Image.open(BytesIO(base64.b64decode(result['data'][0]['b64_json'], validate=True)))
    if image.format != 'PNG' or image.width > 4096 or image.height > 4096:
        raise ValueError('invalid-image-provider-response')
    image.load()
    return image.convert('RGBA')


def create(raw):
    if (not isinstance(raw, dict) or set(raw) != {'kind', 'prompt'} or
            raw['kind'] not in ('sticker', 'page') or not isinstance(raw['prompt'], str) or
            not 1 <= len(raw['prompt'].strip()) <= 500):
        return {'ok': False, 'error': 'invalid-creator-request'}
    if not available():
        return {'ok': False, 'error': 'image-provider-unavailable'}
    if not GATE.acquire(blocking=False):
        return {'ok': False, 'error': 'image-creator-busy'}
    try:
        from PIL import Image, ImageOps
        prompt = raw['prompt'].strip()
        if raw['kind'] == 'sticker':
            sheet = _generate('A four-frame animation sprite sheet for a child stickerbook. '
                'Exactly 2 columns and 2 rows of equal square cells. SAME character, same scale, '
                'same center and viewing angle in all four cells, four successive distinct poses of one '
                'gentle looping animation. Entire character fits each cell with generous clear margin. '
                'Transparent background. No text, borders, shadows, scenery, or extra characters. '
                'Reading order: top left, top right, bottom left, bottom right. Character: ' + prompt,
                transparent=True)
            if sheet.width != sheet.height or sheet.width % 2:
                raise ValueError('invalid-sprite-sheet-layout')
            size = sheet.width // 2
            frames = [_png(sheet.crop((x*size, y*size, (x+1)*size, (y+1)*size)).resize((256,256), Image.Resampling.LANCZOS))
                      for y in range(2) for x in range(2)]
            return {'ok': True, 'draft': {'kind': 'sticker', 'name': prompt[:80],
                'frames': frames, 'summary': 'Four animation frames ready', 'model': IMAGE_MODEL}}
        landscape = _generate('Illustrate a child stickerbook background, with open space for movable stickers. '
            'No lettering. World: ' + prompt, ratio='3:2')
        portrait = _generate('Recompose this SAME stickerbook world as a portrait page, keeping its important '
            'landmarks and visual style. No lettering. World: ' + prompt, ratio='2:3', reference=_png(landscape))
        return {'ok': True, 'draft': {'kind': 'page', 'name': prompt[:80], 'model': IMAGE_MODEL,
            'summary': 'Landscape and portrait page artwork ready', 'images': {
                'landscape': _png(ImageOps.fit(landscape, (1916,717))),
                'portrait': _png(ImageOps.fit(portrait, (941,1574)))}}}
    except urllib.error.HTTPError as exc:
        return {'ok': False, 'error': 'image-provider-http-error', 'status': exc.code}
    except (OSError, TimeoutError):
        return {'ok': False, 'error': 'image-provider-timeout-or-unavailable'}
    except (ValueError, KeyError, IndexError, TypeError):
        return {'ok': False, 'error': 'invalid-image-provider-response'}
    finally:
        GATE.release()
