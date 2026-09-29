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

OMEGA_LLM_ID = "agent:omega-llm"
OMEGA_JEV_ID = "agent:jev-visual-1"
MOVE_STEP = 0.06
MAX_GOAL_TURNS = 6

_ALLOWED_GOAL_FIELDS = frozenset({
    "subject", "intent", "behavior", "target", "facing", "scale",
})
_ALLOWED_INTENTS = frozenset({
    "control", "animate", "move", "move-and-animate",
})


class JevController:
    """Finite choice adapter around a Jev decision runtime."""

    def __init__(self, kernel, runtime, selector_id: str = OMEGA_JEV_ID):
        self.kernel = kernel
        self.runtime = runtime
        self.selector_id = selector_id

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

    def _scene(self, actor: str, goal: dict, table: dict) -> dict:
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

        return {
            "revision": self.kernel.revision,
            "turn": self.kernel.turn,
            "principal": actor,
            "goal": dict(goal),
            "subject": describe(subject),
            "target": target_state,
            "available_actions": sorted(table),
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
