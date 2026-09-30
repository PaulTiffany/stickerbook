"""Typed StickerBook experiences in Omega's native memory, never commands."""
import importlib
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import sys
from threading import RLock

MAX_RECORDS = 256


def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('invalid-memory-text')
    return value


def clean_event(raw, role):
    if not isinstance(raw, dict):
        raise ValueError('invalid-memory-event')
    common = {'id', 'page', 'kind'}
    kind = raw.get('kind')
    fields = {'conversation': {'text', 'reply'},
              'experience': {'subject', 'asset', 'source', 'moves', 'turns', 'clips', 'start', 'end'},
              'teaching': {'experience', 'valence', 'lesson'}}
    if not isinstance(kind, str) or kind not in fields or set(raw) != common | fields[kind]:
        raise ValueError('invalid-memory-fields')
    if (role == 'omegallm') != (kind == 'conversation'):
        raise ValueError('memory-role-mismatch')
    _text(raw['id'], 100); _text(raw['page'], 80)
    if kind == 'conversation':
        _text(raw['text'], 2000); _text(raw['reply'], 1000)
    elif kind == 'teaching':
        _text(raw['experience'], 100); _text(raw['lesson'], 200)
        if raw['valence'] not in ('positive', 'negative'):
            raise ValueError('invalid-memory-feedback')
    else:
        _text(raw['subject'], 100); _text(raw['asset'], 80)
        if raw['source'] not in ('child', 'jev'):
            raise ValueError('invalid-memory-source')
        if any(type(raw[k]) is not int or not 0 <= raw[k] <= 6 for k in ('moves', 'turns')):
            raise ValueError('invalid-memory-evidence')
        if not isinstance(raw['clips'], list) or len(raw['clips']) > 4:
            raise ValueError('invalid-memory-clips')
        for clip in raw['clips']: _text(clip, 80)
        for name in ('start', 'end'):
            point = raw[name]
            if not isinstance(point, dict) or set(point) != {'x', 'y'}:
                raise ValueError('invalid-memory-point')
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in point.values()):
                raise ValueError('invalid-memory-point')
    return json.loads(json.dumps(raw))


class NativeOmegaMemory:
    """Use Omega's remember/query/STV primitives; retain only typed records."""
    def __init__(self, role, *, native=None, embed=None, directory=None):
        if role not in ('omegallm', 'omegajev'):
            raise ValueError('invalid-memory-role')
        self.role = role
        self.lock = RLock()
        if native is None:
            # These are pinned image-owned library locations, never request paths.
            sys.path.insert(0, '/PeTTa/repos/petta_lib_chromadb')
            native = importlib.import_module('lib_chromadb')
            embedding = importlib.import_module('lib_llm_ext')
            embedding.initLocalEmbedding()
            import torch
            torch.set_num_threads(2)
            embed = embedding.useLocalEmbedding
        self.native, self.embed = native, embed
        self.query_embedding = lru_cache(maxsize=32)(embed)
        self.path = Path(directory or '/PeTTa/repos/Omega/memory') / ('stickerbook-' + role + '.json')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.index = []
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw, list) or len(raw) > MAX_RECORDS:
                raise ValueError('invalid-memory-index')
            for item in raw:
                clean_event(item['event'], role)
                _text(item['nativeId'], 100)
            self.index = raw

    def _save(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.index), encoding='utf-8')
        os.replace(temporary, self.path)

    def remember(self, events):
        if not isinstance(events, list) or not 1 <= len(events) <= 8:
            raise ValueError('invalid-memory-batch')
        clean = [clean_event(e, self.role) for e in events]
        with self.lock:
            existing = {i['event']['id'] for i in self.index}
        # Encode outside the native-store lock so background evidence does not
        # stall an agent's current-state decision while computing embeddings.
        vectors = {e['id']: self.embed(json.dumps({'role': self.role, 'event': e}, sort_keys=True))
                   for e in clean if e['id'] not in existing}
        with self.lock:
            stored = 0
            for event in clean:
                if event['id'] not in vectors or any(i['event']['id'] == event['id'] for i in self.index):
                    continue
                parent = None
                if event['kind'] == 'teaching':
                    parent = next((i for i in self.index if i['event']['id'] == event['experience']
                                   and i['event']['page'] == event['page']
                                   and i['event']['kind'] == 'experience'), None)
                    if parent is None:
                        raise ValueError('unknown-memory-experience')
                document = json.dumps({'role': self.role, 'event': event}, sort_keys=True)
                native_id = self.native.remember(document, vectors[event['id']], 'stickerbook:' + self.role + ':' + event['page'])
                self.index.append({'nativeId': native_id, 'event': event})
                if parent:
                    strength, confidence = self.native.get_stv(parent['nativeId']) or [0.5, 0.5]
                    strength = max(0.0, min(1.0, strength + (.1 if event['valence'] == 'positive' else -.1)))
                    self.native.set_stv(parent['nativeId'], strength, min(.99, confidence + .05))
                elif event['kind'] == 'experience':
                    self.native.set_stv(native_id, .5, .5)
                while len(self.index) > MAX_RECORDS:
                    old = self.index.pop(0)
                    self.native.forget_id(old['nativeId'])
                self._save()
                stored += 1
            return {'ok': True, 'stored': stored, 'records': len(self.index)}

    def recall(self, page, query, asset=None):
        _text(page, 80); _text(query, 400)
        with self.lock:
            candidates = [i for i in self.index if i['event']['page'] == page]
            if not candidates:
                return []
            # Native semantic retrieval stays in the agent's own collection.
            found = self.native.query_with_ids(self.query_embedding(query), min(MAX_RECORDS, len(self.index)))
            rank = {item[0]: n for n, item in enumerate(found)}
            candidates.sort(key=lambda i: (i['event']['kind'] != 'teaching', rank.get(i['nativeId'], MAX_RECORDS)))
            notes = []
            for item in candidates:
                e = item['event']
                if e['kind'] == 'conversation':
                    notes.append({'kind': 'conversation', 'child': e['text'][:200], 'reply': e['reply'][:200]})
                elif e['kind'] == 'teaching':
                    parent = next((i for i in self.index if i['event']['id'] == e['experience']), None)
                    if parent and (asset is None or parent['event']['asset'] == asset):
                        strength, confidence = self.native.get_stv(parent['nativeId']) or [0.5, 0.5]
                        notes.append({'kind': 'teaching', 'asset': parent['event']['asset'],
                                      'valence': e['valence'], 'lesson': e['lesson'],
                                      'strength': round(strength, 3), 'confidence': round(confidence, 3)})
                elif asset is None or e['asset'] == asset:
                    strength, confidence = self.native.get_stv(item['nativeId']) or [.5, .5]
                    notes.append({'kind': 'experience', 'asset': e['asset'], 'moves': e['moves'],
                                  'source': e['source'],
                                  'turns': e['turns'], 'clips': e['clips'],
                                  'strength': round(strength, 3), 'confidence': round(confidence, 3)})
                # Raw prior coordinates/subject ids/keys are not current facts.
                if len(notes) == 3:
                    break
            return notes

    def describe(self):
        with self.lock:
            return {'role': self.role, 'records': len(self.index), 'backend': 'Omega native Chroma', 'cap': MAX_RECORDS}
