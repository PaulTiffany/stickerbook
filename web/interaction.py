"""Bounded host-owned record of which child inputs took part in one turn.

StickerBook is voice-interface-forward, and a child's meaning may be spread
across several signals at once: speech, typing, pointing, boxing an area,
dragging a sticker, and -- later -- drawing a path through empty page space.

    "Make Froggy go like this."   + a sticker drag
    "Put him over there."         + a point
    "Remember that."              + an earlier demonstration

An `InteractionEpisode` says **which bounded signals participated in a
conversational turn**. It does not say what they meant. The host records
facts; OmegaLLM interprets them; OmegaJev chooses; the kernel decides.

So this module deliberately contains no interpretation. It never labels a
trajectory a circle, a loop or a zig-zag, never decides that a point "refers
to" a sticker, and never infers relevance from geometry. Adding any of that
here would make it a third intelligent layer, which the architecture does not
have.

An episode is also not a mutation path. It holds no executable content, no
kernel authority object and no model state, it produces no kernel receipt, and
it never changes the world revision.

    Input history is not world history.

**Segmentation is deliberately modest.** This does not solve the general
problem of deciding where one multimodal human utterance begins and ends. An
episode corresponds to one bounded OmegaLLM conversational turn, and signals
join it only by a deterministic, observable host rule -- never by model
judgement. See `Bridge.converse` for the rule.

**Not hard-coded to sticker drags.** A signal carries a `kind` and a
host-issued `ref`, so a page-path gesture or another bounded input type
can participate without changing the shape of the record.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

# Small explicit bounds. This is a conversation aid, not a surveillance log.
MAX_EPISODES = 24
MAX_SIGNALS_PER_EPISODE = 4

# Input kinds that may currently participate. New bounded input types are
# added here; the record shape does not change.
SIGNAL_STICKER_DRAG = "sticker-drag"
SIGNAL_PAGE_PATH = "page-path"
SIGNAL_KINDS = frozenset({SIGNAL_STICKER_DRAG, SIGNAL_PAGE_PATH})
MAX_OBSERVED_INPUTS = 64

# How the child produced the text. Descriptive only: it confers no authority,
# it is not trusted provenance, and nothing branches on it. The browser is the
# only thing that can honestly know, because it owns the microphone and the
# keyboard.
INPUT_MODE_VOICE = "voice"
INPUT_MODE_TEXT = "text"
INPUT_MODES = frozenset({INPUT_MODE_VOICE, INPUT_MODE_TEXT})


@dataclass(frozen=True)
class InputSignal:
    """One bounded reference to an input the host itself observed.

    A reference, never the raw observation. Full sticker and bare-page
    trajectories stay in their respective host logs.
    """

    kind: str
    ref: str
    subject: Optional[str] = None
    duration_ms: Optional[int] = None
    source_event: Optional[str] = None

    def to_dict(self) -> dict:
        record = {
            "kind": self.kind,
            "ref": self.ref,
            "subject": self.subject,
            "durationMs": self.duration_ms,
        }
        if self.source_event is not None:
            record["sourceEvent"] = self.source_event
        return record


@dataclass(frozen=True)
class ObservedInput:
    sequence: int
    principal: str
    signal: InputSignal


class ObservedInputLog:
    """One host arrival sequence across signal kinds; bounded data only."""

    def __init__(self, max_inputs: int = MAX_OBSERVED_INPUTS):
        self.max_inputs = int(max_inputs)
        self._inputs: List[ObservedInput] = []
        self._next_sequence = 1

    def add(self, principal: str, signal: InputSignal,
            *, issue_event: bool = False) -> ObservedInput:
        if issue_event:
            signal = replace(signal,
                             source_event="input-event-%d" % self._next_sequence)
        observed = ObservedInput(self._next_sequence, principal, signal)
        self._next_sequence += 1
        self._inputs.append(observed)
        if len(self._inputs) > self.max_inputs:
            del self._inputs[:len(self._inputs) - self.max_inputs]
        return observed

    def after(self, marker: int) -> Tuple[ObservedInput, ...]:
        return tuple(item for item in self._inputs if item.sequence > marker)


@dataclass(frozen=True)
class InteractionEpisode:
    """The signals that took part in one conversational turn. Data only."""

    episode_id: str
    principal: str
    sequence: int
    scene_revision: int
    utterance_text: Optional[str] = None
    input_mode: Optional[str] = None
    deictic: Optional[dict] = None
    signals: Tuple[InputSignal, ...] = ()

    def to_dict(self) -> dict:
        return {
            "episodeId": self.episode_id,
            "principal": self.principal,
            "sequence": self.sequence,
            "sceneRevision": self.scene_revision,
            "utterance": self.utterance_text,
            "inputMode": self.input_mode,
            "deicticReference": self.deictic,
            "signals": [s.to_dict() for s in self.signals],
            "signalCount": len(self.signals),
        }

    def describe(self) -> dict:
        """The bounded projection OmegaLLM receives for this turn.

        Everything here is bounded input evidence or a host-issued stamp.
        The voice/text mode and geometry originated at the client. There is no
        interpretation, shape label, or raw trajectory sample data.
        """
        return {
            "episodeId": self.episode_id,
            "sequence": self.sequence,
            "sceneRevision": self.scene_revision,
            "utterance": self.utterance_text,
            "inputMode": self.input_mode,
            "deicticReference": self.deictic,
            "signals": [s.to_dict() for s in self.signals],
        }


def valid_input_mode(value) -> Optional[str]:
    """Normalise a browser-reported input mode, or None."""
    if isinstance(value, str) and value in INPUT_MODES:
        return value
    return None


class InteractionLog:
    """Bounded, host-owned log of recent interaction episodes.

    Not persisted across restart. Not shared between children. Never handed to
    an agent, never consulted by the kernel.
    """

    def __init__(self, max_episodes: int = MAX_EPISODES):
        self.max_episodes = int(max_episodes)
        self._episodes: List[InteractionEpisode] = []
        self._next_id = 1

    def next_sequence(self) -> int:
        """Monotonic host sequence, including turns evicted from the log."""
        return self._next_id - 1

    def __len__(self) -> int:
        return len(self._episodes)

    def next_episode_id(self) -> str:
        episode_id = "episode-%d" % self._next_id
        self._next_id += 1
        return episode_id

    def add(self, episode: InteractionEpisode) -> InteractionEpisode:
        self._episodes.append(episode)
        if len(self._episodes) > self.max_episodes:
            del self._episodes[0:len(self._episodes) - self.max_episodes]
        return episode

    def get(self, episode_id) -> Optional[InteractionEpisode]:
        for episode in self._episodes:
            if episode.episode_id == episode_id:
                return episode
        return None

    def episodes(self) -> Tuple[InteractionEpisode, ...]:
        return tuple(self._episodes)

    def latest(self) -> Optional[InteractionEpisode]:
        return self._episodes[-1] if self._episodes else None


__all__ = [
    "MAX_EPISODES", "MAX_SIGNALS_PER_EPISODE", "MAX_OBSERVED_INPUTS",
    "SIGNAL_STICKER_DRAG", "SIGNAL_PAGE_PATH", "SIGNAL_KINDS",
    "INPUT_MODE_VOICE", "INPUT_MODE_TEXT", "INPUT_MODES",
    "InputSignal", "ObservedInput", "ObservedInputLog",
    "InteractionEpisode", "InteractionLog",
    "valid_input_mode",
]
