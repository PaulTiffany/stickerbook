"""Host accepts bounded pixel drafts; providers cannot declare authority."""
import base64
from pathlib import Path
import struct
import uuid


def publish(raw, directory):
    if not isinstance(raw, dict) or raw.get('kind') not in ('sticker', 'page'):
        raise ValueError('invalid-creator-draft')
    kind = raw['kind']
    images = raw.get('frames') if kind == 'sticker' else raw.get('images')
    if kind == 'sticker':
        if not isinstance(images, list) or len(images) != 4:
            raise ValueError('expected-four-animation-frames')
        images = dict(enumerate(images))
    elif not isinstance(images, dict) or set(images) != {'landscape', 'portrait'}:
        raise ValueError('invalid-page-variants')
    decoded = {}
    for name, data in images.items():
        if not isinstance(data, str) or not data.startswith('data:image/png;base64,') or len(data) > 4 * 1024 * 1024:
            raise ValueError('invalid-creator-image')
        image = base64.b64decode(data.split(',',1)[1], validate=True)
        expected = (256,256) if kind == 'sticker' else (1916,717) if name == 'landscape' else (941,1574)
        if (len(image) < 24 or image[:8] != b'\x89PNG\r\n\x1a\n' or
                image[12:16] != b'IHDR' or struct.unpack('>II', image[16:24]) != expected):
            raise ValueError('invalid-creator-image-dimensions')
        decoded[name] = image
    token = uuid.uuid4().hex
    target = Path(directory) / token
    target.mkdir(parents=True)
    sources = {}
    for name, image in decoded.items():
        (target / (str(name)+'.png')).write_bytes(image)
        sources[name] = '/generated-pages/' + token + '/' + str(name) + '.png'
    draft = {'id': token, 'kind': kind, 'name': str(raw.get('name') or 'My creation')[:80]}
    if kind == 'sticker':
        draft['asset'] = {'name': draft['name'], 'themes': ['my creations'], 'default_clip': 'rest',
            'sprites': {str(n): sources[n] for n in range(4)},
            'clips': {'rest': {'frames': ['0'], 'loop': False},
                      'play': {'frames': ['0','1','2','3'], 'loop': True, 'frame_ms': 200}}}
        draft['summary'] = 'Four animation frames ready'
    else:
        draft['variants'] = {name: {'src': source, 'width': 1916 if name == 'landscape' else 941,
            'height': 717 if name == 'landscape' else 1574, 'filename': name+'.png'} for name, source in sources.items()}
        draft['summary'] = 'Landscape and portrait artwork ready'
    return draft
