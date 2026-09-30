"""Bounded observational JPEGs. Pixels are never world facts or commands."""
import base64
import struct

MAX_IMAGE_CHARS = 180000
MAX_VISUAL_BODY = 240 * 1024


def clean_visual(raw, *, page=None, revision=None):
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {'page', 'revision', 'width', 'height', 'image'}:
        raise ValueError('invalid-visual-context')
    if not isinstance(raw['page'], str) or len(raw['page']) > 80 or (page is not None and raw['page'] != page):
        raise ValueError('visual-page-mismatch')
    if type(raw['revision']) is not int or raw['revision'] < 0 or (revision is not None and raw['revision'] > revision):
        raise ValueError('invalid-visual-revision')
    if any(type(raw[k]) is not int or not 1 <= raw[k] <= 1024 for k in ('width', 'height')):
        raise ValueError('invalid-visual-dimensions')
    image = raw['image']
    prefix = 'data:image/jpeg;base64,'
    if not isinstance(image, str) or len(image) > MAX_IMAGE_CHARS or not image.startswith(prefix):
        raise ValueError('invalid-visual-image')
    try:
        data = base64.b64decode(image[len(prefix):], validate=True)
        if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
            raise ValueError()
        offset = 2
        dimensions = None
        while offset < len(data):
            if data[offset] != 255:
                raise ValueError()
            while data[offset] == 255:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker == 0xDA:
                break
            size = struct.unpack('>H', data[offset:offset+2])[0]
            if size < 2 or offset + size > len(data):
                raise ValueError()
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack('>HH', data[offset+3:offset+7])
                dimensions = (width, height)
                break
            offset += size
        if dimensions != (raw['width'], raw['height']):
            raise ValueError()
    except (ValueError, IndexError, struct.error) as exc:
        raise ValueError('invalid-visual-image') from exc
    return dict(raw)


def visual_input(safe_input):
    """Remove image bytes from JSON text; return separate multimodal input."""
    text_input = dict(safe_input)
    scene = dict(text_input.get('scene') or {})
    visual = clean_visual(scene.pop('visual', None))
    if visual:
        scene['visual'] = {k: v for k, v in visual.items() if k != 'image'}
    text_input['scene'] = scene
    return text_input, visual
