"""Bounded host-owned record of governed actions that actually happened.

This exists so a child can say "remember *that*" and the host knows what
"that" was. The rule it enforces:

    The host remembers what happened. OmegaLLM interprets the child's
    reference to it. OmegaLLM does not get to rewrite history.

OmegaLLM receives a bounded declarative projection of this history and may
refer to it. It cannot add to it, edit it, or invent entries: only the host
writes here, and only from real kernel receipts.

Entries are plain data. No executable content, no provider secrets, no model
state, no authority objects, and nothing here is ever consulted by the
authority kernel.

A `key` is present only when the action was selected from the host-owned legal
action table (`Kernel.propose_key`). A freehand human drag is a real governed
mutation and is recorded for audit, but it has no instance-independent typed
form, so it carries no key and cannot become a learned PatternStep.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

# Where the action originated. The host knows this at the call site; a kernel
# receipt alone cannot always distinguish these, so the host labels it here
# rather than teaching the kernel about interaction paths.
ORIGIN_HUMAN_GESTURE = "human-gesture"
ORIGIN_OMEGALLM_JEV = "omegallm-jev"
ORIGIN_GESTURE_JEV = "gesture-jev"
ORIGIN_PATTERN_REPLAY = "pattern-replay"
ORIGIN_PATTERN_PERFORM = "pattern-perform"

ORIGINS = frozenset({
    ORIGIN_HUMAN_GESTURE,
    ORIGIN_OMEGALLM_JEV,
    ORIGIN_GESTURE_JEV,
    ORIGIN_PATTERN_REPLAY,
    ORIGIN_PATTERN_PERFORM,
})

MAX_HISTORY = 128
MAX_SCENE_HISTORY = 12


@dataclass(frozen=True)
class GovernedAction:
    """One governed action the kernel actually decided. Immutable data."""

    sequence: int
    origin: str
    actor: str
    action: str
    accepted: bool
    reason: str
    subject_id: Optional[str] = None
    key: Optional[str] = None
    command_id: Optional[str] = None
    result_revision: Optional[int] = None
    requested_by: Optional[str] = None
    translated_by: Optional[str] = None
    selected_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "origin": self.origin,
            "actor": self.actor,
            "action": self.action,
            "accepted": self.accepted,
            "reason": self.reason,
            "subject": self.subject_id,
            "key": self.key,
            "commandId": self.command_id,
            "resultRevision": self.result_revision,
            "requestedBy": self.requested_by,
            "translatedBy": self.translated_by,
            "selectedBy": self.selected_by,
        }

    def describe(self) -> dict:
        """Bounded declarative view for OmegaLLM.

        Deliberately omits the complete legal action key: OmegaLLM interprets
        language, it does not author or replay keys. It gets enough to say
        "the recent thing involving Froggy", not enough to construct a
        mutation.
        """
        return {
            "sequence": self.sequence,
            "subject": self.subject_id,
            "action": self.action,
            "accepted": self.accepted,
            "origin": self.origin,
            "requestedBy": self.requested_by,
        }


class GovernedHistory:
    """Bounded, host-owned, append-only-in-practice action history.

    Not persisted across restart in this tranche.
    """

    def __init__(self, max_entries: int = MAX_HISTORY):
        self.max_entries = int(max_entries)
        self._entries = deque(maxlen=self.max_entries)
        self._next_sequence = 1

    def __len__(self) -> int:
        return len(self._entries)

    def record(self, receipt, *, origin: str, key: Optional[str] = None,
               subject_id: Optional[str] = None) -> Optional[GovernedAction]:
        """Record one kernel receipt. Only the host calls this."""
        if origin not in ORIGINS:
            raise ValueError("unknown governed-action origin: %r" % (origin,))
        if receipt is None:
            return None

        entry = GovernedAction(
            sequence=self._next_sequence,
            origin=origin,
            actor=receipt.actor,
            action=receipt.action,
            accepted=bool(receipt.accepted),
            reason=receipt.reason,
            subject_id=subject_id if subject_id is not None
            else receipt.object_id,
            key=key,
            command_id=receipt.command_id,
            result_revision=receipt.result_revision,
            requested_by=receipt.requested_by,
            translated_by=receipt.translated_by,
            selected_by=receipt.selected_by,
        )
        self._next_sequence += 1
        self._entries.append(entry)
        return entry

    def entries(self) -> Tuple[GovernedAction, ...]:
        return tuple(self._entries)

    def recent_for_subject(self, subject_id: str,
                           limit: int = MAX_SCENE_HISTORY
                           ) -> Tuple[GovernedAction, ...]:
        found = [e for e in self._entries if e.subject_id == subject_id]
        return tuple(found[-limit:]) if limit > 0 else tuple(found)

    def latest_episode(self, subject_id: str, limit: int,
                       is_learnable=None) -> Tuple[GovernedAction, ...]:
        """The latest contiguous learnable episode for one subject.

        This is what the host means by "that". It is deliberately a
        *contiguous* run rather than a filter, so nothing is silently skipped
        over: scanning backwards from the most recent action, an entry joins
        the episode only while it stays learnable for this subject, and the
        first entry that is not ends it.

        An episode is terminated by any of:

        * **a switch to another subject** -- the child's attention moved, so
          the run of actions about this sticker is over;
        * **a non-learnable action on this subject** -- a refused proposal, a
          freehand drag with no typed form, or an accepted action outside the
          remembered verb families such as a removal;
        * **the `limit`**, which is the caller's maximum pattern length;
        * **the end of the bounded history window**.

        Every boundary is already observable in this record. None of them
        needs model judgement, and none of them is decided by OmegaLLM.
        """
        episode = []
        for entry in reversed(self._entries):
            if entry.subject_id != subject_id:
                break
            if not entry.accepted or not entry.key:
                break
            if is_learnable is not None and not is_learnable(entry):
                break
            episode.append(entry)
            if limit > 0 and len(episode) >= limit:
                break
        episode.reverse()
        return tuple(episode)

    def describe_for_scene(self, limit: int = MAX_SCENE_HISTORY) -> list:
        """Bounded recent history for the OmegaLLM conversation scene."""
        entries = list(self._entries)[-limit:] if limit > 0 else list(
            self._entries)
        return [e.describe() for e in entries]


__all__ = [
    "ORIGIN_HUMAN_GESTURE", "ORIGIN_OMEGALLM_JEV", "ORIGIN_GESTURE_JEV",
    "ORIGIN_PATTERN_REPLAY", "ORIGIN_PATTERN_PERFORM", "ORIGINS",
    "MAX_HISTORY", "MAX_SCENE_HISTORY",
    "GovernedAction", "GovernedHistory",
]
