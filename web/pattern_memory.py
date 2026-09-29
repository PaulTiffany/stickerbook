"""Bounded host-side movement-pattern memory.

A child is not programming an agent. The child is teaching a sticker a way it
likes to move, and StickerBook remembers it:

    "Remember that as your happy dance."

The research invariant is that **learning changes memory, not authority**. A
remembered pattern means only:

    when asked for this behavior, these previously accepted action forms
    occurred in this order

It never means "these actions are now permitted". Nothing here is consulted by
the authority kernel, and this module adds no mutation primitive. It is data
plus a bounded container, deliberately living beside the bridge rather than
inside `stickerbook_core`, so the kernel cannot acquire pattern awareness by
accident.

A step is a *typed, instance-independent* action fragment. Legal keys have the
form `<VERB>:<sticker-id>:<suffix>`, and a suffix alone is ambiguous:
`STEP-E` belongs to MOVE while `spin` belongs to ANIMATE. So a step keeps its
verb and discards only the transient StickerInstance id. Complete legal keys
are never stored; they are rebuilt against the current subject at replay time
and must still be present in the current host-owned table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Verb vocabulary for remembered movement. These name action FAMILIES, and
# each maps onto one existing kernel action. Nothing here creates a new
# mutation primitive; an unmapped verb simply cannot be remembered.
MOVE = "MOVE"
ANIMATE = "ANIMATE"
SCALE = "SCALE"
FACE = "FACE"

# Verb -> the kernel action a key of that family must have produced. Used to
# cross-check a captured step against its receipt, so a MOVE step can never be
# recorded from an ANIMATE receipt.
VERB_ACTIONS: Dict[str, str] = {
    MOVE: "move-sticker",
    ANIMATE: "animate-own-sticker",
    SCALE: "resize-own-sticker",
    FACE: "set-sticker-facing",
}

PATTERN_VERBS = frozenset(VERB_ACTIONS)

# Bounds. Memory is finite on purpose.
MAX_PATTERNS = 32
MAX_PATTERN_STEPS = 12
MAX_LABEL_LENGTH = 48
MAX_SUFFIX_LENGTH = 40
MAX_SCENE_PATTERNS = 8

_SUFFIX_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_.")

# A label is child-facing text. Colons are excluded so no remembered string
# can be mistaken for, or assembled into, a complete action key.
_LABEL_FORBIDDEN = frozenset(":\r\n\t")


def valid_suffix(suffix) -> bool:
    return (isinstance(suffix, str)
            and 0 < len(suffix) <= MAX_SUFFIX_LENGTH
            and all(ch in _SUFFIX_CHARS for ch in suffix))


def valid_label(label) -> bool:
    return (isinstance(label, str)
            and 0 < len(label.strip()) <= MAX_LABEL_LENGTH
            and not any(ch in _LABEL_FORBIDDEN for ch in label))


@dataclass(frozen=True)
class PatternStep:
    """One typed, instance-independent action fragment.

    Data only. It holds no sticker id, no coordinates, no command and nothing
    callable. `verb` preserves the action family that a bare suffix loses.
    """

    verb: str
    suffix: str

    def __post_init__(self):
        if self.verb not in PATTERN_VERBS:
            raise ValueError("unknown pattern verb: %r" % (self.verb,))
        if not valid_suffix(self.suffix):
            raise ValueError("invalid pattern suffix: %r" % (self.suffix,))

    def to_dict(self) -> dict:
        return {"verb": self.verb, "suffix": self.suffix}


def bind_key(step: PatternStep, subject_id: str) -> str:
    """Rebuild a CANDIDATE action key for one current subject.

    Deliberately a module function rather than a method: a pattern stays inert
    data, and binding is something the host does to it. The result is only a
    candidate. The caller must still find it in the current legal table.
    """
    return "%s:%s:%s" % (step.verb, subject_id, step.suffix)


def split_key(key, subject_id) -> Optional[PatternStep]:
    """Turn one accepted legal key back into an instance-independent step.

    Returns None when the key does not belong to a remembered verb family or
    does not belong to this subject. Matching uses an explicit prefix, so a
    sticker id containing a colon cannot confuse the split.
    """
    if not isinstance(key, str) or not isinstance(subject_id, str):
        return None
    for verb in sorted(PATTERN_VERBS):
        prefix = "%s:%s:" % (verb, subject_id)
        if key.startswith(prefix):
            suffix = key[len(prefix):]
            if not valid_suffix(suffix):
                return None
            return PatternStep(verb=verb, suffix=suffix)
    return None


def steps_from_trace(trace, subject_id):
    """Derive steps from a run trace, keeping only ACCEPTED kernel receipts.

    Rejected, replayed, unavailable, malformed or merely proposed actions do
    not become learned movement. A NOOP is a decision to stop rather than a
    way of moving, so it is skipped rather than remembered.

    Returns (steps, error).
    """
    if not isinstance(trace, (list, tuple)):
        return None, "invalid-pattern-trace"

    steps: List[PatternStep] = []
    for entry in trace:
        if not isinstance(entry, dict):
            return None, "invalid-pattern-trace"
        receipt = entry.get("receipt")
        if not isinstance(receipt, dict):
            return None, "invalid-pattern-trace"
        if receipt.get("accepted") is not True:
            continue
        step = split_key(entry.get("choice"), subject_id)
        if step is None:
            # NOOP, and anything outside the remembered verb families.
            continue
        # The receipt has to agree with the family the key implies.
        if receipt.get("action") != VERB_ACTIONS[step.verb]:
            return None, "pattern-step-action-mismatch"
        if receipt.get("object") not in (None, subject_id):
            return None, "pattern-step-subject-mismatch"
        steps.append(step)

    if not steps:
        return None, "no-accepted-pattern-steps"
    return tuple(steps), None


@dataclass(frozen=True)
class MovementPattern:
    """One remembered way of moving. Immutable data.

    Records what was accepted, for which StickerDefinition, and where it came
    from. Carries no principal authority, no capability, no executable
    content.
    """

    pattern_id: str
    label: str
    asset: str
    steps: Tuple[PatternStep, ...]
    learned_from_subject: str
    learned_by: str
    learned_at_revision: int

    def to_dict(self) -> dict:
        return {
            "id": self.pattern_id,
            "label": self.label,
            "asset": self.asset,
            "steps": [s.to_dict() for s in self.steps],
            "stepCount": len(self.steps),
            "learnedFromSubject": self.learned_from_subject,
            "learnedBy": self.learned_by,
            "learnedAtRevision": self.learned_at_revision,
        }

    def describe(self) -> dict:
        """Bounded declarative view for a chooser scene.

        Omits the originating StickerInstance id and never contains a complete
        action key. Typed fragments are included because an informed chooser
        still has to select from the current legal table; a fragment cannot be
        submitted to the kernel.
        """
        return {
            "id": self.pattern_id,
            "label": self.label,
            "stepCount": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
        }


class PatternLibrary:
    """Bounded, in-memory, host-owned pattern memory.

    Not persisted across restart in this tranche. Not shared between children.
    Never handed to an agent, never consulted by the kernel.
    """

    def __init__(self, max_patterns: int = MAX_PATTERNS,
                 max_steps: int = MAX_PATTERN_STEPS):
        self.max_patterns = int(max_patterns)
        self.max_steps = int(max_steps)
        self._patterns: Dict[str, MovementPattern] = {}
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._patterns)

    def get(self, pattern_id) -> Optional[MovementPattern]:
        if not isinstance(pattern_id, str):
            return None
        return self._patterns.get(pattern_id)

    def for_asset(self, asset) -> Tuple[MovementPattern, ...]:
        return tuple(p for p in self._patterns.values() if p.asset == asset)

    def describe_for_scene(self, asset, limit: int = MAX_SCENE_PATTERNS):
        out = []
        for pattern in sorted(self.for_asset(asset),
                              key=lambda p: p.pattern_id):
            out.append(pattern.describe())
            if len(out) >= limit:
                break
        return out

    def remember(self, *, label, asset, steps, subject_id, learned_by,
                 revision):
        """Store one pattern. Returns (pattern, error)."""
        if not valid_label(label):
            return None, "invalid-pattern-label"
        if not isinstance(asset, str) or not asset:
            return None, "invalid-pattern-asset"
        if not isinstance(steps, tuple) or not steps:
            return None, "empty-pattern"
        if any(not isinstance(s, PatternStep) for s in steps):
            return None, "invalid-pattern-step"
        if len(steps) > self.max_steps:
            return None, "pattern-too-long"
        if len(self._patterns) >= self.max_patterns:
            return None, "pattern-memory-full"

        pattern_id = "pattern-%d" % self._next_id
        self._next_id += 1
        pattern = MovementPattern(
            pattern_id=pattern_id,
            label=label.strip(),
            asset=asset,
            steps=steps,
            learned_from_subject=subject_id,
            learned_by=learned_by,
            learned_at_revision=int(revision),
        )
        self._patterns[pattern_id] = pattern
        return pattern, None


__all__ = [
    "MOVE", "ANIMATE", "SCALE", "FACE", "PATTERN_VERBS", "VERB_ACTIONS",
    "MAX_PATTERNS", "MAX_PATTERN_STEPS", "MAX_LABEL_LENGTH",
    "MAX_SUFFIX_LENGTH", "MAX_SCENE_PATTERNS",
    "PatternStep", "MovementPattern", "PatternLibrary",
    "bind_key", "split_key", "steps_from_trace",
    "valid_label", "valid_suffix",
]
