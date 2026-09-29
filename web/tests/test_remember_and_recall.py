"""
Tests for "Remember that" / "Do that again".

The architecture under test is the real one, with deterministic doubles
standing in for the two Omega loops while OpenShell is blocked:

    child language
      -> OmegaLLM       (interprets: which sticker, what to call it)
      -> bounded semantic goal
      -> host           (resolves "that" from what actually happened)
      -> OmegaJev       (selects from the CURRENT finite legal table)
      -> kernel         (decides every mutation)

    Omega talks. Jev chooses. The kernel decides.

The doubles implement the same interfaces and the same roles as the live
loops. Neither of them authors a legal key or a PatternStep.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402
from governed_history import (  # noqa: E402
    ORIGIN_GESTURE_JEV, ORIGIN_HUMAN_GESTURE, ORIGIN_PATTERN_PERFORM,
)
from jev_controller import (  # noqa: E402
    JevController, MOVE_STEP, PERFORM_PATTERN, REMEMBER_PATTERN,
)
from pattern_memory import ANIMATE, MOVE, PatternLibrary  # noqa: E402

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "core"))

from stickerbook_core import (  # noqa: E402
    AGENT, ALL_ACTIONS, MUTATING_ACTIONS, Principal, StickerInstance,
)

HUMAN_ID = farm.HUMAN_ID
AGENT_ID = farm.AGENT_ID


# ---------------------------------------------------------------------------
# Deterministic doubles for the two Omega roles
# ---------------------------------------------------------------------------

class FakeOmegaLLM:
    """The linguistic/semantic Omega loop, deterministically.

    It receives bounded child text plus a scene view and returns language and
    at most one bounded semantic goal. It never returns legal keys, movement
    data or PatternSteps: naming what the child meant is its whole job.
    """

    def __init__(self):
        self.scenes = []
        self.goals = []

    def capabilities(self):
        return {"creator_agent": False, "conversational_agent": True}

    def inference_options(self):
        # A configured lane, so the responsible-adult selector is not "off".
        # Conversation is gated on that in the real bridge, and the double
        # has to be faithful about it.
        return [{
            "id": "openrouter",
            "label": "OpenRouter",
            "description": "Configured OpenRouter.",
            "default_model": "z-ai/glm-5.2",
            "model_locked": False,
            "sponsored": False,
            "available": True,
        }]

    def creator_draft(self, **kwargs):
        return {"ok": False, "error": "creator-agent-unavailable"}

    def _subject_from_scene(self, scene, word):
        """Resolve the sticker the child named, from the bounded scene.

        When several match, take the most recently placed one -- the child
        usually means the frog they just put down.
        """
        found = None
        for sticker in scene.get("stickers", []):
            if word in str(sticker.get("definition", "")).casefold():
                found = sticker.get("id")
        return found

    def _recent_subject(self, scene):
        """Resolve "that" to the sticker the recent action history is about.

        Note what this does NOT do: it reads only the declarative projection
        the host offers, and it names a subject. The host decides which
        accepted actions the child actually meant.
        """
        for entry in reversed(scene.get("recent_actions", [])):
            if entry.get("accepted") and entry.get("subject"):
                return entry["subject"]
        return None

    def converse(self, *, text, principal, scene, reference=None,
                 inference=None):
        self.scenes.append(scene)
        lowered = text.casefold()

        if "remember" in lowered:
            subject = self._recent_subject(scene)
            if subject is None:
                return {"ok": True, "reply": "I am not sure what to remember."}
            label = lowered.split(" as ", 1)[-1]
            label = label.replace("your ", "").replace("its ", "").strip(" .!?")
            goal = {
                "subject": subject,
                "intent": REMEMBER_PATTERN,
                "label": label,
            }
            self.goals.append(goal)
            return {"ok": True, "reply": "Okay, I will remember that.",
                    "goal": goal}

        if "do your" in lowered or "do the" in lowered:
            subject = self._subject_from_scene(scene, "frog")
            label = lowered.split("do your", 1)[-1]
            label = label.split("do the", 1)[-1].strip(" .!?")
            goal = {
                "subject": subject,
                "intent": PERFORM_PATTERN,
                "label": label,
            }
            self.goals.append(goal)
            return {"ok": True, "reply": "Here goes!", "goal": goal}

        return {"ok": True, "reply": "Hello!"}


class FakeOmegaJev:
    """The discriminative/control Omega loop, deterministically.

    It receives the validated goal, fresh scene, bounded pattern context and
    the CURRENT finite legal choices, and selects one offered key. It cannot
    manufacture a choice outside that table.
    """

    def __init__(self):
        self.calls = []

    def available(self):
        return True

    def choose(self, *, goal, scene, actions, turn, max_turns):
        self.calls.append({
            "goal": dict(goal), "scene": scene, "actions": dict(actions),
            "turn": turn, "max_turns": max_turns,
        })

        # Performing a remembered behaviour: use the pattern context to see
        # which currently offered choice matches the next remembered form.
        pattern = scene.get("pattern")
        if pattern and pattern.get("nextStep"):
            step = pattern["nextStep"]
            wanted = "%s:%s:%s" % (
                step["verb"], scene["subject"]["id"], step["suffix"])
            if wanted in actions:
                return {"ok": True, "choice": wanted}
            return {"ok": True, "choice": "NOOP"}

        # Ordinary bounded animation intent, e.g. a double-click.
        if goal.get("intent") == "animate":
            for key in sorted(actions):
                if key.startswith("ANIMATE:") \
                        and not key.endswith(":none") \
                        and not key.endswith(":rest"):
                    return {"ok": True, "choice": key}

        return {"ok": True, "choice": "NOOP"}


# ---------------------------------------------------------------------------

class RememberCase(unittest.TestCase):
    """A farm, both Omega doubles, and a frog to teach."""

    def setUp(self):
        self.kernel = farm.build_world()
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge_mod.Bridge(
            self.kernel, agent_runtime=self.llm, jev_runtime=self.jev)
        self.controller = self.bridge.jev_controller
        self.history = self.bridge.history
        self.patterns = self.bridge.patterns
        self.replays = self.bridge.replays
        self.place_frog("frog-1", x=0.50, y=0.50)

    def place_frog(self, sticker_id, *, x, y, owner=HUMAN_ID, asset="frog"):
        self.kernel.place_sticker(StickerInstance(
            sticker_id, owner, owner, asset, 1, x=x, y=y, animation="rest"))
        return self.kernel.sticker(sticker_id)

    def perform(self, keys, *, subject="frog-1", actor=HUMAN_ID,
                prefix="teach", origin=ORIGIN_GESTURE_JEV):
        """Perform real governed actions and record them as the host would."""
        receipts = []
        for index, key in enumerate(keys):
            sticker = self.kernel.sticker(subject)
            moves = self.controller._move_candidates(sticker)
            receipt = self.kernel.propose_key(
                actor, key, "%s-%d" % (prefix, index + 1),
                based_on_revision=self.kernel.revision,
                requested_by=actor, move_candidates=moves)
            self.history.record(
                receipt, origin=origin, key=key, subject_id=subject)
            receipts.append(receipt)
        return receipts

    def say(self, text):
        return self.bridge.converse({"text": text})


# ---------------------------------------------------------------------------
# What OmegaLLM may and may not say
# ---------------------------------------------------------------------------

class OmegaLLMStaysLinguistic(RememberCase):

    def test_remember_goal_carries_subject_and_label_only(self):
        self.perform(["MOVE:frog-1:STEP-E", "ANIMATE:frog-1:hop"])
        self.say("Remember that as your happy dance")

        goal = self.llm.goals[-1]
        self.assertEqual(goal["intent"], REMEMBER_PATTERN)
        self.assertEqual(goal["subject"], "frog-1")
        self.assertEqual(goal["label"], "happy dance")
        self.assertEqual(set(goal), {"subject", "intent", "label"})

        # No steps, no keys, no movement data anywhere in the goal.
        for value in goal.values():
            self.assertNotIn(":", str(value))

    def test_perform_goal_carries_subject_and_label_only(self):
        self.perform(["ANIMATE:frog-1:hop"])
        self.say("Remember that as your happy dance")
        self.say("Froggy, do your happy dance")

        goal = self.llm.goals[-1]
        self.assertEqual(goal["intent"], PERFORM_PATTERN)
        self.assertEqual(set(goal), {"subject", "intent", "label"})
        self.assertEqual(goal["label"], "happy dance")

    def test_omegallm_sees_history_without_complete_keys(self):
        self.perform(["MOVE:frog-1:STEP-E"])
        self.say("hello")
        scene = self.llm.scenes[-1]
        self.assertIn("recent_actions", scene)
        self.assertTrue(scene["recent_actions"])
        verbs = ("MOVE:", "ANIMATE:", "SCALE:", "FACE:")
        for entry in scene["recent_actions"]:
            self.assertNotIn("key", entry)
            for value in entry.values():
                text = str(value) if value is not None else ""
                # Principal ids such as "human:kid" contain a colon; a
                # complete action key is what must never appear.
                for verb in verbs:
                    self.assertFalse(text.startswith(verb), text)

    def test_omegallm_cannot_smuggle_steps_into_a_goal(self):
        """Unknown goal fields are refused by host validation."""
        goal, error = self.controller.normalize_goal({
            "subject": "frog-1", "intent": REMEMBER_PATTERN,
            "label": "sneaky", "steps": [{"verb": "MOVE", "suffix": "STEP-E"}],
        })
        self.assertIsNone(goal)
        self.assertEqual(error, "unknown-jev-goal-field")

    def test_remember_requires_a_label(self):
        goal, error = self.controller.normalize_goal(
            {"subject": "frog-1", "intent": REMEMBER_PATTERN})
        self.assertIsNone(goal)
        self.assertEqual(error, "missing-jev-label")

    def test_perform_requires_a_pattern_reference(self):
        goal, error = self.controller.normalize_goal(
            {"subject": "frog-1", "intent": PERFORM_PATTERN})
        self.assertIsNone(goal)
        self.assertEqual(error, "missing-jev-pattern-reference")


# ---------------------------------------------------------------------------
# The host resolves "that"
# ---------------------------------------------------------------------------

class HostResolvesThat(RememberCase):

    def test_pattern_comes_from_real_history_not_from_omegallm(self):
        self.perform(["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-N",
                      "ANIMATE:frog-1:hop"])
        result = self.say("Remember that as your happy dance")

        stored = result["jev"]["pattern"]
        self.assertEqual(
            stored["steps"],
            [{"verb": MOVE, "suffix": "STEP-E"},
             {"verb": MOVE, "suffix": "STEP-N"},
             {"verb": ANIMATE, "suffix": "hop"}])
        self.assertEqual(stored["asset"], "frog")
        self.assertEqual(stored["learnedFromSubject"], "frog-1")
        # Every step is traceable to a real recorded action.
        self.assertEqual(len(result["jev"]["resolvedFrom"]), 3)

    def test_nothing_to_remember_fails_cleanly(self):
        self.place_frog("frog-quiet", x=0.3, y=0.3)
        result = self.controller.remember_recent(
            subject_id="frog-quiet", label="nothing", learned_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no-accepted-pattern-steps")
        self.assertEqual(len(self.patterns), 0)

    def test_refused_actions_cannot_enter_a_learned_pattern(self):
        # An agent may not act on a human-owned sticker: refused by the kernel.
        self.perform(["ANIMATE:frog-1:hop"], actor=AGENT_ID, prefix="refused")
        entries = self.history.recent_for_subject("frog-1")
        self.assertTrue(entries)
        self.assertFalse(entries[-1].accepted)

        result = self.controller.remember_recent(
            subject_id="frog-1", label="refused dance", learned_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no-accepted-pattern-steps")

    def test_a_refused_action_ends_the_episode(self):
        """A non-learnable action separates one episode from the next.

        The episode is a contiguous run, not a filter, so the earlier hop is
        not silently reached across the refusal.
        """
        self.perform(["ANIMATE:frog-1:hop"])
        self.perform(["MOVE:frog-1:STEP-E"], actor=AGENT_ID, prefix="nope")
        self.perform(["MOVE:frog-1:STEP-N"], prefix="ok2")

        result = self.controller.remember_recent(
            subject_id="frog-1", label="mixed", learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result["pattern"]["steps"],
            [{"verb": MOVE, "suffix": "STEP-N"}])

    def test_switching_subject_ends_the_episode(self):
        """Froggy, Froggy, Bird, Froggy -> "that" is the last Froggy run."""
        self.perform(["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-N"])
        self.perform(["MOVE:butterfly-1:STEP-W"], subject="butterfly-1",
                     prefix="bird")
        self.perform(["ANIMATE:frog-1:hop"], prefix="after")

        result = self.controller.remember_recent(
            subject_id="frog-1", label="happy dance", learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result["pattern"]["steps"],
            [{"verb": ANIMATE, "suffix": "hop"}])
        self.assertEqual(len(result["resolvedFrom"]), 1)

    def test_an_uninterrupted_run_is_learned_whole(self):
        """Without a boundary, the whole contiguous run is the episode."""
        self.perform(["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-N",
                      "ANIMATE:frog-1:hop"])
        result = self.controller.remember_recent(
            subject_id="frog-1", label="happy dance", learned_by=HUMAN_ID)
        self.assertEqual(
            result["pattern"]["steps"],
            [{"verb": MOVE, "suffix": "STEP-E"},
             {"verb": MOVE, "suffix": "STEP-N"},
             {"verb": ANIMATE, "suffix": "hop"}])

    def test_episode_is_bounded_by_pattern_length(self):
        self.perform(["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-N",
                      "ANIMATE:frog-1:hop"])
        result = self.controller.remember_recent(
            subject_id="frog-1", label="short", learned_by=HUMAN_ID,
            max_steps=2)
        # The two most recent, not the first two.
        self.assertEqual(
            result["pattern"]["steps"],
            [{"verb": MOVE, "suffix": "STEP-N"},
             {"verb": ANIMATE, "suffix": "hop"}])

    def test_freehand_drag_is_audited_but_not_learnable(self):
        """A drag is a real mutation with no instance-independent form."""
        self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "drag-1",
            "point": {"x": 0.70, "y": 0.40}})
        entries = self.history.recent_for_subject("frog-1")
        self.assertEqual(entries[-1].origin, ORIGIN_HUMAN_GESTURE)
        self.assertTrue(entries[-1].accepted)
        self.assertIsNone(entries[-1].key)

        result = self.controller.remember_recent(
            subject_id="frog-1", label="dragged", learned_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no-accepted-pattern-steps")

    def test_mixed_move_and_animate_keeps_action_families(self):
        self.perform(["ANIMATE:frog-1:hop", "MOVE:frog-1:STEP-W",
                      "ANIMATE:frog-1:land"])
        result = self.controller.remember_recent(
            subject_id="frog-1", label="typed", learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            [s["verb"] for s in result["pattern"]["steps"]],
            [ANIMATE, MOVE, ANIMATE])

    def test_stored_memory_holds_no_complete_legal_keys(self):
        self.perform(["MOVE:frog-1:STEP-E", "ANIMATE:frog-1:hop"])
        self.controller.remember_recent(
            subject_id="frog-1", label="clean", learned_by=HUMAN_ID)
        pattern = self.patterns.for_asset("frog")[0]
        for step in pattern.steps:
            self.assertNotIn(":", step.verb)
            self.assertNotIn(":", step.suffix)
            self.assertNotIn("frog-1", step.suffix)


# ---------------------------------------------------------------------------
# Recall through OmegaJev
# ---------------------------------------------------------------------------

class RecallThroughJev(RememberCase):

    def teach_happy_dance(self):
        self.perform(["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-N",
                      "ANIMATE:frog-1:hop"])
        result = self.controller.remember_recent(
            subject_id="frog-1", label="happy dance", learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        return result["pattern"]["id"]

    def test_unknown_pattern_fails_cleanly(self):
        result = self.controller.perform_known_pattern(
            {"subject": "frog-1", "intent": PERFORM_PATTERN,
             "label": "no such dance"},
            actor=HUMAN_ID, command_prefix="ghost", requested_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unknown-pattern")

    def test_jev_sees_only_current_finite_legal_choices(self):
        self.teach_happy_dance()
        self.place_frog("frog-2", x=0.30, y=0.30)
        self.controller.perform_known_pattern(
            {"subject": "frog-2", "intent": PERFORM_PATTERN,
             "label": "happy dance"},
            actor=HUMAN_ID, command_prefix="perform", requested_by=HUMAN_ID)

        self.assertTrue(self.jev.calls)
        for call in self.jev.calls:
            offered = set(call["actions"])
            self.assertEqual(offered, set(call["scene"]["available_actions"]))
            for key in offered:
                self.assertTrue(key == "NOOP" or ":frog-2:" in key)

    def test_pattern_context_never_widens_available_actions(self):
        self.teach_happy_dance()
        self.place_frog("frog-2", x=0.30, y=0.30)
        goal = {"subject": "frog-2", "intent": PERFORM_PATTERN,
                "label": "happy dance"}

        bare = JevController(self.kernel, FakeOmegaJev(), patterns=None)
        without, _ = bare._table(HUMAN_ID, goal, animate_only=False)
        with_memory, _ = self.controller._table(
            HUMAN_ID, goal, animate_only=False)
        self.assertEqual(set(without), set(with_memory))
        self.assertTrue(with_memory)

    def test_pattern_context_is_declarative_only(self):
        self.teach_happy_dance()
        self.place_frog("frog-2", x=0.30, y=0.30)
        self.controller.perform_known_pattern(
            {"subject": "frog-2", "intent": PERFORM_PATTERN,
             "label": "happy dance"},
            actor=HUMAN_ID, command_prefix="declarative",
            requested_by=HUMAN_ID)

        context = self.jev.calls[0]["scene"]["pattern"]
        self.assertEqual(context["label"], "happy dance")
        self.assertEqual(context["stepIndex"], 0)
        self.assertEqual(context["nextStep"],
                         {"verb": MOVE, "suffix": "STEP-E"})
        for step in context["steps"]:
            self.assertNotIn(":", step["verb"])
            self.assertNotIn(":", step["suffix"])

    def test_successful_recall_creates_an_inspectable_record(self):
        self.teach_happy_dance()
        frog2 = self.place_frog("frog-2", x=0.30, y=0.60)

        result = self.controller.perform_known_pattern(
            {"subject": "frog-2", "intent": PERFORM_PATTERN,
             "label": "happy dance"},
            actor=HUMAN_ID, command_prefix="recall", requested_by=HUMAN_ID)

        self.assertTrue(result["ok"], result)
        record = result["replay"]
        self.assertEqual(record["result"], "completed")
        self.assertEqual(record["mode"], "agent")
        self.assertEqual(record["acceptedSteps"], 3)
        self.assertEqual(record["subject"], "frog-2")
        self.assertEqual(record["requestedBy"], HUMAN_ID)
        self.assertEqual(
            [(s["verb"], s["suffix"]) for s in record["steps"]],
            [(MOVE, "STEP-E"), (MOVE, "STEP-N"), (ANIMATE, "hop")])
        self.assertTrue(
            all(s["receipt"]["accepted"] for s in record["steps"]))

        after = self.kernel.sticker("frog-2")
        self.assertGreater(after.x, frog2.x)
        self.assertLess(after.y, frog2.y)
        self.assertEqual(after.animation, "hop")

        # Filed in the host-side log, and every step is in host history.
        self.assertEqual(len(self.replays), 1)
        self.assertIsNotNone(self.replays.get(record["replayId"]))
        performed = [
            e for e in self.history.recent_for_subject("frog-2")
            if e.origin == ORIGIN_PATTERN_PERFORM]
        self.assertEqual(len(performed), 3)

    def test_partial_recall_under_changed_world_state(self):
        """Two steps east near the edge: one runs, then it stops."""
        self.perform(["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-E"])
        self.controller.remember_recent(
            subject_id="frog-1", label="two steps east", learned_by=HUMAN_ID)

        self.place_frog("frog-edge", x=0.97, y=0.50)
        result = self.controller.perform_known_pattern(
            {"subject": "frog-edge", "intent": PERFORM_PATTERN,
             "label": "two steps east"},
            actor=HUMAN_ID, command_prefix="edge", requested_by=HUMAN_ID)

        self.assertFalse(result["ok"])
        record = result["replay"]
        # Three unambiguous counts: the pattern had two steps, one was
        # submitted to the kernel, one was accepted.
        self.assertEqual(record["plannedSteps"], 2)
        self.assertEqual(record["submittedSteps"], 1)
        self.assertEqual(record["acceptedSteps"], 1)
        self.assertEqual(record["result"], "partial")
        self.assertEqual(record["stoppedAt"], 2)
        # The world changed, so this reads the same as mechanical replay
        # rather than blaming the chooser for declining.
        self.assertEqual(record["stoppedReason"], "pattern-step-unavailable")
        self.assertTrue(record["steps"][0]["receipt"]["accepted"])
        self.assertFalse(record["steps"][1]["submitted"])
        self.assertEqual(record["steps"][1]["unavailableReason"],
                         "pattern-step-unavailable")
        # The first movement stays applied. No rollback.
        self.assertEqual(self.kernel.sticker("frog-edge").x, 1.0)

    def test_declining_an_available_step_is_recorded_as_jev_noop(self):
        """Available but declined is different evidence from never offered."""
        class DecliningJev(FakeOmegaJev):
            def choose(self, **kwargs):
                super().choose(**kwargs)
                return {"ok": True, "choice": "NOOP"}

        self.teach_happy_dance()
        self.place_frog("frog-2", x=0.30, y=0.30)
        controller = JevController(
            self.kernel, DecliningJev(), patterns=self.patterns,
            history=self.history, replays=self.replays)

        result = controller.perform_known_pattern(
            {"subject": "frog-2", "intent": PERFORM_PATTERN,
             "label": "happy dance"},
            actor=HUMAN_ID, command_prefix="declined", requested_by=HUMAN_ID)

        record = result["replay"]
        self.assertEqual(record["stoppedReason"], "jev-noop")
        self.assertEqual(record["stoppedAt"], 1)
        self.assertEqual(record["plannedSteps"], 3)
        self.assertEqual(record["submittedSteps"], 0)
        self.assertEqual(record["acceptedSteps"], 0)
        self.assertEqual(record["result"], "stopped")
        # Nothing happened to the world.
        self.assertEqual(self.kernel.sticker("frog-2").animation, "rest")

    def test_action_budget_still_applies_across_a_recall(self):
        self.kernel.register_principal(Principal(
            "agent:tiny", AGENT, tools=farm.AGENT_TOOLS,
            delegable=frozenset(), max_actions=1))
        self.place_frog("frog-agent", x=0.40, y=0.40, owner="agent:tiny")
        self.perform(["MOVE:frog-agent:STEP-E", "MOVE:frog-agent:STEP-N"],
                     subject="frog-agent", actor=HUMAN_ID, prefix="teach-a")
        self.controller.remember_recent(
            subject_id="frog-agent", label="budget dance",
            learned_by=HUMAN_ID)

        self.place_frog("frog-agent2", x=0.40, y=0.40, owner="agent:tiny")
        result = self.controller.perform_known_pattern(
            {"subject": "frog-agent2", "intent": PERFORM_PATTERN,
             "label": "budget dance"},
            actor="agent:tiny", command_prefix="budget",
            requested_by="agent:tiny")

        self.assertFalse(result["ok"])
        self.assertEqual(result["acceptedSteps"], 1)
        self.assertEqual(result["replay"]["steps"][1]["receipt"]["reason"],
                         "action-budget-exhausted")

    def test_incompatible_definition_is_refused(self):
        self.teach_happy_dance()
        result = self.controller.perform_known_pattern(
            {"subject": "cow-1", "intent": PERFORM_PATTERN,
             "label": "happy dance"},
            actor=HUMAN_ID, command_prefix="wrong", requested_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unknown-pattern")
        self.assertEqual(self.kernel.sticker("cow-1").animation, "rest")

    def test_unauthorized_actor_still_loses_to_kernel_authority(self):
        self.teach_happy_dance()
        before = self.kernel.sticker("frog-1")
        result = self.controller.perform_known_pattern(
            {"subject": "frog-1", "intent": PERFORM_PATTERN,
             "label": "happy dance"},
            actor=AGENT_ID, command_prefix="agent", requested_by=AGENT_ID)
        self.assertFalse(result["ok"])
        after = self.kernel.sticker("frog-1")
        self.assertEqual((after.x, after.y, after.animation),
                         (before.x, before.y, before.animation))
        self.assertEqual(after.revision, before.revision)


# ---------------------------------------------------------------------------
# The direct, non-linguistic path
# ---------------------------------------------------------------------------

class DirectGesturePathIntact(RememberCase):

    def test_double_click_reaches_jev_without_omegallm(self):
        result = self.bridge.animate(
            {"sticker": "frog-1", "command_id": "dbl-1"})
        self.assertTrue(result["ok"], result)
        # OmegaLLM was never consulted.
        self.assertEqual(self.llm.goals, [])
        self.assertEqual(self.llm.scenes, [])
        # Jev was, with an animation-only surface.
        self.assertTrue(self.jev.calls)
        offered = set(self.jev.calls[-1]["actions"])
        self.assertTrue(offered)
        for key in offered:
            self.assertTrue(key == "NOOP" or key.startswith("ANIMATE:"))
        self.assertNotEqual(self.kernel.sticker("frog-1").animation, "rest")

    def test_double_click_is_recorded_as_a_gesture_path(self):
        self.bridge.animate({"sticker": "frog-1", "command_id": "dbl-2"})
        entries = self.history.recent_for_subject("frog-1")
        self.assertTrue(entries)
        self.assertEqual(entries[-1].origin, ORIGIN_GESTURE_JEV)
        self.assertTrue(entries[-1].accepted)
        self.assertTrue(entries[-1].key.startswith("ANIMATE:"))


# ---------------------------------------------------------------------------
# Authority did not move
# ---------------------------------------------------------------------------

class AuthorityUnchanged(RememberCase):

    def test_no_new_kernel_mutation_verb_has_appeared(self):
        self.assertEqual(ALL_ACTIONS, frozenset({
            "noop", "observe", "add-own-sticker", "move-sticker",
            "animate-own-sticker", "resize-own-sticker",
            "set-sticker-facing", "remove-own-sticker",
            "remove-agent-sticker", "create-agent",
        }))
        self.assertEqual(MUTATING_ACTIONS, frozenset({
            "add-own-sticker", "move-sticker", "animate-own-sticker",
            "resize-own-sticker", "set-sticker-facing",
            "remove-own-sticker", "remove-agent-sticker", "create-agent",
        }))

    def test_kernel_receipts_know_nothing_about_patterns(self):
        self.perform(["MOVE:frog-1:STEP-E"])
        self.controller.remember_recent(
            subject_id="frog-1", label="happy dance", learned_by=HUMAN_ID)
        self.place_frog("frog-2", x=0.4, y=0.4)
        result = self.controller.perform_known_pattern(
            {"subject": "frog-2", "intent": PERFORM_PATTERN,
             "label": "happy dance"},
            actor=HUMAN_ID, command_prefix="plain", requested_by=HUMAN_ID)

        for step in result["replay"]["steps"]:
            receipt = step["receipt"]
            self.assertNotIn("pattern", receipt)
            self.assertNotIn("label", receipt)
            for value in receipt.values():
                self.assertNotEqual(value, "happy dance")

    def test_patterns_transfer_across_instances_but_authority_does_not(self):
        """Taught on an agent-owned frog, performed on a human-owned one."""
        self.place_frog("frog-agent", x=0.40, y=0.40, owner=AGENT_ID)
        self.perform(["ANIMATE:frog-agent:hop"], subject="frog-agent",
                     actor=AGENT_ID, prefix="agent-teach")
        remembered = self.controller.remember_recent(
            subject_id="frog-agent", label="shared hop", learned_by=AGENT_ID)
        self.assertTrue(remembered["ok"], remembered)
        self.assertEqual(remembered["pattern"]["learnedBy"], AGENT_ID)

        # The human may perform it on their own frog.
        result = self.controller.perform_known_pattern(
            {"subject": "frog-1", "intent": PERFORM_PATTERN,
             "label": "shared hop"},
            actor=HUMAN_ID, command_prefix="shared", requested_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.kernel.sticker("frog-1").animation, "hop")


# ---------------------------------------------------------------------------
# The whole conversation, end to end
# ---------------------------------------------------------------------------

class FroggyRemembersAndPerforms(RememberCase):

    def test_remember_that_then_do_that_again(self):
        # 1. The child moves Froggy and makes it hop. Ordinary governed
        #    actions, each with an accepted kernel receipt.
        receipts = self.perform([
            "MOVE:frog-1:STEP-E",
            "MOVE:frog-1:STEP-N",
            "ANIMATE:frog-1:hop",
        ])
        self.assertTrue(all(r.accepted for r in receipts))

        # 2. "Remember that as your happy dance."
        said = self.say("Remember that as your happy dance")
        self.assertTrue(said["ok"], said)
        stored = said["jev"]["pattern"]
        self.assertEqual(stored["label"], "happy dance")
        self.assertEqual(
            stored["steps"],
            [{"verb": MOVE, "suffix": "STEP-E"},
             {"verb": MOVE, "suffix": "STEP-N"},
             {"verb": ANIMATE, "suffix": "hop"}])

        # 3. A second frog, elsewhere, at rest.
        self.place_frog("frog-2", x=0.35, y=0.65)

        # 4. "Froggy, do your happy dance."
        done = self.say("Froggy, do your happy dance")
        self.assertTrue(done["ok"], done)
        performed = done["jev"]
        self.assertTrue(performed["ok"], performed)
        self.assertEqual(performed["result"], "completed")

        # 5. Jev chose each step from the table offered at that moment.
        perform_calls = [c for c in self.jev.calls
                         if c["goal"].get("intent") == PERFORM_PATTERN]
        self.assertEqual(len(perform_calls), 3)
        for call in perform_calls:
            self.assertIn(call["scene"]["pattern"]["nextStep"]["verb"],
                          (MOVE, ANIMATE))
            self.assertEqual(set(call["actions"]),
                             set(call["scene"]["available_actions"]))

        # 6. Ordinary kernel receipts, in order.
        record = performed["replay"]
        self.assertEqual(
            [s["receipt"]["action"] for s in record["steps"]],
            ["move-sticker", "move-sticker", "animate-own-sticker"])
        self.assertTrue(all(s["receipt"]["accepted"] for s in record["steps"]))

        # 7. And the frog that was taught is not the frog that danced.
        self.assertEqual(record["subject"], "frog-2")
        self.assertEqual(self.kernel.sticker("frog-2").animation, "hop")


# ---------------------------------------------------------------------------
# A finite move table belongs to the revision it was built from
# ---------------------------------------------------------------------------

class MoveTableRevisionIsAuthoritative(RememberCase):
    """Absolute move destinations bind to one world revision.

    `_move_candidates` bakes the subject's position at table-build time into
    each MOVE key's destination coordinates, so a choice made against that
    table is a claim about THAT world. Powered replay releases the world lock
    for Jev think-time, during which a child may move the same sticker. The
    proposal must therefore name the revision its own table came from: if it
    re-read the revision instead, the kernel would accept an old coordinate
    as current and silently drag the child's sticker back.
    """

    def teach_step_east(self):
        self.perform(["MOVE:frog-1:STEP-E"])
        result = self.controller.remember_recent(
            subject_id="frog-1", label="hop east", learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        return result["pattern"]["id"]

    def child_moves_frog(self, x, y):
        """A real child gesture, on its own thread, through the bridge."""
        landed = []
        thread = threading.Thread(target=lambda: landed.append(
            self.bridge.propose_move({
                "sticker": "frog-1", "command_id": "child-drag",
                "point": {"x": x, "y": y}})))
        thread.start()
        thread.join(5)
        # Not merely "eventually": it must finish while Jev is still thinking.
        self.assertFalse(thread.is_alive(), "the child's gesture blocked")
        self.assertEqual(len(landed), 1)
        return landed[0]

    def test_child_move_during_jev_think_time_refuses_stale_coordinate(self):
        self.teach_step_east()
        before = self.kernel.sticker("frog-1")
        stale_revision = self.kernel.revision
        # Where the pre-move table's STEP-E key points. Nothing may send the
        # frog here once the child has moved it somewhere else.
        stale_destination = (round(min(1.0, before.x + MOVE_STEP), 6),
                             round(before.y, 6))
        observed = {}
        jev_choose = self.jev.choose
        taught = len(self.kernel.receipts)

        def choose(**request):
            observed["table_revision"] = request["scene"]["revision"]
            # The thread running powered replay holds no world lock here.
            observed["own_lock"] = self.bridge._world_lock._is_owned()
            # And no other holder is blocking the world either.
            observed["child"] = self.child_moves_frog(0.20, 0.80)
            return jev_choose(**request)

        with patch.object(self.jev, "choose", side_effect=choose):
            result = self.controller.perform_known_pattern(
                {"subject": "frog-1", "intent": PERFORM_PATTERN,
                 "label": "hop east"},
                actor=HUMAN_ID, command_prefix="stale",
                requested_by=HUMAN_ID)

        # 1. Jev genuinely ran, against the pre-move table.
        self.assertTrue(self.jev.calls)
        self.assertEqual(observed["table_revision"], stale_revision)

        # 2. It ran with no world lock held, on this thread or any other.
        self.assertFalse(observed["own_lock"])
        self.assertTrue(observed["child"]["ok"], observed["child"])

        # 3. The child's move is the one that happened.
        after = self.kernel.sticker("frog-1")
        self.assertEqual((after.x, after.y), (0.20, 0.80))
        self.assertNotEqual((after.x, after.y), stale_destination)
        self.assertGreater(after.revision, stale_revision)

        # 4. The stale Jev proposal was submitted and refused AS stale.
        self.assertFalse(result["ok"], result)
        record = result["replay"]
        self.assertEqual(len(record["steps"]), 1)
        step = record["steps"][0]
        self.assertTrue(step["submitted"])
        self.assertIsNone(step["unavailableReason"])
        self.assertFalse(step["receipt"]["accepted"])
        self.assertEqual(step["receipt"]["reason"], "stale-revision")
        self.assertEqual(step["receipt"]["basedOnRevision"], stale_revision)

        # 5. The audit says so truthfully, and nothing retried over the child.
        self.assertEqual(record["result"], "stopped")
        self.assertEqual(record["stoppedReason"], "pattern-step-refused")
        self.assertEqual(record["stoppedAt"], 1)
        self.assertEqual(record["acceptedSteps"], 0)
        self.assertEqual(record["submittedSteps"], 1)
        self.assertEqual(len(self.jev.calls), 1)

        # 6. Of everything proposed after the teaching setup, exactly one
        # was accepted on this sticker: the child's own gesture.
        attempt = self.kernel.receipts[taught:]
        accepted = [r for r in attempt
                    if r.accepted and r.object_id == "frog-1"]
        self.assertEqual([r.command_id for r in accepted], ["child-drag"])
        self.assertEqual(
            sorted((r.command_id, r.accepted) for r in attempt),
            [("child-drag", True), ("stale-1", False)])

    def test_undisturbed_powered_replay_still_completes(self):
        # The fix must not make an ordinary attempt look stale to itself:
        # each step proposes against the table it just built.
        self.teach_step_east()
        result = self.controller.perform_known_pattern(
            {"subject": "frog-1", "intent": PERFORM_PATTERN,
             "label": "hop east"},
            actor=HUMAN_ID, command_prefix="clean", requested_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["replay"]["result"], "completed")
        self.assertEqual(result["replay"]["acceptedSteps"], 1)

    def test_multi_step_replay_advances_its_own_revision(self):
        # Consecutive accepted steps each bump the revision; a later step must
        # not be refused as stale because an earlier step of the same attempt
        # moved the subject.
        self.perform(["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-N",
                      "MOVE:frog-1:STEP-E"])
        remembered = self.controller.remember_recent(
            subject_id="frog-1", label="zigzag", learned_by=HUMAN_ID)
        self.assertTrue(remembered["ok"], remembered)
        result = self.controller.perform_known_pattern(
            {"subject": "frog-1", "intent": PERFORM_PATTERN,
             "label": "zigzag"},
            actor=HUMAN_ID, command_prefix="multi", requested_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        record = result["replay"]
        self.assertEqual(record["result"], "completed")
        self.assertEqual(record["acceptedSteps"], 3)
        revisions = [s["receipt"]["basedOnRevision"] for s in record["steps"]]
        self.assertEqual(revisions, sorted(revisions))
        self.assertEqual(len(set(revisions)), 3)


class MoveOnlyChoiceSurface(RememberCase):
    """The narrow surface a continuous movement objective needs."""

    def surface(self, **mode):
        goal = {"subject": "frog-1", "intent": PERFORM_PATTERN}
        table, moves = self.controller._table(HUMAN_ID, goal, **mode)
        return table, moves

    def test_move_only_offers_exactly_current_subject_moves_and_noop(self):
        self.place_frog("frog-2", x=0.30, y=0.30)
        table, moves = self.surface(move_only=True)
        expected = {"MOVE:frog-1:%s" % name for name in moves} | {"NOOP"}
        self.assertEqual(set(table), expected)
        # Eight local steps are all available from mid-page.
        self.assertEqual(len(moves), 8)
        for key, command in table.items():
            if key == "NOOP":
                continue
            self.assertEqual(command.object_id, "frog-1")
            self.assertEqual((command.param("x"), command.param("y")),
                             moves[key.rsplit(":", 1)[1]])

    def test_move_only_excludes_appearance_and_other_stickers(self):
        self.place_frog("frog-2", x=0.30, y=0.30)
        table, _ = self.surface(move_only=True)
        for key in table:
            self.assertFalse(key.startswith("ANIMATE:"), key)
            self.assertFalse(key.startswith("SCALE:"), key)
            self.assertFalse(key.startswith("FACE:"), key)
            self.assertFalse(key.startswith("REMOVE:"), key)
            self.assertTrue(key == "NOOP" or ":frog-1:" in key, key)
        # Those choices genuinely exist on the ordinary surface.
        ordinary, _ = self.surface()
        self.assertTrue(any(k.startswith("ANIMATE:") for k in ordinary))
        self.assertTrue(any(k.startswith("SCALE:") for k in ordinary))
        self.assertTrue(any(k.startswith("FACE:") for k in ordinary))

    def test_move_only_narrows_rather_than_widens_ordinary_surface(self):
        ordinary, _ = self.surface()
        narrow, _ = self.surface(move_only=True)
        self.assertTrue(set(narrow) < set(ordinary))

    def test_move_only_shrinks_at_a_page_edge_without_clamping(self):
        # A corner offers fewer legal steps. The surface reports that by
        # omission; no candidate is clamped into a no-op.
        self.place_frog("corner-1", x=0.0, y=0.0)
        goal = {"subject": "corner-1", "intent": PERFORM_PATTERN}
        table, moves = self.controller._table(HUMAN_ID, goal, move_only=True)
        # The three directions that cannot move at all are absent. The two
        # diagonals that can still move in one axis are clamped to their
        # usable component rather than dropped, so they survive as keys that
        # happen to share a destination with an axis step.
        self.assertEqual(set(moves),
                         {"STEP-E", "STEP-NE", "STEP-SE", "STEP-S", "STEP-SW"})
        self.assertEqual(len(set(moves.values())), 3)
        self.assertEqual(moves["STEP-NE"], moves["STEP-E"])
        self.assertEqual(moves["STEP-SW"], moves["STEP-S"])
        self.assertEqual(set(table),
                         {"MOVE:corner-1:%s" % n for n in moves} | {"NOOP"})
        # Nothing was clamped into a no-op: every offered step really moves.
        for destination in moves.values():
            self.assertNotEqual(destination, (0.0, 0.0))

    def test_existing_modes_are_unchanged(self):
        goal = {"subject": "frog-1", "intent": PERFORM_PATTERN}
        animate, _ = self.controller._table(
            HUMAN_ID, goal, animate_only=True)
        self.assertTrue(animate)
        for key in animate:
            self.assertTrue(key == "NOOP" or key.startswith("ANIMATE:"), key)
        ordinary, _ = self.controller._table(
            HUMAN_ID, goal, animate_only=False)
        kinds = {k.split(":", 1)[0] for k in ordinary if k != "NOOP"}
        self.assertEqual(kinds, {"MOVE", "ANIMATE", "SCALE", "FACE"})


if __name__ == "__main__":
    unittest.main()
