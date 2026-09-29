"""Observed bare-page pointer path. No world anchors or interpretation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

MAX_SAMPLES = 32
MAX_INPUT_SAMPLES = 64
MAX_DURATION_MS = 20000
MAX_TRACES = 32
KIND_PAGE_PATH = "page-path"


@dataclass(frozen=True)
class PathSample:
    t: float
    x: float
    y: float

    def to_dict(self) -> dict:
        return {"t": self.t, "x": self.x, "y": self.y}


@dataclass(frozen=True)
class PagePathTrace:
    trace_id: str
    principal: str
    page: str
    scene_revision_at_recording: int
    duration_ms: int
    samples: Tuple[PathSample, ...]
    observed_sample_count: int
    deictic_box: Optional[dict] = None
    kind: str = KIND_PAGE_PATH

    def to_dict(self) -> dict:
        return {
            "traceId": self.trace_id,
            "principal": self.principal,
            "page": self.page,
            "sceneRevisionAtRecording": self.scene_revision_at_recording,
            "durationMs": self.duration_ms,
            "samples": [sample.to_dict() for sample in self.samples],
            "sampleCount": len(self.samples),
            "observedSampleCount": self.observed_sample_count,
            "deicticBox": self.deictic_box,
            "kind": self.kind,
        }

    def summary(self) -> dict:
        return {"traceId": self.trace_id, "kind": self.kind,
                "durationMs": self.duration_ms, "sampleCount": len(self.samples)}


def _fraction(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and 0 <= number <= 1 else None


def _error(a: PathSample, b: PathSample, c: PathSample) -> float:
    sx, sy = c.x - a.x, c.y - a.y
    length = math.hypot(sx, sy)
    if length == 0:
        return math.hypot(b.x - a.x, b.y - a.y)
    return abs(sy * b.x - sx * b.y + c.x * a.y - c.y * a.x) / length


def decimate(samples: List[PathSample], limit: int = MAX_SAMPLES
             ) -> Tuple[PathSample, ...]:
    """Remove least consequential interior samples; retain observed endpoints."""
    kept = list(samples)
    while len(kept) > limit:
        worst = min(range(1, len(kept) - 1),
                    key=lambda index: _error(
                        kept[index - 1], kept[index], kept[index + 1]))
        del kept[worst]
    return tuple(kept)


def parse_path(raw):
    """Return (observed samples, duration, error); never invent endpoints."""
    if not isinstance(raw, dict) or set(raw) != {"samples", "duration_ms"}:
        return None, None, "malformed page-path telemetry"
    duration = raw["duration_ms"]
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) \
            or not math.isfinite(duration) or not 0 < duration <= MAX_DURATION_MS:
        return None, None, "page-path duration out of range"
    samples = raw["samples"]
    if not isinstance(samples, list) or len(samples) < 2:
        return None, None, "page-path needs at least two samples"
    if len(samples) > MAX_INPUT_SAMPLES:
        return None, None, "too many page-path samples"
    parsed = []
    previous_t = None
    for item in samples:
        if not isinstance(item, dict) or set(item) != {"t", "x", "y"}:
            return None, None, "malformed page-path sample"
        values = tuple(_fraction(item[name]) for name in ("t", "x", "y"))
        if any(value is None for value in values):
            return None, None, "malformed page-path sample"
        t, x, y = values
        if previous_t is not None and t < previous_t:
            return None, None, "page-path samples are not ordered"
        parsed.append(PathSample(round(t, 6), round(x, 6), round(y, 6)))
        previous_t = t
    return decimate(parsed), max(1, round(duration)), None


class PagePathLog:
    def __init__(self, max_traces: int = MAX_TRACES):
        self.max_traces = int(max_traces)
        self._traces: List[PagePathTrace] = []
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._traces)

    def next_trace_id(self) -> str:
        trace_id = "path-%d" % self._next_id
        self._next_id += 1
        return trace_id

    def add(self, trace: PagePathTrace) -> PagePathTrace:
        self._traces.append(trace)
        if len(self._traces) > self.max_traces:
            del self._traces[:len(self._traces) - self.max_traces]
        return trace

    def get(self, trace_id) -> Optional[PagePathTrace]:
        return next((t for t in self._traces if t.trace_id == trace_id), None)

    def traces(self) -> Tuple[PagePathTrace, ...]:
        return tuple(self._traces)
