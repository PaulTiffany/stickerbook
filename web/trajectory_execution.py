"""Mechanical bookkeeping for following a resolved trajectory reference.

A `ResolvedTrajectoryReference` is frozen observation. Nothing here makes it
authoritative: this module only computes, from CURRENT world state, which
single retained point the subject is presently heading toward, and records
what the kernel then decided.

    reference (frozen geometry)
        -> host derives the CURRENT local objective
        -> host builds the CURRENT move_only legal surface
        -> a selector picks one CURRENT legal move
        -> kernel adjudicates an ordinary proposal
        -> fresh world state, and repeat

The trajectory is never compiled into a sequence of keys. Every step is
re-derived, so a trajectory confers no more power than being allowed to
propose one ordinary move at a time.

Progress is a MONOTONIC index into the retained points. It is never a nearest
-point search, and it never projects across the whole path. That ordering is
the only thing protecting loops: in an out-and-return trajectory the first and
last retained points may be the same coordinate, and any rule that asked
"which point am I closest to" could answer with the last one and declare the
whole excursion finished before it began.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from pattern_memory import COMPLETED, PARTIAL, STOPPED

# One bounded mechanical attempt. This is a MOTOR STEP budget, not elapsed
# time: nothing here reads a clock, and the reference's observed timing stays
# evidence rather than a schedule.
MAX_TRAJECTORY_STEPS = 48

# How much further than the step budget's bare geometric minimum an attempt
# may wander. The eight-direction alphabet cannot travel exactly along an
# arbitrary path, so a little slack is the difference between a truthful
# COMPLETED and a budget exhaustion on geometry we know is followable.
BUDGET_SLACK = 1.25

# The one executable coordinate frame. A page-frame reference stays valid
# non-executing data: its first point can be far from the subject, and what
# that should mean is a semantic question, not a geometric one.
FRAME_SUBJECT = "subject"

# How an attempt ended. `None` means it ended by completing.
STOPPED_UNKNOWN_SUBJECT = "trajectory-subject-unavailable"
STOPPED_NO_LEGAL_MOVES = "no-legal-move-choices"
STOPPED_UNREACHABLE = "trajectory-objective-unreachable"
STOPPED_BUDGET = "step-budget-exhausted"
STOPPED_REFUSED = "trajectory-step-refused"
STOPPED_SUPERSEDED = "superseded-by-human"
STOPPED_WORLD_CHANGED = "world-changed"
STOPPED_SELECTOR_DECLINED = "selector-declined"
STOPPED_SELECTOR_ERROR = "selector-error"
STOPPED_INVALID_CHOICE = "unknown-selector-choice"

NOT_EXECUTABLE = "trajectory-frame-not-executable"
NO_GEOMETRY = "trajectory-evidence-unavailable"


def distance(a, b) -> float:
    """Ordinary page-unit distance. Page axes; no normalisation."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def arc_length(points) -> float:
    return sum(distance((points[i].x, points[i].y),
                        (points[i + 1].x, points[i + 1].y))
               for i in range(len(points) - 1))


def planned_steps(points, reach: float) -> int:
    """A bounded budget derived once from the frozen geometry.

    Deterministic, host-side, and computed before any step is taken, so an
    attempt's length is never a function of what a selector decided.
    """
    if len(points) < 2:
        return 0
    return min(MAX_TRAJECTORY_STEPS,
               math.ceil(BUDGET_SLACK * arc_length(points) / reach))


def advance(points, progress: int, position, reach: float) -> int:
    """Walk the progress index past consecutive points already within reach.

    Strictly forward, one point at a time, and only through points the subject
    has actually come near. It cannot skip an excursion, because reaching a
    later index requires every intermediate point to have been within reach
    first.
    """
    last = len(points) - 1
    while progress < last \
            and distance(position, (points[progress].x,
                                    points[progress].y)) < reach:
        progress += 1
    return progress


def objective_of(points, progress: int):
    """The point the subject is currently heading toward."""
    point = points[progress]
    return (point.x, point.y)


def is_complete(points, progress: int, position, reach: float) -> bool:
    """Only sequential arrival at the FINAL point completes a trajectory.

    Not proximity to any later point, not proximity to the origin, not a
    selector declining, and not budget exhaustion. Host bookkeeping only.
    """
    last = len(points) - 1
    return progress >= last and distance(
        position, (points[last].x, points[last].y)) < reach


