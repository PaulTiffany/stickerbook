"""Host-owned bridge from semantic goals to OmegaJev choices.

OmegaLLM and OmegaJev are separate cognitive loops:

    child language -> OmegaLLM -> bounded goal
    bounded goal + world feedback -> OmegaJev -> ACTION KEY
    ACTION KEY -> StickerBook kernel -> Receipt

A child double-click enters the same OmegaJev selection seam without passing
through OmegaLLM.  In that case the choice surface is animation-only.

This module contains no model inference and no network code.  It creates only
finite, host-owned choices and applies a selected key through Kernel.propose_key.

One rule governs every path here that consults a model:

    A finite action table containing absolute move destinations is valid only
    against the world revision from which that table was constructed. Model
    think-time never refreshes the revision attached to an old choice.

`_move_candidates` bakes the subject's position at table-build time into each
MOVE key's destination coordinates, so a choice made against that table is a
statement about that world, not about a later one. Every proposal therefore
names the revision its own table came from. If a child moved the subject while
the chooser was thinking, the kernel returns `stale-revision` and the old
coordinate is never applied.
"""

from __future__ import annotations

import math
import os
import sys
from contextlib import nullcontext

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))

from stickerbook_core import (  # noqa: E402
    ANIMATE_OWN_STICKER, MOVE_STICKER, NOOP, RESIZE_OWN_STICKER,
    SET_STICKER_FACING,
)

from governed_history import (  # noqa: E402
    ORIGIN_GESTURE_JEV, ORIGIN_HUMAN_GESTURE, ORIGIN_OMEGALLM_JEV,
    ORIGIN_PATTERN_PERFORM, ORIGIN_PATTERN_REPLAY,
    ORIGIN_TRAJECTORY_AGENT, ORIGIN_TRAJECTORY_MECHANICAL,
)
from pattern_memory import (  # noqa: E402
    COMPLETED, MODE_AGENT, MODE_MECHANICAL, PARTIAL, PatternReplayRecord,
    MAX_PATTERN_STEPS, PatternStep, ReplayStepRecord, STOPPED, bind_key,
    split_key, steps_from_trace, valid_label,
)

import trajectory_execution  # noqa: E402

OMEGA_LLM_ID = "agent:omega-llm"
OMEGA_JEV_ID = "agent:jev-visual-1"
# The deterministic reference selector. Named in receipts so a trajectory
# move is never mistaken for a hand drag, exactly as a Jev-selected move is
# not: `selected_by` records that a controller chose this, under the child's
# authority, and the kernel reads it to preserve the chosen clip.
MECHANICAL_SELECTOR_ID = "host:trajectory-argmin"
# The decision context type handed to OmegaJev when it is choosing a
# motor step along a trajectory. Deliberately NOT one of the ordinary
# semantic goal intents: it never passes through normalize_goal, so the
# ordinary goal vocabulary stays closed and `frame` never becomes an
# acceptable field on an unrelated intent.
TRAJECTORY_DECISION = "follow-trajectory"
MAX_AGENT_TRAJECTORY_STEPS = (
    trajectory_execution.MAX_AGENT_TRAJECTORY_STEPS)
MOVE_STEP = 0.06
MAX_GOAL_TURNS = 6

_ALLOWED_GOAL_FIELDS = frozenset({
    "subject", "intent", "behavior", "target", "facing", "scale",
    # Pattern intents refer to a remembered behaviour by the child-facing
    # name, or by an already-resolved id. Neither is an action.
    "label", "pattern",
})

# Semantic intents OmegaLLM may express. The first four drive the ordinary
# bounded Jev control loop. The last two are about remembered behaviour:
# they are still semantic goals, not mutations, and neither carries steps.
REMEMBER_PATTERN = "remember-pattern"
PERFORM_PATTERN = "perform-pattern"

_ALLOWED_INTENTS = frozenset({
    "control", "animate", "move", "move-and-animate",
    REMEMBER_PATTERN, PERFORM_PATTERN,
})
_PATTERN_INTENTS = frozenset({REMEMBER_PATTERN, PERFORM_PATTERN})


