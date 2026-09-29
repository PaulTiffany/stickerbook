"""Host-derived trajectory coordinates. Declarative evidence, never actions."""

from dataclasses import dataclass
from typing import Tuple

from page_path import PagePathTrace, PathSample
from semantic_reference import PendingSemanticReference


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def describe(self) -> dict:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class ResolvedTrajectoryReference:
    subject: str
    demonstration: str
    path_ref: str
    frame: str
    principal: str
    page: str
    source_episode: str
    source_start: Point
    subject_start: Point
    source_samples: Tuple[PathSample, ...]
    resolved_samples: Tuple[PathSample, ...]
    observed_duration_ms: int
    source_scene_revision: int
    resolution_scene_revision: int

    def describe(self) -> dict:
        """Bounded response summary; trajectory arrays stay host-side."""
        return {
            "subject": self.subject, "demonstration": self.demonstration,
            "pathRef": self.path_ref, "frame": self.frame,
            "principal": self.principal, "page": self.page,
            "sourceEpisode": self.source_episode,
            "sourceStart": self.source_start.describe(),
            "subjectStart": self.subject_start.describe(),
            "sampleCount": len(self.source_samples),
            "observedDurationMs": self.observed_duration_ms,
            "sourceSceneRevision": self.source_scene_revision,
            "resolutionSceneRevision": self.resolution_scene_revision,
        }


def resolve(reference: PendingSemanticReference, trace: PagePathTrace, *,
            frame: str, subject_start: Point,
            resolution_scene_revision: int) -> ResolvedTrajectoryReference:
    """Apply only the explicit frame to already-admitted retained evidence."""
    if frame not in ("page", "subject"):
        raise ValueError("invalid trajectory frame")
    # Own immutable copies survive source-log eviction. No second decimation,
    # rounding, interpolation, clipping, or interpretation occurs here.
    source = tuple(PathSample(p.t, p.x, p.y) for p in trace.samples)
    start = Point(source[0].x, source[0].y)
    resolved = source if frame == "page" else tuple(
        PathSample(p.t, subject_start.x + (p.x - start.x),
                   subject_start.y + (p.y - start.y)) for p in source)
    return ResolvedTrajectoryReference(
        subject=reference.subject, demonstration=reference.demonstration,
        path_ref=reference.path_ref, frame=frame,
        principal=reference.principal, page=reference.page,
        source_episode=reference.source_episode, source_start=start,
        subject_start=subject_start, source_samples=source,
        resolved_samples=resolved, observed_duration_ms=trace.duration_ms,
        source_scene_revision=trace.scene_revision_at_recording,
        resolution_scene_revision=resolution_scene_revision)