@dataclass(frozen=True)
class TrajectoryStepRecord:
    """One attempted motor step, and what authority said about it.

    `receipt` is an ordinary kernel mutation receipt. A step the host could
    not submit carries `unavailable_reason` instead. `superseded` marks a step
    the kernel refused as stale because the child moved this same sticker
    themselves while the selector was choosing.
    """

    index: int
    objective_index: int
    objective: Tuple[float, float]
    submitted: bool
    choice: Optional[str] = None
    receipt: Optional[dict] = None
    unavailable_reason: Optional[str] = None
    superseded: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "objectiveIndex": self.objective_index,
            "objective": {"x": self.objective[0], "y": self.objective[1]},
            "submitted": self.submitted,
            "choice": self.choice,
            "receipt": self.receipt,
            "unavailableReason": self.unavailable_reason,
            "superseded": self.superseded,
        }


@dataclass(frozen=True)
class TrajectoryExecutionRecord:
    """Host-side audit of one attempt to follow a resolved trajectory.

    This OBSERVES and GROUPS authority events. It holds no authority, and the
    kernel knows nothing about trajectories: its receipts stay ordinary move
    receipts. The reference itself is not stored here, only named, because an
    attempt must never be able to alter the observation it was following.
    """

    execution_id: str
    path_ref: str
    frame: str
    source_episode: str
    subject_id: str
    requested_by: str
    mode: str
    starting_revision: int
    waypoint_count: int
    planned_steps: int
    steps: Tuple[TrajectoryStepRecord, ...]
    progress_reached: int
    result: str
    stopped_at: Optional[int] = None
    stopped_reason: Optional[str] = None

    # Three counts, named for what each means. A step can be planned and never
    # submitted, or submitted and refused. `planned_steps` comes from the
    # frozen geometry and never varies with what happened.
    @property
    def submitted_steps(self) -> int:
        return sum(1 for s in self.steps if s.submitted)

    @property
    def accepted_steps(self) -> int:
        return sum(1 for s in self.steps
                   if s.receipt is not None
                   and s.receipt.get("accepted") is True)

    def to_dict(self) -> dict:
        return {
            "executionId": self.execution_id,
            "pathRef": self.path_ref,
            "frame": self.frame,
            "sourceEpisode": self.source_episode,
            "subject": self.subject_id,
            "requestedBy": self.requested_by,
            "mode": self.mode,
            "startingRevision": self.starting_revision,
            "waypointCount": self.waypoint_count,
            "plannedSteps": self.planned_steps,
            "submittedSteps": self.submitted_steps,
            "acceptedSteps": self.accepted_steps,
            "progressReached": self.progress_reached,
            "steps": [s.to_dict() for s in self.steps],
            "result": self.result,
            "stoppedAt": self.stopped_at,
            "stoppedReason": self.stopped_reason,
        }


def result_of(record_steps, complete: bool) -> str:
    """COMPLETED only on mechanical arrival; PARTIAL once anything landed."""
    accepted = sum(1 for s in record_steps
                   if s.receipt is not None
                   and s.receipt.get("accepted") is True)
    if complete:
        return COMPLETED
    return PARTIAL if accepted > 0 else STOPPED


class TrajectoryExecutionLog:
    """Bounded host-side log of trajectory attempts. Audit only."""

    def __init__(self, max_records: int = 64):
        self.max_records = int(max_records)
        self._records = []
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._records)

    def next_execution_id(self) -> str:
        execution_id = "trajectory-%d" % self._next_id
        self._next_id += 1
        return execution_id

    def add(self, record: TrajectoryExecutionRecord
            ) -> TrajectoryExecutionRecord:
        self._records.append(record)
        if len(self._records) > self.max_records:
            del self._records[0:len(self._records) - self.max_records]
        return record

    def records(self) -> Tuple[TrajectoryExecutionRecord, ...]:
        return tuple(self._records)

    def get(self, execution_id) -> Optional[TrajectoryExecutionRecord]:
        for record in self._records:
            if record.execution_id == execution_id:
                return record
        return None


__all__ = [
    "MAX_TRAJECTORY_STEPS", "BUDGET_SLACK", "FRAME_SUBJECT",
    "NOT_EXECUTABLE", "NO_GEOMETRY",
    "STOPPED_UNKNOWN_SUBJECT", "STOPPED_NO_LEGAL_MOVES",
    "STOPPED_UNREACHABLE", "STOPPED_BUDGET", "STOPPED_REFUSED",
    "STOPPED_SUPERSEDED", "STOPPED_WORLD_CHANGED",
    "STOPPED_SELECTOR_DECLINED", "STOPPED_SELECTOR_ERROR",
    "STOPPED_INVALID_CHOICE",
    "distance", "arc_length", "planned_steps", "advance", "objective_of",
    "is_complete", "result_of",
    "TrajectoryStepRecord", "TrajectoryExecutionRecord",
    "TrajectoryExecutionLog",
]
