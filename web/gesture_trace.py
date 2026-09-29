"""Bounded host-side record of what a child physically demonstrated.

    Input history is not world history.

When a child freehand-drags a sticker, the browser sees a whole trajectory --
a circle, a zig-zag, a swoop -- while the kernel is asked to authorize exactly
one ordinary `MOVE_STICKER` to the release point. Without this module the host
remembers only "the sticker ended over there", and the demonstration is lost.

So a `GestureTrace` preserves the gesture as bounded declarative data. It is
deliberately a *mixed evidence* object:

* the **start** is authoritative -- the StickerInstance position the kernel
  had before the move was proposed, not something the browser asserted;
* the **samples between** are observations of the child's physical input.
  They are not world mutations and never become kernel receipts;
* the **end** is authoritative -- the StickerInstance position after the
  kernel accepted the move.

Nothing here has authority. The kernel is unchanged and knows nothing about
gestures. A trace is retained only when its terminal governed move was
accepted; a refused, cancelled or off-page release produces no demonstration.

This tranche is observational. It deliberately does NOT quantise a trajectory
into `STEP-E`/`STEP-N` fragments, because the child never supplied those, and
it does not make a freehand drag learnable by the discrete PatternStep
mechanism. How a demonstration becomes movement memory is the next decision,
and it should be made against real recorded trajectories.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Retained samples per trace. A child gesture does not need many points to
# keep its shape, and this is what the host stores after decimation.
MAX_SAMPLES = 32

# Raw samples the host will accept in one request before refusing it. The
# browser decimates as it records so pointermove frequency cannot create an
# unbounded POST; this is the host's own limit, enforced regardless.
MAX_INPUT_SAMPLES = 256

# A child drag is short. Anything longer is not a gesture we want to keep.
MAX_DURATION_MS = 20000

# Bounded log of recent demonstrations.
MAX_TRACES = 32

KIND_FREEHAND = "freehand"

# Exactly the keys a browser sample may carry. Anything else -- provenance,
# principal, metadata, executable content -- makes the request malformed.
_SAMPLE_KEYS = frozenset({"t", "x", "y"})
_GESTURE_KEYS = frozenset({"samples", "duration_ms"})


def _finite_fraction(value) -> Optional[float]:
    """A finite page fraction in [0, 1], or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return None
    return number


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class TrajectorySample:
    """One observed point of the child's gesture.

    `t` is monotonic progress through the gesture, 0.0 to 1.0. `dx`/`dy` are
    page-space displacement from the gesture's AUTHORITATIVE starting
    position, not absolute coordinates, so the same demonstrated shape can
    later be read against another sticker starting somewhere else.
    """

    t: float
    dx: float
    dy: float

    def to_dict(self) -> dict:
        return {"t": self.t, "dx": self.dx, "dy": self.dy}


@dataclass(frozen=True)
class GestureTrace:
    """One bounded freehand demonstration. Data only."""

    trace_id: str
    subject_id: str
    asset: str
    demonstrated_by: str
    starting_revision: int
    start: Point
    end: Point
    duration_ms: int
    samples: Tuple[TrajectorySample, ...]
    terminal_command_id: str
    terminal_move_accepted: bool
    kind: str = KIND_FREEHAND

    def to_dict(self) -> dict:
        return {
            "traceId": self.trace_id,
            "subject": self.subject_id,
            "asset": self.asset,
            "demonstratedBy": self.demonstrated_by,
            "startingRevision": self.starting_revision,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "durationMs": self.duration_ms,
            "samples": [s.to_dict() for s in self.samples],
            "sampleCount": len(self.samples),
            "terminalCommandId": self.terminal_command_id,
            "terminalMoveAccepted": self.terminal_move_accepted,
            "kind": self.kind,
        }

    def summary(self) -> dict:
        """What may travel in a bounded projection.

        The raw sample array stays with the host: OmegaLLM does not need it to
        talk about a gesture, and the discrete Jev choice surface is unrelated
        to it.
        """
        return {
            "traceId": self.trace_id,
            "subject": self.subject_id,
            "kind": self.kind,
            "sampleCount": len(self.samples),
            "durationMs": self.duration_ms,
        }


def _perpendicular_error(previous, point, following) -> float:
    """How far `point` sits off the line between its neighbours."""
    ax, ay = previous.dx, previous.dy
    bx, by = following.dx, following.dy
    px, py = point.dx, point.dy
    segment_x, segment_y = bx - ax, by - ay
    length = math.hypot(segment_x, segment_y)
    if length == 0.0:
        return math.hypot(px - ax, py - ay)
    return abs(segment_y * px - segment_x * py + bx * ay - by * ax) / length


