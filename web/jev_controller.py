"""Host-owned bridge from semantic goals to OmegaJev choices.

OmegaLLM and OmegaJev are separate cognitive loops:

    child language -> OmegaLLM -> bounded goal
    bounded goal + world feedback -> OmegaJev -> ACTION KEY
    ACTION KEY -> StickerBook kernel -> Receipt

A child double-click enters the same OmegaJev selection seam without passing
through OmegaLLM.  In that case the choice surface is animation-only.

This module contains no model inference and no network code.  It creates only
finite, host-owned choices and applies a selected key through Kernel.propose_key.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))

from stickerbook_core import (  # noqa: E402
    ANIMATE_OWN_STICKER, MOVE_STICKER, NOOP, RESIZE_OWN_STICKER,
    SET_STICKER_FACING,
)

from governed_history import (  # noqa: E402
    ORIGIN_GESTURE_JEV, ORIGIN_OMEGALLM_JEV, ORIGIN_PATTERN_PERFORM,
    ORIGIN_PATTERN_REPLAY,
)
from pattern_memory import (  # noqa: E402
    COMPLETED, MODE_AGENT, MODE_MECHANICAL, PARTIAL, PatternReplayRecord,
    MAX_PATTERN_STEPS, PatternStep, ReplayStepRecord, STOPPED, bind_key,
    split_key, steps_from_trace, valid_label,
)

OMEGA_LLM_ID = "agent:omega-llm"
OMEGA_JEV_ID = "agent:jev-visual-1"
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
                 patterns=None, history=None, replays=None):
        self.kernel = kernel
        self.runtime = runtime
        self.selector_id = selector_id
        # Host-owned movement memory. Optional: everything below degrades to
        # "no patterns known" when it is absent, and the Jev seam is
        # unchanged. The library is never passed to the runtime.
        self.patterns = patterns
        # Host-owned record of what actually happened, and host-side audit of
        # attempts to perform remembered behaviour. Both observe authority
        # events; neither possesses authority.
        self.history = history
        self.replays = replays

    def available(self) -> bool:
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

    def _table(self, actor: str, goal: dict, *, animate_only: bool) -> tuple:
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

        for index in range(max_turns):
            table, moves = self._table(actor, goal, animate_only=animate_only)
            if not table:
                return {
                    "ok": False,
                    "error": "no-legal-jev-actions",
                    "goal": goal,
                    "trace": trace,
                }

            scene = self._scene(actor, goal, table)
            descriptions = self._describe_actions(table)
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
    def _replay_result(step_records, expected, stopped_reason):
        accepted = sum(
            1 for r in step_records
            if r.receipt is not None and r.receipt.get("accepted") is True)
        if stopped_reason is None and expected > 0 and accepted == expected:
            return COMPLETED
        if accepted > 0:
            return PARTIAL
        return STOPPED

    def _finish_replay(self, *, replay_id, pattern, subject_id, requested_by,
                       starting_revision, mode, step_records, expected,
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
            steps=tuple(step_records),
            result=self._replay_result(
                step_records, expected, stopped_reason),
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
            "completed": record.completed_steps,
            "steps": len(pattern.steps),
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
        meant and what to call it. It does NOT supply the movement. The host
        resolves the referenced behaviour from its own governed history, and
        only accepted, key-selected mutations can become steps.
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
        entries = self.history.recent_accepted_keyed(subject_id, limit)

        steps = []
        resolved_from = []
        for entry in entries:
            step = split_key(entry.key, subject_id)
            if step is None:
                # An accepted action outside the remembered verb families,
                # such as a removal. Visible in history, not learnable.
                continue
            steps.append(step)
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
        expected = min(len(pattern.steps), MAX_PATTERN_STEPS)

        for index in range(expected):
            subject = self.kernel.sticker(subject_id)
            if subject is None:
                stopped_at = index + 1
                stopped_reason = "unknown-pattern-subject"
                break
            if subject.asset != pattern.asset:
                stopped_at = index + 1
                stopped_reason = "pattern-definition-mismatch"
                break

            table, moves = self._table(actor, goal, animate_only=False)
            if not table:
                stopped_at = index + 1
                stopped_reason = "no-legal-jev-actions"
                break

            scene = self._scene(
                actor, goal, table, pattern_context=(pattern, index))
            descriptions = self._describe_actions(table)
            try:
                decision = self.runtime.choose(
                    goal=dict(goal),
                    scene=scene,
                    actions=descriptions,
                    turn=index + 1,
                    max_turns=expected,
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

            receipt = self.kernel.propose_key(
                actor,
                choice,
                "%s-%d" % (command_prefix, index + 1),
                based_on_revision=self.kernel.revision,
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
            mode=MODE_AGENT, step_records=step_records, expected=expected,
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
        expected = len(pattern.steps)

        for index, step in enumerate(pattern.steps):
            # 1. fresh current state, every step
            subject = self.kernel.sticker(subject_id)
            if subject is None:
                stopped_at = index + 1
                stopped_reason = "unknown-pattern-subject"
                break
            # A pattern belongs to a StickerDefinition. An incompatible
            # definition never inherits it by accident.
            if subject.asset != pattern.asset:
                stopped_at = index + 1
                stopped_reason = "pattern-definition-mismatch"
                break

            # 2. rebuild the current host-owned legal table
            moves = self._move_candidates(subject)
            table = self.kernel.available_actions(
                actor, move_candidates=moves)

            # 3. re-bind the stored fragment to the current instance
            key = bind_key(step, subject_id)

            # 4. the key has to exist in the table as it is right now
            if key not in table:
                step_records.append(ReplayStepRecord(
                    index=index + 1, verb=step.verb, suffix=step.suffix,
                    submitted=False,
                    unavailable_reason="pattern-step-unavailable"))
                stopped_at = index + 1
                stopped_reason = "pattern-step-unavailable"
                break

            # 5. ordinary kernel proposal path; no pattern-level privilege
            receipt = self.kernel.propose_key(
                actor,
                key,
                "%s-%d" % (command_prefix, index + 1),
                based_on_revision=self.kernel.revision,
                requested_by=requested_by,
                move_candidates=moves,
            )
            self._record(
                receipt, origin=ORIGIN_PATTERN_REPLAY, key=key,
                subject_id=subject_id)
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
            expected=expected, stopped_at=stopped_at,
            stopped_reason=stopped_reason)
        return self._replay_payload(record, pattern, subject_id)

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
