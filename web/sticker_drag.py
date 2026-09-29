"""Bounded host-side record of one child dragging a placed sticker.

    Input history is not world history.
    Failure to observe must not become failure to act.

**Scope.** This is ONE input type, not StickerBook's gesture ontology. It is
specifically the observed trajectory of a child dragging a sticker that is
already on the page, which is why the record structurally requires a subject
and an asset. Pointing, boxing a region, drawing a path through empty page
space, speech accompanied by a gesture, and directing one sticker along a path
demonstrated elsewhere are all different input types. None of them is modelled
here, and nothing in this module should be generalised into a universal
gesture semantics.

When a child drags a sticker, the browser sees a whole trajectory -- a circle,
a zig-zag, a swoop -- while the kernel is asked to authorize exactly one
ordinary `MOVE_STICKER` to the release point. Without this module the host
remembers only "the sticker ended over there", and the demonstration is lost.

A `StickerDragTrace` keeps that demonstration as bounded declarative data with
**three explicit classes of evidence**:

1. an **authoritative start** -- `TrajectorySample(t=0, dx=0, dy=0)`, bound by
   the host from the StickerInstance position read before the move was
   proposed;
2. an **observed interior trajectory** -- what the browser reported the
   pointer doing, validated and decimated, never a world mutation and never a
   kernel receipt;
3. an **authoritative terminal point** -- bound by the host from the
   StickerInstance position after the kernel accepted the move.

The anchors are host-derived, not merely trusted to coincide with the
browser's first and last samples. A modified or stale browser therefore cannot
produce a trace whose path claims an origin or destination different from its
authoritative anchors.

Nothing here has authority. The kernel is unchanged and knows nothing about
drags. A trace is retained only when its terminal governed move was accepted.

This tranche is observational. It deliberately does NOT quantise a trajectory
into `STEP-E`/`STEP-N` fragments, classify a path as a circle or a zig-zag, or
make a drag learnable by the discrete PatternStep mechanism.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Retained samples per trace, including the two host-bound anchors.
MAX_SAMPLES = 32

# Raw samples the host will accept in one request. Chosen so that a
# worst-case legal payload still fits the bridge's MAX_BODY_BYTES transport
# ceiling with room for the ordinary move envelope; see the size regression
# test. The browser retains far fewer than this.
MAX_INPUT_SAMPLES = 192

# A child drag is short. Anything longer is not a demonstration we keep.
MAX_DURATION_MS = 20000

# Bounded log of recent demonstrations.
MAX_TRACES = 32

# Observational precision. Rounding before transmission is input compression,
# not semantic interpretation: a quarter of a thousandth of a page is far
# below anything a child's hand or the renderer distinguishes.
PROGRESS_PLACES = 3
POSITION_PLACES = 4

KIND_STICKER_DRAG = "sticker-drag"

# Exactly the keys a browser may send. Anything else -- provenance, an acting
# principal, another subject, executable content -- is malformed.
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
    """One point of the retained trajectory.

    `t` is monotonic progress through the drag, 0.0 to 1.0. `dx`/`dy` are
    page-space displacement from the drag's AUTHORITATIVE starting position,
    not absolute coordinates, so the same demonstrated shape can later be read
    against another sticker starting somewhere else.
    """

    t: float
    dx: float
    dy: float

    def to_dict(self) -> dict:
        return {"t": self.t, "dx": self.dx, "dy": self.dy}


@dataclass(frozen=True)
class StickerDragTrace:
    """One bounded demonstration of dragging a placed sticker. Data only."""

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
    observed_sample_count: int = 0
    kind: str = KIND_STICKER_DRAG

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
            "observedSampleCount": self.observed_sample_count,
            "terminalCommandId": self.terminal_command_id,
            "terminalMoveAccepted": self.terminal_move_accepted,
            "kind": self.kind,
        }

    def summary(self) -> dict:
        """What may travel in a bounded projection.

        The raw sample array stays with the host: OmegaLLM does not need it to
        talk about a demonstration, and the discrete Jev choice surface is
        unrelated to it.
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
             limit: int) -> List[TrajectorySample]:
    """Reduce a trajectory to `limit` points, keeping its shape.

    Repeatedly drops the interior point whose removal changes the path least,
    measured as perpendicular distance from the line between its neighbours.
    That keeps the first point, the last point, the ordering and the major
    bends, and it observes the WHOLE gesture: a long demonstration cannot fill
    the buffer early and lose its ending, which is what taking the first N
    events would do.

    Deterministic: ties keep the earliest index. Points are only ever removed,
    never invented or moved -- no smoothing, no fitting, no inference.
    """
    points = list(samples)
    if limit <= 0:
        return []
    if len(points) <= limit:
        return points
    if limit < 2:
        return points[:limit]
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