def decimate(samples: List[TrajectorySample],
             limit: int = MAX_SAMPLES) -> List[TrajectorySample]:
    """Reduce a trajectory to `limit` points, keeping its shape.

    Repeatedly drops the interior point whose removal changes the path least,
    measured as perpendicular distance from the line between its neighbours.
    That keeps the first point, the last point, the ordering and the major
    bends, and it observes the WHOLE gesture: a long demonstration cannot fill
    the buffer early and lose its ending, which is what taking the first N
    events would do.

    Deterministic: ties keep the earliest index. No inference, no fitting, no
    smoothing -- points are only ever removed, never invented or moved.
    """
    points = list(samples)
    if limit < 2 or len(points) <= limit:
        return points
    while len(points) > limit:
        worst_index = None
        worst_error = None
        for index in range(1, len(points) - 1):
            error = _perpendicular_error(
                points[index - 1], points[index], points[index + 1])
            if worst_error is None or error < worst_error:
                worst_error = error
                worst_index = index
        del points[worst_index]
    return points


def parse_gesture(raw, *, start: Point):
    """Validate one browser gesture payload. Returns (samples, duration, error).

    The browser is the physical input surface, so it is the only possible
    source of pointer samples. It remains untrusted for world state: the
    subject, the acting principal and the starting position all come from the
    host, and anything this payload carries beyond `samples` and `duration_ms`
    makes the request malformed.
    """
    if not isinstance(raw, dict):
        return None, None, "gesture must be an object"
    unknown = set(raw) - _GESTURE_KEYS
    if unknown:
        return None, None, "unknown gesture field"

    duration = raw.get("duration_ms")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        return None, None, "gesture duration must be a number"
    duration = float(duration)
    if not math.isfinite(duration) or duration <= 0 \
            or duration > MAX_DURATION_MS:
        return None, None, "gesture duration out of range"

    samples = raw.get("samples")
    if not isinstance(samples, list) or not samples:
        return None, None, "gesture samples must be a non-empty list"
    if len(samples) > MAX_INPUT_SAMPLES:
        return None, None, "too many gesture samples"

    parsed: List[TrajectorySample] = []
    previous_t = None
    for item in samples:
        if not isinstance(item, dict) or set(item) != _SAMPLE_KEYS:
            return None, None, "malformed gesture sample"
        t = _finite_fraction(item.get("t"))
        x = _finite_fraction(item.get("x"))
        y = _finite_fraction(item.get("y"))
        if t is None or x is None or y is None:
            return None, None, "malformed gesture sample"
        if previous_t is not None and t < previous_t:
            return None, None, "gesture samples are not ordered"
        previous_t = t
        # Relative to the AUTHORITATIVE start, not to anything the browser
        # claimed the gesture began at.
        parsed.append(TrajectorySample(
            t=t, dx=round(x - start.x, 6), dy=round(y - start.y, 6)))

    return decimate(parsed), int(duration), None


class GestureTraceLog:
    """Bounded host-owned log of recent demonstrations. Not persisted."""

    def __init__(self, max_traces: int = MAX_TRACES):
        self.max_traces = int(max_traces)
        self._traces: List[GestureTrace] = []
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._traces)

    def next_trace_id(self) -> str:
        trace_id = "gesture-%d" % self._next_id
        self._next_id += 1
        return trace_id

    def add(self, trace: GestureTrace) -> GestureTrace:
        self._traces.append(trace)
        if len(self._traces) > self.max_traces:
            del self._traces[0:len(self._traces) - self.max_traces]
        return trace

    def get(self, trace_id) -> Optional[GestureTrace]:
        for trace in self._traces:
            if trace.trace_id == trace_id:
                return trace
        return None

    def for_subject(self, subject_id) -> Tuple[GestureTrace, ...]:
        return tuple(t for t in self._traces if t.subject_id == subject_id)

    def traces(self) -> Tuple[GestureTrace, ...]:
        return tuple(self._traces)


__all__ = [
    "MAX_SAMPLES", "MAX_INPUT_SAMPLES", "MAX_DURATION_MS", "MAX_TRACES",
    "KIND_FREEHAND", "Point", "TrajectorySample", "GestureTrace",
    "GestureTraceLog", "decimate", "parse_gesture",
]