class JevController:
    """Finite choice adapter around a Jev decision runtime."""

    def __init__(self, kernel, runtime, selector_id: str = OMEGA_JEV_ID,
                 patterns=None, history=None, replays=None, world_lock=None,
                 executions=None, activity=None):
        self.activity = activity or (lambda: 0)
        self.kernel = kernel
        self.runtime = runtime
        self.selector_id = selector_id
        # Optional host serialization for the world operation only. The
        # kernel has no internal lock, so a coherent read and the mutation
        # that follows it are each held briefly. Model think-time is NEVER
        # inside it: runtime.choose() always runs with the lock released.
        # This orders concurrent host work; based_on_revision still decides.
        self.world_lock = world_lock
        # Host-owned movement memory. Optional: everything below degrades to
        # "no patterns known" when it is absent, and the Jev seam is
        # unchanged. The library is never passed to the runtime.
        self.patterns = patterns
        # Host-owned record of what actually happened, and host-side audit of
        # attempts to perform remembered behaviour. Both observe authority
        # events; neither possesses authority.
        self.history = history
        self.replays = replays
        # Bounded audit of trajectory-following attempts. Observation only:
        # absent, following still works and is simply not logged.
        self.executions = executions

    def _world(self):
        """Hold the host world lock, when one was supplied, or nothing."""
        return nullcontext() if self.world_lock is None else self.world_lock

    def available(self) -> bool:
        # Deliberately unlocked: the live adapter's health probe is network
        # I/O, and no world state is read or written here.
        try:
            return bool(self.runtime.available())
        except Exception:
            return False

    def normalize_goal(self, raw: dict) -> tuple[dict | None, str | None]:
        if not isinstance(raw, dict):
            return None, "invalid-jev-goal"
        unknown = set(raw) - _ALLOWED_GOAL_FIELDS
        if unknown:
            return None, "unknown-jev-goal-field"

        subject = raw.get("subject")
        if not isinstance(subject, str) or not subject:
            return None, "missing-jev-subject"
        sticker = self.kernel.sticker(subject)
        if sticker is None:
            return None, "unknown-jev-subject"

        intent = raw.get("intent", "control")
        if intent not in _ALLOWED_INTENTS:
            return None, "invalid-jev-intent"

        goal = {"subject": subject, "intent": intent}

        label = raw.get("label")
        if label is not None:
            if not valid_label(label):
                return None, "invalid-jev-label"
            goal["label"] = " ".join(label.split())

        reference = raw.get("pattern")
        if reference is not None:
            if not isinstance(reference, str) or not reference                     or len(reference) > 64 or ":" in reference:
                return None, "invalid-jev-pattern-reference"
            goal["pattern"] = reference

        # A remembered behaviour has to be nameable. Performing one has to
        # say which one. Neither intent may carry movement data.
        if intent == REMEMBER_PATTERN and "label" not in goal:
            return None, "missing-jev-label"
        if intent == PERFORM_PATTERN                 and "label" not in goal and "pattern" not in goal:
            return None, "missing-jev-pattern-reference"

        behavior = raw.get("behavior")
        if behavior is not None:
            if not isinstance(behavior, str) or not behavior or len(behavior) > 80:
                return None, "invalid-jev-behavior"
            goal["behavior"] = behavior

        facing = raw.get("facing")
        if facing is not None:
            if facing not in ("left", "right"):
                return None, "invalid-jev-facing"
            goal["facing"] = facing

        scale = raw.get("scale")
        if scale is not None:
            if isinstance(scale, bool):
                return None, "invalid-jev-scale"
            try:
                scale = float(scale)
            except (TypeError, ValueError):
                return None, "invalid-jev-scale"
            if not math.isfinite(scale) or not 0.90 <= scale <= 1.10:
                return None, "invalid-jev-scale"
            goal["scale"] = scale

        target = raw.get("target")
        if target is not None:
            clean, error = self._target(target)
            if error:
                return None, error
            goal["target"] = clean

        return goal, None

    def _target(self, raw):
        if not isinstance(raw, dict):
            return None, "invalid-jev-target"
        kind = raw.get("kind")
        if kind == "sticker":
            if set(raw) != {"kind", "id"}:
                return None, "invalid-jev-target"
            sticker_id = raw.get("id")
            if not isinstance(sticker_id, str) or not sticker_id:
                return None, "invalid-jev-target"
            sticker = self.kernel.sticker(sticker_id)
            if sticker is None:
                return None, "unknown-jev-target"
            return {"kind": "sticker", "id": sticker_id}, None
        if kind == "point":
            if set(raw) != {"kind", "x", "y"}:
                return None, "invalid-jev-target"
            clean = {"kind": "point"}
            for name in ("x", "y"):
                value = raw.get(name)
                if isinstance(value, bool):
                    return None, "invalid-jev-target"
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    return None, "invalid-jev-target"
                if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                    return None, "invalid-jev-target"
                clean[name] = value
            return clean, None
        return None, "invalid-jev-target"

    def _move_candidates(self, sticker) -> dict:
        """Eight local steps; continuous page geometry remains authoritative."""
        dirs = {
            "STEP-N": (0.0, -MOVE_STEP),
            "STEP-NE": (MOVE_STEP, -MOVE_STEP),
            "STEP-E": (MOVE_STEP, 0.0),
            "STEP-SE": (MOVE_STEP, MOVE_STEP),
            "STEP-S": (0.0, MOVE_STEP),
            "STEP-SW": (-MOVE_STEP, MOVE_STEP),
            "STEP-W": (-MOVE_STEP, 0.0),
            "STEP-NW": (-MOVE_STEP, -MOVE_STEP),
        }
        out = {}
        for name, (dx, dy) in dirs.items():
            x = min(1.0, max(0.0, sticker.x + dx))
            y = min(1.0, max(0.0, sticker.y + dy))
            if x != sticker.x or y != sticker.y:
                out[name] = (round(x, 6), round(y, 6))
        return out

    def _scene(self, actor: str, goal: dict, table: dict,
               pattern_context=None) -> dict:
        subject = self.kernel.sticker(goal["subject"])
        definition = self.kernel.assets.get(subject.asset)

        def describe(sticker):
            if sticker is None:
                return None
            definition = self.kernel.assets.get(sticker.asset)
            return {
                "id": sticker.id,
                "definition": sticker.asset,
                "x": sticker.x,
                "y": sticker.y,
                "scale": sticker.scale,
                "facing": sticker.facing,
                "clip": sticker.animation,
                "rest_clip": (
                    definition.rest_animation if definition else "none"),
                "clips": list(definition.animations if definition else ("none",)),
                "revision": sticker.revision,
            }

        target_state = None
        target = goal.get("target")
        if target and target["kind"] == "sticker":
            target_state = describe(self.kernel.sticker(target["id"]))
        elif target and target["kind"] == "point":
            target_state = dict(target)

        # Read-only, bounded, declarative. Pattern memory may INFORM a
        # chooser; it can never manufacture a choice. These entries carry no
        # StickerInstance id and no complete action key, so nothing here can
        # be submitted to the kernel. The chooser still has to pick a key
        # from available_actions.
        known_patterns = []
        if self.patterns is not None and subject is not None:
            known_patterns = self.patterns.describe_for_scene(subject.asset)

        scene_pattern = None
        if pattern_context is not None:
            # The remembered behaviour being asked for, plus which step the
            # host is on. Declarative only: typed fragments, never keys. Jev
            # still has to pick from available_actions.
            pattern, step_index = pattern_context
            scene_pattern = dict(pattern.describe())
            scene_pattern["stepIndex"] = step_index
            scene_pattern["nextStep"] = (
                pattern.steps[step_index].to_dict()
                if step_index < len(pattern.steps) else None)

        return {
            "revision": self.kernel.revision,
            "turn": self.kernel.turn,
            "principal": actor,
            "goal": dict(goal),
            "subject": describe(subject),
            "target": target_state,
            "available_actions": sorted(table),
            "known_patterns": known_patterns,
            "pattern": scene_pattern,
        }

    @staticmethod
    def _describe_actions(table: dict) -> dict:
        out = {}
        for key, command in table.items():
            if command.action == NOOP:
                out[key] = (
                    "Do nothing. Choose only when no offered action should be "
                    "taken for the stated goal.")
            elif command.action == MOVE_STICKER:
                out[key] = (
                    "Move the subject one local step to x=%s y=%s."
                    % (command.param("x"), command.param("y")))
            elif command.action == ANIMATE_OWN_STICKER:
                out[key] = (
                    "Set the subject visual clip to '%s'."
                    % command.param("animation"))
            elif command.action == RESIZE_OWN_STICKER:
                out[key] = (
                    "Set the subject scale to %s." % command.param("scale"))
            elif command.action == SET_STICKER_FACING:
                out[key] = (
                    "Face the subject %s." % command.param("facing"))
        return out

    def _table(self, actor: str, goal: dict, *, animate_only: bool = False,
               move_only: bool = False) -> tuple:
        """The subject's current finite choice surface, plus NOOP.

        `animate_only` is the child double-tap surface. `move_only` is the
        narrow surface a continuous movement objective needs: the subject's
        currently legal local steps and nothing that changes its appearance,
        so a chooser cannot satisfy a movement goal by animating, resizing or
        turning instead. Both are filters over the ordinary host-owned table;
        neither invents a choice, and the kernel still decides.
        """
        subject = self.kernel.sticker(goal["subject"])
        moves = self._move_candidates(subject)
        raw = self.kernel.available_actions(actor, move_candidates=moves)
        prefix = ":" + subject.id + ":"
        allowed = {}
        for key, command in raw.items():
            if key == "NOOP":
                allowed[key] = command
                continue
            if prefix not in key:
                continue
            if animate_only:
                if command.action == ANIMATE_OWN_STICKER:
                    allowed[key] = command
            elif move_only:
                if command.action == MOVE_STICKER:
                    allowed[key] = command
            elif command.action in (
                    MOVE_STICKER, ANIMATE_OWN_STICKER,
                    RESIZE_OWN_STICKER, SET_STICKER_FACING):
                allowed[key] = command
        return allowed, moves

    def run_goal(
            self, raw_goal: dict, *, actor: str, command_prefix: str,
            requested_by: str, translated_by: str | None = None,
            animate_only: bool = False,
            max_turns: int = MAX_GOAL_TURNS) -> dict:
        if not self.available():
            return {"ok": False, "error": "jev-runtime-unavailable"}

        goal, error = self.normalize_goal(raw_goal)
        if error:
            return {"ok": False, "error": error}

        max_turns = max(1, min(int(max_turns), MAX_GOAL_TURNS))
        trace = []
        activation = self.activity()

        for index in range(max_turns):
            # One coherent read: table, scene, and the revision the choice is
            # made against all describe the same world.
            with self._world():
                if activation is None or self.activity() != activation:
                    return {"ok": False, "error": "page-changed", "goal": goal, "trace": trace}
                table, moves = self._table(
                    actor, goal, animate_only=animate_only)
                scene = self._scene(actor, goal, table) if table else None
            if not table:
                return {
                    "ok": False,
                    "error": "no-legal-jev-actions",
                    "goal": goal,
                    "trace": trace,
                }

            descriptions = self._describe_actions(table)
            # OmegaJev think-time, with no lock held. A child may move a
            # sticker meanwhile; scene["revision"] below lets the kernel
            # refuse a choice made against a world that has since moved.
            try:
                decision = self.runtime.choose(
                    goal=dict(goal),
                    scene=scene,
                    actions=descriptions,
                    turn=index + 1,
                    max_turns=max_turns,
                )
            except Exception:
                return {
                    "ok": False,
                    "error": "jev-runtime-error",
                    "goal": goal,
                    "trace": trace,
                }

            if not isinstance(decision, dict) or not decision.get("ok"):
                return {
                    "ok": False,
                    "error": (
                        decision.get("error", "invalid-jev-decision")
                        if isinstance(decision, dict)
                        else "invalid-jev-decision"),
                    "goal": goal,
                    "trace": trace,
                }
            choice = decision.get("choice")
            if not isinstance(choice, str) or choice not in table:
                return {
                    "ok": False,
                    "error": "unknown-jev-choice",
                    "goal": goal,
                    "trace": trace,
                }

            with self._world():
                if self.activity() != activation:
                    return {"ok": False, "error": "page-changed", "goal": goal, "trace": trace}
                receipt = self.kernel.propose_key(
                    actor,
                    choice,
                    "%s-%d" % (command_prefix, index + 1),
                    based_on_revision=scene["revision"],
                    requested_by=requested_by,
                    translated_by=translated_by,
                    selected_by=self.selector_id,
                    move_candidates=moves,
                )
                self._record(
                    receipt,
                    origin=(ORIGIN_OMEGALLM_JEV if translated_by
                            else ORIGIN_GESTURE_JEV),
                    key=choice,
                    subject_id=goal["subject"])
            trace.append({
                "turn": index + 1,
                "choice": choice,
                "receipt": receipt.to_dict(),
            })

            if not receipt.accepted:
                return {
                    "ok": False,
                    "error": "jev-action-refused",
                    "goal": goal,
                    "trace": trace,
                }
            if choice == "NOOP":
                return {
                    "ok": True,
                    "goal": goal,
                    "trace": trace,
                    "stopped": "noop",
                }
            if index + 1 < max_turns:
                with self._world():
                    self.kernel.begin_turn()

        return {
            "ok": True,
            "goal": goal,
            "trace": trace,
            "stopped": "turn-limit",
        }

    # -- movement-pattern memory -------------------------------------
    #
    # A child teaching a sticker a way to move is remembering, not granting.
    # Capture reads only ACCEPTED receipts; replay re-derives every key from
    # the CURRENT world and submits it through the ordinary kernel path.

    def _record(self, receipt, *, origin, key=None, subject_id=None):
        """Note one governed action in host-owned history, if it is present."""
        if self.history is None:
            return None
        return self.history.record(
            receipt, origin=origin, key=key, subject_id=subject_id)

    def _next_replay_id(self) -> str:
        if self.replays is not None:
            return self.replays.next_replay_id()
        self._local_replay_counter = getattr(
            self, "_local_replay_counter", 0) + 1
        return "replay-local-%d" % self._local_replay_counter

    @staticmethod
    def _replay_result(step_records, planned, stopped_reason):
        accepted = sum(
            1 for r in step_records
            if r.receipt is not None and r.receipt.get("accepted") is True)
        if stopped_reason is None and planned > 0 and accepted == planned:
            return COMPLETED
        if accepted > 0:
            return PARTIAL
        return STOPPED

    def _finish_replay(self, *, replay_id, pattern, subject_id, requested_by,
                       starting_revision, mode, step_records, planned,
                       stopped_at, stopped_reason):
        """Build and file the host-side audit record for one replay attempt.

        This observes and groups authority events. It has no authority, and
        the kernel never learns what a "happy dance" is: its receipts stay
        ordinary mutation receipts.
        """
        record = PatternReplayRecord(
            replay_id=replay_id,
            pattern_id=pattern.pattern_id,
            label=pattern.label,
            subject_id=subject_id,
            requested_by=requested_by,
            starting_revision=starting_revision,
            mode=mode,
            planned_steps=planned,
            steps=tuple(step_records),
            result=self._replay_result(
                step_records, planned, stopped_reason),
            stopped_at=stopped_at,
            stopped_reason=stopped_reason,
        )
        if self.replays is not None:
            self.replays.add(record)
        return record

    @staticmethod
    def _replay_payload(record, pattern, subject_id):
        payload = {
            "ok": record.result == COMPLETED,
            "result": record.result,
            "pattern": pattern.pattern_id,
            "label": pattern.label,
            "subject": subject_id,
            "plannedSteps": record.planned_steps,
            "submittedSteps": record.submitted_steps,
            "acceptedSteps": record.accepted_steps,
            "replay": record.to_dict(),
        }
        if record.stopped_reason:
            payload["error"] = record.stopped_reason
        return payload

    # -- "remember that" ----------------------------------------------

    def remember_recent(self, *, subject_id, label, learned_by,
                        max_steps=None):
        """Give "that" a safe meaning, from what the host saw actually happen.

        OmegaLLM decides that the child meant "remember", which sticker they
        meant and what to call it. It does NOT choose the historical slice.
        The host resolves "that" to one deterministic, bounded episode from
        its own governed history: the latest contiguous learnable accepted
        run for the named subject, ending before this request.

        An episode ends at a switch to another subject, at a non-learnable
        action on this subject, at the pattern-length limit, or at the edge of
        the bounded history window. See `GovernedHistory.latest_episode`.
        """
        if self.patterns is None:
            return {"ok": False, "error": "pattern-memory-unavailable"}
        if self.history is None:
            return {"ok": False, "error": "governed-history-unavailable"}
        if not valid_label(label):
            return {"ok": False, "error": "invalid-pattern-label"}
        subject = self.kernel.sticker(subject_id)
        if subject is None:
            return {"ok": False, "error": "unknown-pattern-subject"}

        limit = int(max_steps) if max_steps else self.patterns.max_steps
        entries = self.history.latest_episode(
            subject_id, limit,
            is_learnable=lambda e: split_key(e.key, subject_id) is not None)

        steps = []
        resolved_from = []
        for entry in entries:
            steps.append(split_key(entry.key, subject_id))
            resolved_from.append(entry.sequence)

        if not steps:
            return {"ok": False, "error": "no-accepted-pattern-steps"}

        pattern, error = self.patterns.remember(
            label=label,
            asset=subject.asset,
            steps=tuple(steps),
            subject_id=subject_id,
            learned_by=learned_by,
            revision=self.kernel.revision,
        )
        if error:
            return {"ok": False, "error": error}
        return {
            "ok": True,
            "pattern": pattern.to_dict(),
            "resolvedFrom": resolved_from,
        }

    def remember_trace(self, *, label, subject_id, trace, learned_by):
        """Remember an explicitly supplied accepted trace.

        The narrower sibling of `remember_recent`, kept for callers that
        already hold the trace they mean -- notably the deterministic
        mechanical path. Same rule: only accepted receipts become steps.
        """
        if self.patterns is None:
            return {"ok": False, "error": "pattern-memory-unavailable"}
        subject = self.kernel.sticker(subject_id)
        if subject is None:
            return {"ok": False, "error": "unknown-pattern-subject"}

        steps, error = steps_from_trace(trace, subject_id)
        if error:
            return {"ok": False, "error": error}

        pattern, error = self.patterns.remember(
            label=label,
            asset=subject.asset,
            steps=steps,
            subject_id=subject_id,
            learned_by=learned_by,
            revision=self.kernel.revision,
        )
        if error:
            return {"ok": False, "error": error}
        return {"ok": True, "pattern": pattern.to_dict()}

    # -- "do that again" ----------------------------------------------

    def resolve_pattern(self, goal, subject):
        """Resolve a bounded pattern reference. Returns (pattern, error)."""
        if self.patterns is None:
            return None, "pattern-memory-unavailable"
        pattern = None
        reference = goal.get("pattern")
        if reference:
            pattern = self.patterns.get(reference)
        if pattern is None and goal.get("label"):
            pattern = self.patterns.by_label(
                goal["label"], asset=subject.asset)
        if pattern is None:
            return None, "unknown-pattern"
        if pattern.asset != subject.asset:
            return None, "pattern-definition-mismatch"
        return pattern, None

    def perform_known_pattern(self, goal, *, actor, command_prefix,
                              requested_by, translated_by=None):
        """Perform a remembered behaviour through OmegaJev.

        This is the powered path. OmegaJev is handed fresh state, the current
        finite legal-action table and bounded pattern context, and chooses one
        offered key per step. Memory informs the choice; it never creates one,
        and the kernel still decides every mutation.
        """
        if not self.available():
            return {"ok": False, "error": "jev-runtime-unavailable"}
        subject_id = goal["subject"]
        subject = self.kernel.sticker(subject_id)
        if subject is None:
            return {"ok": False, "error": "unknown-pattern-subject"}
        pattern, error = self.resolve_pattern(goal, subject)
        if error:
            return {"ok": False, "error": error}

        replay_id = self._next_replay_id()
        starting_revision = self.kernel.revision
        step_records = []
        stopped_at = None
        stopped_reason = None

        # The episode is bounded by the remembered length, not by open-ended
        # search, so it does not borrow the ordinary goal turn limit.
        planned = min(len(pattern.steps), MAX_PATTERN_STEPS)
        activation = self.activity()

        for index in range(planned):
            # One coherent read per step: subject, current legal table and
            # the scene OmegaJev will answer against.
            with self._world():
                subject = self.kernel.sticker(subject_id)
                table, moves = (self._table(actor, goal, animate_only=False)
                                if subject is not None else (None, None))
                scene = self._scene(
                    actor, goal, table, pattern_context=(pattern, index)
                ) if table else None
            if subject is None:
                stopped_at = index + 1
                stopped_reason = "unknown-pattern-subject"
                break
            if subject.asset != pattern.asset:
                stopped_at = index + 1
                stopped_reason = "pattern-definition-mismatch"
                break

            if not table:
                stopped_at = index + 1
                stopped_reason = "no-legal-jev-actions"
                break

            descriptions = self._describe_actions(table)
            # OmegaJev think-time, with no lock held.
            try:
                decision = self.runtime.choose(
                    goal=dict(goal),
                    scene=scene,
                    actions=descriptions,
                    turn=index + 1,
                    max_turns=planned,
                )
            except Exception:
                stopped_at = index + 1
                stopped_reason = "jev-runtime-error"
                break

            if not isinstance(decision, dict) or not decision.get("ok"):
                stopped_at = index + 1
                stopped_reason = (
                    decision.get("error", "invalid-jev-decision")
                    if isinstance(decision, dict) else "invalid-jev-decision")
                break

            choice = decision.get("choice")
            if not isinstance(choice, str) or choice not in table:
                stopped_at = index + 1
                stopped_reason = "unknown-jev-choice"
                break
            if choice == "NOOP":
                # Jev declined. Report WHY, so this path reads the same as
                # mechanical replay: if the remembered form is simply not
                # offered any more, the world changed, and saying "jev-noop"
                # would blame the chooser for it.
                stopped_at = index + 1
                remembered = pattern.steps[index]
                if bind_key(remembered, subject_id) not in table:
                    step_records.append(ReplayStepRecord(
                        index=index + 1, verb=remembered.verb,
                        suffix=remembered.suffix, submitted=False,
                        unavailable_reason="pattern-step-unavailable"))
                    stopped_reason = "pattern-step-unavailable"
                else:
                    stopped_reason = "jev-noop"
                break

            step = split_key(choice, subject_id)
            if step is None:
                stopped_at = index + 1
                stopped_reason = "unknown-jev-choice"
                break

            with self._world():
                if activation is None or self.activity() != activation:
                    stopped_at, stopped_reason = index + 1, "page-changed"
                    break
                # scene["revision"], NOT a fresh read: `moves` holds absolute
                # destinations derived from the subject as it was when this
                # table was built, and Jev chose against that table. Re-reading
                # the revision here would submit an old coordinate as though it
                # were current, so a child who moved this sticker during
                # inference would be silently dragged back. The kernel refuses
                # the stale choice instead.
                receipt = self.kernel.propose_key(
                    actor,
                    choice,
                    "%s-%d" % (command_prefix, index + 1),
                    based_on_revision=scene["revision"],
                    requested_by=requested_by,
                    translated_by=translated_by,
                    selected_by=self.selector_id,
                    move_candidates=moves,
                )
                self._record(
                    receipt, origin=ORIGIN_PATTERN_PERFORM, key=choice,
                    subject_id=subject_id)
            step_records.append(ReplayStepRecord(
                index=index + 1, verb=step.verb, suffix=step.suffix,
                submitted=True, receipt=receipt.to_dict()))

            if not receipt.accepted:
                stopped_at = index + 1
                stopped_reason = "pattern-step-refused"
                break

        record = self._finish_replay(
            replay_id=replay_id, pattern=pattern, subject_id=subject_id,
            requested_by=requested_by, starting_revision=starting_revision,
            mode=MODE_AGENT, step_records=step_records, planned=planned,
            stopped_at=stopped_at, stopped_reason=stopped_reason)
        return self._replay_payload(record, pattern, subject_id)

    def replay_pattern(self, pattern_id, *, subject_id, actor,
                       command_prefix, requested_by):
        """Re-perform a remembered pattern as a sequence of FRESH proposals.

        The deterministic mechanical reference path. The host drives the steps
        itself so pattern representation, rebinding, fresh legality, kernel
        authority and partial behaviour can be verified without live
        inference. It is not a macro with authority, and it uses the same
        PatternStep representation and the same current legal-action table as
        the OmegaJev path.
        """
        if self.patterns is None:
            return {"ok": False, "error": "pattern-memory-unavailable"}
        pattern = self.patterns.get(pattern_id)
        if pattern is None:
            return {"ok": False, "error": "unknown-pattern"}

        replay_id = self._next_replay_id()
        starting_revision = self.kernel.revision
        step_records = []
        stopped_at = None
        stopped_reason = None
        planned = len(pattern.steps)

        for index, step in enumerate(pattern.steps):
            # No model is consulted on this path, so one step's current read
            # and its proposal are a single brief world operation.
            receipt = None
            with self._world():
                # 1. fresh current state, every step
                subject = self.kernel.sticker(subject_id)
                # A pattern belongs to a StickerDefinition. An incompatible
                # definition never inherits it by accident.
                if subject is None:
                    stopped_reason = "unknown-pattern-subject"
                elif subject.asset != pattern.asset:
                    stopped_reason = "pattern-definition-mismatch"
                else:
                    # 2. rebuild the current host-owned legal table, and
                    # keep the revision it was built from
                    moves = self._move_candidates(subject)
                    table = self.kernel.available_actions(
                        actor, move_candidates=moves)
                    table_revision = self.kernel.revision

                    # 3. re-bind the stored fragment to the current instance
                    key = bind_key(step, subject_id)

                    # 4. the key has to exist in the table as it is right now
                    if key not in table:
                        stopped_reason = "pattern-step-unavailable"
                    else:
                        # 5. ordinary kernel proposal path; no pattern-level
                        # privilege. No model is consulted here, so the table
                        # revision is still current -- but the proposal names
                        # it explicitly, because the table's absolute move
                        # destinations are only valid against it.
                        receipt = self.kernel.propose_key(
                            actor,
                            key,
                            "%s-%d" % (command_prefix, index + 1),
                            based_on_revision=table_revision,
                            requested_by=requested_by,
                            move_candidates=moves,
                        )
                        self._record(
                            receipt, origin=ORIGIN_PATTERN_REPLAY, key=key,
                            subject_id=subject_id)
            if receipt is None:
                if stopped_reason == "pattern-step-unavailable":
                    step_records.append(ReplayStepRecord(
                        index=index + 1, verb=step.verb, suffix=step.suffix,
                        submitted=False,
                        unavailable_reason="pattern-step-unavailable"))
                stopped_at = index + 1
                break
            step_records.append(ReplayStepRecord(
                index=index + 1, verb=step.verb, suffix=step.suffix,
                submitted=True, receipt=receipt.to_dict()))

            # 6. an accepted receipt is required before advancing
            if not receipt.accepted:
                stopped_at = index + 1
                stopped_reason = "pattern-step-refused"
                break

        record = self._finish_replay(
            replay_id=replay_id, pattern=pattern, subject_id=subject_id,
            requested_by=requested_by, starting_revision=starting_revision,
            mode=MODE_MECHANICAL, step_records=step_records,
            planned=planned, stopped_at=stopped_at,
            stopped_reason=stopped_reason)
        return self._replay_payload(record, pattern, subject_id)

    # -- following a demonstrated trajectory ---------------------------
    #
    # A resolved trajectory reference is frozen observation of what the child
    # drew. Following it is an ordinary bounded control loop: the host derives
    # one CURRENT local objective, builds the CURRENT move_only legal surface,
    # a selector picks one offered key, and the kernel decides. Nothing is
    # precompiled, so possessing a trajectory grants no more than the right to
    # propose one ordinary move at a time.
    #
    # `select` is the seam. The deterministic argmin below is the reference
    # implementation; a powered follower swaps in a chooser with the same
    # signature and reuses the objective, progress, table, revision, audit,
    # completion and boundary behaviour unchanged.

    def _history_watermark(self) -> int:
        """The newest governed sequence number the host has recorded."""
        if self.history is None:
            return 0
        entries = self.history.entries()
        return entries[-1].sequence if entries else 0

    def _human_moved_since(self, subject_id: str, watermark: int) -> bool:
        """Did the CHILD themselves move this sticker since the snapshot?

        Deliberately narrow. A global revision change is not evidence: the
        kernel's staleness check is per-sticker, and other paths can mutate
        this same subject. Only an accepted direct-gesture record for THIS
        subject, newer than the snapshot, establishes supersession.
        """
        if self.history is None:
            return False
        for entry in self.history.entries():
            if entry.sequence > watermark and entry.accepted \
                    and entry.subject_id == subject_id \
                    and entry.origin == ORIGIN_HUMAN_GESTURE:
                return True
        return False

    @staticmethod
    def _mechanical_choice(snapshot: dict) -> dict:
        """Deterministic reference selector: nearest offered destination.

        Only real MOVE choices compete; NOOP is not a geometric candidate.
        Ties are broken by action key, so a page edge that offers two keys
        with the same clamped destination always yields the same recorded
        key -- a bookkeeping choice, not a different physical path.
        """
        objective = snapshot["objective"]
        target = (objective["x"], objective["y"])
        ranked = sorted(
            snapshot["destinations"].items(),
            key=lambda item: (
                trajectory_execution.distance(item[1], target), item[0]))
        if not ranked:
            return {"ok": False, "error": "no-move-candidates"}
        return {"ok": True, "choice": ranked[0][0]}

    def follow_trajectory(self, reference, *, actor, command_prefix,
                          requested_by, select=None, mode=MODE_MECHANICAL,
                          origin=ORIGIN_TRAJECTORY_MECHANICAL,
                          selected_by=MECHANICAL_SELECTOR_ID,
                          translated_by=None,
                          decline_reason=None, max_decisions=None):
        """Follow one resolved subject-frame trajectory, step by step.

        `select` is the only thing a powered follower changes. `mode`,
        `origin`, `selected_by`, `decline_reason` and `max_decisions` are
        audit and resource metadata for whichever chooser is in use; every
        geometric and authority decision below is shared.
        """
        if reference.frame != trajectory_execution.FRAME_SUBJECT:
            return {"ok": False, "error": trajectory_execution.NOT_EXECUTABLE}
        points = reference.resolved_samples
        if not points:
            return {"ok": False, "error": trajectory_execution.NO_GEOMETRY}

        subject_id = reference.subject
        goal = {"subject": subject_id}
        select = select or self._mechanical_choice
        reach = MOVE_STEP

        execution_id = self._next_execution_id()
        planned = trajectory_execution.planned_steps(points, reach)
        steps = []
        progress = 0
        decisions = 0
        detail = None
        complete = False
        stopped_at = None
        stopped_reason = None
        decline_reason = (
            decline_reason or trajectory_execution.STOPPED_SELECTOR_DECLINED)
        with self._world():
            starting_revision = self.kernel.revision

        activation = self.activity()
        while True:
            # 1. One coherent read: subject, progress, objective, the current
            # move_only surface, and the revision they all describe.
            with self._world():
                subject = self.kernel.sticker(subject_id)
                if subject is None:
                    table = moves = None
                    revision = self.kernel.revision
                    position = None
                else:
                    position = (subject.x, subject.y)
                    progress = trajectory_execution.advance(
                        points, progress, position, reach)
                    table, moves = self._table(
                        actor, goal, move_only=True)
                    revision = self.kernel.revision
                watermark = self._history_watermark()

            if subject is None:
                stopped_at = len(steps) + 1
                stopped_reason = \
                    trajectory_execution.STOPPED_UNKNOWN_SUBJECT
                break

            # 2. Completion is host bookkeeping, checked BEFORE selection so
            # it can never be confused with a selector declining.
            if trajectory_execution.is_complete(
                    points, progress, position, reach):
                complete = True
                break

            # The motor safety cap comes first: it bounds control, whoever
            # is choosing.
            if len(steps) >= planned:
                stopped_at = len(steps) + 1
                stopped_reason = trajectory_execution.STOPPED_BUDGET
                break
            # Then the model-resource cap, reported separately because it
            # means something different: the geometry was followable, we just
            # declined to spend more inference on it.
            if max_decisions is not None and decisions >= max_decisions:
                stopped_at = len(steps) + 1
                stopped_reason = trajectory_execution.STOPPED_AGENT_BUDGET
                break

            objective = trajectory_execution.objective_of(points, progress)
            # Only real moves are geometric candidates. NOOP stays in the
            # table the selector sees, because that is the honest legal
            # surface, but it does not compete on distance.
            move_keys = {
                key: command for key, command in table.items()
                if command.action == MOVE_STICKER}
            if not move_keys:
                stopped_at = len(steps) + 1
                stopped_reason = \
                    trajectory_execution.STOPPED_NO_LEGAL_MOVES
                break

            destinations = {
                key: (command.param("x"), command.param("y"))
                for key, command in move_keys.items()}
            # 3. Unreachability is host-determined, also before selection. If
            # nothing offered gets strictly closer, say so truthfully rather
            # than deforming the reference or improvising a detour.
            here = trajectory_execution.distance(position, objective)
            if not any(trajectory_execution.distance(d, objective) < here
                       for d in destinations.values()):
                stopped_at = len(steps) + 1
                stopped_reason = trajectory_execution.STOPPED_UNREACHABLE
                break

            snapshot = {
                "pathRef": reference.path_ref,
                "frame": reference.frame,
                "subject": {"id": subject_id, "x": subject.x, "y": subject.y},
                "progressIndex": progress,
                "waypointCount": len(points),
                "remaining": len(points) - 1 - progress,
                "objective": {"x": objective[0], "y": objective[1]},
                "error": {"dx": objective[0] - position[0],
                          "dy": objective[1] - position[1],
                          "distance": here},
                "next": [{"x": p.x, "y": p.y}
                         for p in points[progress + 1:progress + 3]],
                "revision": revision,
                # The honest current legal surface, NOOP included, as a
                # powered chooser must see it.
                "actions": self._describe_actions(table),
                # Only real moves carry a destination, so only they can
                # compete on distance.
                "destinations": dict(destinations),
            }

            # 4. The selector seam, with NO world lock held. Deterministic
            # here, but structurally identical to a powered chooser: a child
            # must be able to interact while a selection is being made.
            decisions += 1
            try:
                decision = select(snapshot)
            except Exception:
                stopped_at = len(steps) + 1
                stopped_reason = \
                    trajectory_execution.STOPPED_SELECTOR_ERROR
                break
            if not isinstance(decision, dict):
                stopped_at = len(steps) + 1
                stopped_reason = \
                    trajectory_execution.STOPPED_SELECTOR_ERROR
                break
            if not decision.get("ok"):
                # A selector may name its own failure, but only from the
                # host's vocabulary, and any diagnostic text is bounded and
                # never interpreted.
                reported = decision.get("error")
                stopped_at = len(steps) + 1
                stopped_reason = (
                    reported if reported in trajectory_execution.SELECTOR_ERRORS
                    else trajectory_execution.STOPPED_SELECTOR_ERROR)
                said = decision.get("detail")
                if isinstance(said, str):
                    detail = said[:trajectory_execution.MAX_SELECTOR_DETAIL]
                break
            choice = decision.get("choice")
            if choice == "NOOP":
                # Declining to move is a real answer, and not one of
                # completion, unreachability or budget. Nothing asks again.
                stopped_at = len(steps) + 1
                stopped_reason = decline_reason
                break
            if not isinstance(choice, str) or choice not in move_keys:
                stopped_at = len(steps) + 1
                stopped_reason = \
                    trajectory_execution.STOPPED_INVALID_CHOICE
                break

            # 5. Submit against the revision THIS table was built from. The
            # table's move destinations are absolute, so refreshing the
            # revision here would apply an old coordinate as current.
            with self._world():
                if activation is None or self.activity() != activation:
                    stopped_at, stopped_reason = len(steps) + 1, "page-changed"
                    break
                receipt = self.kernel.propose_key(
                    actor,
                    choice,
                    "%s-%d" % (command_prefix, len(steps) + 1),
                    based_on_revision=revision,
                    requested_by=requested_by,
                    translated_by=translated_by,
                    selected_by=selected_by,
                    move_candidates=moves,
                )
                self._record(receipt, origin=origin, key=choice,
                             subject_id=subject_id)

            superseded = (
                not receipt.accepted
                and receipt.reason == "stale-revision"
                and self._human_moved_since(subject_id, watermark))
            steps.append(trajectory_execution.TrajectoryStepRecord(
                index=len(steps) + 1, objective_index=progress,
                objective=objective, submitted=True, choice=choice,
                receipt=receipt.to_dict(), superseded=superseded))

            if not receipt.accepted:
                stopped_at = len(steps)
                if receipt.reason != "stale-revision":
                    stopped_reason = trajectory_execution.STOPPED_REFUSED
                elif superseded:
                    # The child is the higher-authority actor. Their move
                    # stands, the attempt stops, and nothing re-aims.
                    stopped_reason = \
                        trajectory_execution.STOPPED_SUPERSEDED
                else:
                    # Truthfully neutral: this same subject changed by some
                    # other path. Claiming the child did it would be a
                    # fabricated provenance.
                    stopped_reason = \
                        trajectory_execution.STOPPED_WORLD_CHANGED
                break

        record = trajectory_execution.TrajectoryExecutionRecord(
            execution_id=execution_id, path_ref=reference.path_ref,
            frame=reference.frame, source_episode=reference.source_episode,
            subject_id=subject_id, requested_by=requested_by, mode=mode,
            starting_revision=starting_revision, waypoint_count=len(points),
            planned_steps=planned, steps=tuple(steps),
            progress_reached=progress,
            result=trajectory_execution.result_of(steps, complete),
            stopped_at=stopped_at, stopped_reason=stopped_reason,
            decisions=decisions, selector_detail=detail)
        if self.executions is not None:
            self.executions.add(record)
        payload = {
            "ok": record.result == COMPLETED,
            "result": record.result,
            "subject": subject_id,
            "pathRef": reference.path_ref,
            "frame": reference.frame,
            "plannedSteps": record.planned_steps,
            "submittedSteps": record.submitted_steps,
            "acceptedSteps": record.accepted_steps,
            "progressReached": record.progress_reached,
            "decisions": record.decisions,
            "execution": record.to_dict(),
        }
        if record.stopped_reason:
            payload["error"] = record.stopped_reason
        return payload

    def _next_execution_id(self) -> str:
        if self.executions is not None:
            return self.executions.next_execution_id()
        self._local_execution_counter = getattr(
            self, "_local_execution_counter", 0) + 1
        return "trajectory-local-%d" % self._local_execution_counter


    # -- the powered follower -------------------------------------------
    #
    # Identical to the mechanical path in every respect except WHO picks one
    # of the current legal choices. Objective, progress, table construction,
    # revision discipline, completion, boundary behaviour and audit are all
    # the shared implementation above.
    #
    # A trajectory selection is deliberately NOT an ordinary Jev semantic
    # goal. `normalize_goal` and its intent/field vocabulary are untouched:
    # the follower already takes a resolved reference directly, so nothing
    # needs to teach ordinary goals about coordinate frames. What Jev gets is
    # its own narrow decision context, typed by `TRAJECTORY_DECISION`.

    @staticmethod
    def trajectory_scene(snapshot, principal):
        """The bounded declarative scene OmegaJev answers a motor step with.

        Derived entirely from the CURRENT world plus the frozen reference. It
        carries where the subject is, which retained point it is heading for,
        how far off it is, and at most the next two points. It carries NO
        sample arrays, no transcript, no earlier episodes, no drag telemetry
        and no previous action tables, so nothing here could reconstruct the
        drawn path or name an action key the current table does not offer.
        """
        return {
            "revision": snapshot["revision"],
            "principal": principal,
            "subject": snapshot["subject"],
            "available_actions": sorted(snapshot["actions"]),
            "trajectory": {
                "pathRef": snapshot["pathRef"],
                "frame": snapshot["frame"],
                "progressIndex": snapshot["progressIndex"],
                "waypointCount": snapshot["waypointCount"],
                "remaining": snapshot["remaining"],
                "position": {"x": snapshot["subject"]["x"],
                             "y": snapshot["subject"]["y"]},
                "objective": dict(snapshot["objective"]),
                "error": dict(snapshot["error"]),
                "next": [dict(point) for point in snapshot["next"]],
            },
        }

    def _jev_trajectory_select(self, subject_id, *, principal, max_decisions):
        """Build a selector that asks OmegaJev for one offered key.

        Returns a closure so the decision counter belongs to one attempt.
        Same `select(snapshot) -> {"ok", "choice"}` contract the deterministic
        reference selector satisfies, so the follower cannot tell them apart.
        """
        state = {"turn": 0}

        def select(snapshot):
            state["turn"] += 1
            scene = self.trajectory_scene(snapshot, principal)
            try:
                decision = self.runtime.choose(
                    goal={"subject": subject_id,
                          "intent": TRAJECTORY_DECISION},
                    scene=scene,
                    actions=snapshot["actions"],
                    turn=state["turn"],
                    max_turns=max_decisions,
                )
            except Exception:
                # A runtime failure is a failure, never a decision to hold
                # still: collapsing it into NOOP would credit Jev with a
                # judgement it never made.
                return {"ok": False,
                        "error": trajectory_execution.STOPPED_JEV_FAILED,
                        "detail": "jev-runtime-raised"}
            if not isinstance(decision, dict):
                return {"ok": False,
                        "error": trajectory_execution.STOPPED_JEV_FAILED,
                        "detail": "non-object-decision"}
            if not decision.get("ok"):
                detail = decision.get("error")
                return {"ok": False,
                        "error": trajectory_execution.STOPPED_JEV_FAILED,
                        "detail": detail if isinstance(detail, str) else None}
            return {"ok": True, "choice": decision.get("choice")}

        return select

    def follow_trajectory_with_jev(
            self, reference, *, actor, command_prefix, requested_by,
            translated_by=None, max_decisions=MAX_AGENT_TRAJECTORY_STEPS):
        """Follow a resolved subject-frame trajectory, OmegaJev choosing."""
        if not self.available():
            return {"ok": False,
                    "error": trajectory_execution.STOPPED_JEV_UNAVAILABLE}
        return self.follow_trajectory(
            reference, actor=actor, command_prefix=command_prefix,
            requested_by=requested_by, translated_by=translated_by,
            select=self._jev_trajectory_select(
                reference.subject, principal=actor,
                max_decisions=max_decisions),
            mode=MODE_AGENT,
            origin=ORIGIN_TRAJECTORY_AGENT,
            selected_by=self.selector_id,
            decline_reason=trajectory_execution.STOPPED_JEV_NOOP,
            max_decisions=max_decisions)

    # -- semantic goal dispatch ---------------------------------------

    def run_semantic_goal(self, raw_goal, *, actor, command_prefix,
                          requested_by, translated_by=None, learned_by=None):
        """Route one bounded OmegaLLM goal to the right bounded host action.

        OmegaLLM expresses meaning. This decides which governed machinery that
        meaning reaches: remembering reads host history and writes memory,
        performing goes to OmegaJev, and everything else is the ordinary
        bounded control loop. None of these paths lets OmegaLLM author an
        action.
        """
        goal, error = self.normalize_goal(raw_goal)
        if error:
            return {"ok": False, "error": error}

        if goal["intent"] == REMEMBER_PATTERN:
            return self.remember_recent(
                subject_id=goal["subject"],
                label=goal["label"],
                learned_by=learned_by or requested_by)

        if goal["intent"] == PERFORM_PATTERN:
            return self.perform_known_pattern(
                goal, actor=actor, command_prefix=command_prefix,
                requested_by=requested_by, translated_by=translated_by)

        return self.run_goal(
            raw_goal, actor=actor, command_prefix=command_prefix,
            requested_by=requested_by, translated_by=translated_by)

    def double_click(
            self, sticker_id: str, *, actor: str, command_prefix: str,
            requested_by: str) -> dict:
        return self.run_goal(
            {"subject": sticker_id, "intent": "animate"},
            actor=actor,
            command_prefix=command_prefix,
            requested_by=requested_by,
            translated_by=None,
            animate_only=True,
            max_turns=1,
        )