def parse_drag(raw, *, start: Point):
    """Validate one browser drag payload. Returns (interior, duration, error).

    The browser is the physical input surface, so it is the only possible
    source of pointer samples. It remains untrusted for world state: the
    subject, the acting principal and the starting position all come from the
    host, and anything beyond `samples` and `duration_ms` is malformed.

    Only the interior of the trajectory is returned. Observed samples at the
    extremes of progress are dropped, because the host binds those positions
    itself from authoritative state.
    """
    if not isinstance(raw, dict):
        return None, None, "drag telemetry must be an object"
    unknown = set(raw) - _GESTURE_KEYS
    if unknown:
        return None, None, "unknown drag telemetry field"

    duration = raw.get("duration_ms")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        return None, None, "drag duration must be a number"
    duration = float(duration)
    if not math.isfinite(duration) or duration <= 0 \
            or duration > MAX_DURATION_MS:
        return None, None, "drag duration out of range"

    samples = raw.get("samples")
    if not isinstance(samples, list) or not samples:
        return None, None, "drag samples must be a non-empty list"
    if len(samples) > MAX_INPUT_SAMPLES:
        return None, None, "too many drag samples"

    interior: List[TrajectorySample] = []
    previous_t = None
    for item in samples:
        if not isinstance(item, dict) or set(item) != _SAMPLE_KEYS:
            return None, None, "malformed drag sample"
        t = _finite_fraction(item.get("t"))
        x = _finite_fraction(item.get("x"))
        y = _finite_fraction(item.get("y"))
        if t is None or x is None or y is None:
            return None, None, "malformed drag sample"
        if previous_t is not None and t < previous_t:
            return None, None, "drag samples are not ordered"
        previous_t = t
        if t <= 0.0 or t >= 1.0:
            # The host binds both endpoints itself.
            continue
        interior.append(TrajectorySample(
            t=round(t, 6),
            dx=round(x - start.x, 6),
            dy=round(y - start.y, 6)))

    return interior, int(duration), None


def anchor(interior, *, start: Point, end: Point,
           limit: int = MAX_SAMPLES) -> Tuple[TrajectorySample, ...]:
    """Bind an observed interior trajectory between authoritative endpoints.

    The first and last retained samples are derived from host-owned state, not
    from anything the browser claimed, so the path cannot assert a different
    origin or destination from the move the kernel actually accepted.
    """
    head = TrajectorySample(t=0.0, dx=0.0, dy=0.0)
    tail = TrajectorySample(
        t=1.0,
        dx=round(end.x - start.x, 6),
        dy=round(end.y - start.y, 6))
    middle = decimate(list(interior), max(0, limit - 2))
    return tuple([head] + middle + [tail])


class StickerDragLog:
    """Bounded host-owned log of recent demonstrations. Not persisted."""

    def __init__(self, max_traces: int = MAX_TRACES):
        self.max_traces = int(max_traces)
        self._traces: List[StickerDragTrace] = []
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._traces)

    def next_trace_id(self) -> str:
        trace_id = "drag-%d" % self._next_id
        self._next_id += 1
        return trace_id

    def add(self, trace: StickerDragTrace) -> StickerDragTrace:
        self._traces.append(trace)
        if len(self._traces) > self.max_traces:
            del self._traces[0:len(self._traces) - self.max_traces]
        return trace

    def get(self, trace_id) -> Optional[StickerDragTrace]:
        for trace in self._traces:
            if trace.trace_id == trace_id:
                return trace
        return None

    def for_subject(self, subject_id) -> Tuple[StickerDragTrace, ...]:
        return tuple(t for t in self._traces if t.subject_id == subject_id)

    def traces(self) -> Tuple[StickerDragTrace, ...]:
        return tuple(self._traces)


__all__ = [
    "MAX_SAMPLES", "MAX_INPUT_SAMPLES", "MAX_DURATION_MS", "MAX_TRACES",
    "PROGRESS_PLACES", "POSITION_PLACES", "KIND_STICKER_DRAG",
    "Point", "TrajectorySample", "StickerDragTrace", "StickerDragLog",
    "decimate", "parse_drag", "anchor",
]
