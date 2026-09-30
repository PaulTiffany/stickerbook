"""Host evidence courier. Omega owns storage and recall, not this queue."""
from collections import deque
import copy
import math
from pathlib import Path
import sys
from threading import Lock, Thread
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
from stickerbook_core import MOVE_STICKER, ANIMATE_OWN_STICKER


class ExperienceCourier:
    def __init__(self, kernel, runtime, page):
        self.kernel, self.runtime, self.page = kernel, runtime, page
        self.recent = deque(maxlen=12)
        self.pending = {}
        self.previous = {s['id']: {'x': s['x'], 'y': s['y']}
                         for s in kernel.view('human:kid')['stickers']}
        self.queue = deque(maxlen=32)
        self.lock = Lock()
        self.worker = None
        self.status = 'idle'

    def record(self, receipt, subject=None):
        if not receipt.accepted or receipt.replayed or receipt.action not in (MOVE_STICKER, ANIMATE_OWN_STICKER):
            return
        sticker = self.kernel.sticker(subject or receipt.object_id)
        if sticker is None:
            return
        point = {'x': sticker.x, 'y': sticker.y}
        source = 'jev' if receipt.selected_by else 'child'
        event = self.pending.get(sticker.id)
        if event and event['source'] != source:
            self.flush(sticker.id)
            event = None
        if event is None:
            event = {'id': 'experience-' + uuid.uuid4().hex, 'kind': 'experience', 'page': self.page,
                     'subject': sticker.id, 'asset': sticker.asset, 'moves': 0, 'turns': 0,
                     'source': source,
                     'clips': [], 'start': self.previous.get(sticker.id, point), 'end': point}
            self.pending[sticker.id] = event
        if receipt.action == MOVE_STICKER:
            previous = self.previous.get(sticker.id, point)
            dx, dy = point['x'] - previous['x'], point['y'] - previous['y']
            delta = round(math.atan2(dy, dx) * 8 / math.pi) % 16 if dx or dy else None
            last = getattr(self, 'deltas', {}).get(sticker.id)
            if last is not None and delta != last:
                event['turns'] = min(6, event['turns'] + 1)
            if not hasattr(self, 'deltas'): self.deltas = {}
            self.deltas[sticker.id] = delta
            event['moves'] += 1
        if sticker.animation not in event['clips'] and len(event['clips']) < 4:
            event['clips'].append(sticker.animation)
        event['end'] = point
        self.previous[sticker.id] = point
        if event['moves'] >= 6:
            self.flush(sticker.id)

    def flush(self, subject=None):
        for sid in list(self.pending) if subject is None else [subject]:
            event = self.pending.pop(sid, None)
            if event:
                self.recent.append(event)
                self.enqueue(event)

    def describe(self):
        self.flush()
        return copy.deepcopy(list(self.recent))

    def enqueue(self, event):
        if not hasattr(self.runtime, 'remember'):
            self.status = 'unavailable'
            return
        with self.lock:
            self.queue.append(copy.deepcopy(event))
            if self.worker is None or not self.worker.is_alive():
                self.worker = Thread(target=self._send, name='omega-experience-courier', daemon=True)
                self.worker.start()

    def _send(self):
        while True:
            with self.lock:
                if not self.queue:
                    self.worker = None
                    return
                event = self.queue.popleft()
            try:
                result = self.runtime.remember([event])
                self.status = 'stored' if result.get('ok') else 'unavailable'
            except Exception:
                self.status = 'unavailable'

    def teach(self, teaching, offered):
        if not isinstance(teaching, dict) or set(teaching) != {'experience', 'valence', 'lesson'}:
            return {'ok': False, 'error': 'invalid-teaching'}
        if teaching['valence'] not in ('positive', 'negative') or not isinstance(teaching['lesson'], str) or not 1 <= len(teaching['lesson']) <= 200:
            return {'ok': False, 'error': 'invalid-teaching'}
        experience = next((e for e in offered if e['id'] == teaching['experience'] and e['page'] == self.page), None)
        if experience is None:
            return {'ok': False, 'error': 'unknown-teaching-experience'}
        if not hasattr(self.runtime, 'remember'):
            return {'ok': False, 'error': 'omega-memory-unavailable'}
        event = {'id': 'teaching-' + uuid.uuid4().hex, 'kind': 'teaching', 'page': self.page, **teaching}
        try:
            return self.runtime.remember([experience, event])
        except Exception:
            return {'ok': False, 'error': 'omega-memory-unavailable'}
