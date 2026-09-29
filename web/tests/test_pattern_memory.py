"""
Tests for child-directed movement-pattern memory.

The product idea: a child is not programming an agent, the child is teaching
a sticker a way it likes to move. The safety idea: **learning changes memory,
not authority**.

These run headless against a real Kernel and a real JevController. No
OpenShell, no model, no HTTP: the seam under test is capture and replay, and
a deterministic Jev double stands in for the live chooser.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import farm  # noqa: E402
from jev_controller import JevController  # noqa: E402
from pattern_memory import (  # noqa: E402
    ANIMATE, MOVE, MovementPattern, PatternLibrary, PatternStep,
    bind_key, split_key, steps_from_trace,
)

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "core"))

from stickerbook_core import (  # noqa: E402
    AGENT, Principal, StickerInstance,
)

HUMAN_ID = farm.HUMAN_ID
AGENT_ID = farm.AGENT_ID


class StubJev:
    """Deterministic chooser. Plays a fixed script of keys, in order.

    It still sees only the bounded scene and the finite host-owned table, and
    it still returns only a key. It exists so the pattern seam can be proven
    without a live OmegaJev.
    """

    def __init__(self, script):
        self.script = list(script)
        self.scenes = []

    def available(self):
        return True

    def choose(self, *, goal, scene, actions, turn, max_turns):
        self.scenes.append(scene)
        if not self.script:
            return {"ok": True, "choice": "NOOP"}
        return {"ok": True, "choice": self.script.pop(0)}


class PatternCase(unittest.TestCase):
    """A fresh farm, a fresh library and a frog to teach."""

    def setUp(self):
        self.kernel = farm.build_world()
        self.library = PatternLibrary()
        self.jev = StubJev([])
        self.controller = JevController(
            self.kernel, self.jev, patterns=self.library)
        self.place_frog("frog-1", x=0.50, y=0.50)

    def place_frog(self, sticker_id, *, x, y, owner=HUMAN_ID, asset="frog"):
        self.kernel.place_sticker(StickerInstance(
            sticker_id, owner, owner, asset, 1, x=x, y=y, animation="rest"))
        return self.kernel.sticker(sticker_id)

    # -- helpers ------------------------------------------------------------

    def perform(self, keys, *, subject="frog-1", actor=HUMAN_ID,
                prefix="teach"):
        """Actually perform keys through the kernel, returning a run trace.

        Shaped exactly like JevController.run_goal's trace, because that is
        what capture consumes.
        """
        trace = []
        for index, key in enumerate(keys):
            sticker = self.kernel.sticker(subject)
            moves = self.controller._move_candidates(sticker)
            receipt = self.kernel.propose_key(
                actor, key, "%s-%d" % (prefix, index + 1),
                based_on_revision=self.kernel.revision,
                move_candidates=moves)
            trace.append({
                "turn": index + 1,
                "choice": key,
                "receipt": receipt.to_dict(),
            })
        return trace

    def teach(self, keys, label="happy dance", subject="frog-1"):
        trace = self.perform(keys, subject=subject)
        return self.controller.remember_trace(
            label=label, subject_id=subject, trace=trace,
            learned_by=HUMAN_ID)


# ---------------------------------------------------------------------------
# Representation
# ---------------------------------------------------------------------------

class Representation(PatternCase):

    def test_step_keeps_the_action_family_a_suffix_would_lose(self):
        """STEP-E belongs to MOVE; spin belongs to ANIMATE."""
        move = PatternStep(verb=MOVE, suffix="STEP-E")
        animate = PatternStep(verb=ANIMATE, suffix="hop")
        self.assertNotEqual(move.verb, animate.verb)
        self.assertEqual(bind_key(move, "frog-1"), "MOVE:frog-1:STEP-E")
        self.assertEqual(bind_key(animate, "frog-1"), "ANIMATE:frog-1:hop")

    def test_stored_steps_contain_no_sticker_instance_id(self):
        result = self.teach(["MOVE:frog-1:STEP-E", "ANIMATE:frog-1:hop"])
        self.assertTrue(result["ok"], result)
        pattern = self.library.get(result["pattern"]["id"])
        for step in pattern.steps:
            self.assertNotIn("frog-1", step.suffix)
            self.assertNotIn(":", step.suffix)
            self.assertNotIn(":", step.verb)

    def test_no_executable_content_enters_the_representation(self):
        result = self.teach(["MOVE:frog-1:STEP-E"])
        pattern = self.library.get(result["pattern"]["id"])
        for value in vars(pattern).values():
            self.assertFalse(callable(value))
        for step in pattern.steps:
            self.assertIsInstance(step, PatternStep)
            for field in vars(step).values():
                self.assertIsInstance(field, str)
                self.assertFalse(callable(field))

    def test_pattern_and_step_are_immutable(self):
        result = self.teach(["MOVE:frog-1:STEP-E"])
        pattern = self.library.get(result["pattern"]["id"])
        with self.assertRaises(Exception):
            pattern.label = "something else"
        with self.assertRaises(Exception):
            pattern.steps[0].suffix = "STEP-W"

    def test_bogus_verb_cannot_be_represented(self):
        with self.assertRaises(ValueError):
            PatternStep(verb="SHELL", suffix="rm")
        with self.assertRaises(ValueError):
            PatternStep(verb=MOVE, suffix="STEP-E; rm -rf /")

    def test_split_key_rejects_another_subject(self):
        self.assertIsNone(split_key("MOVE:frog-2:STEP-E", "frog-1"))
        self.assertIsNone(split_key("NOOP", "frog-1"))
        self.assertIsNone(split_key("REMOVE:frog-1", "frog-1"))


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

class Capture(PatternCase):

    def test_accepted_trace_becomes_a_pattern(self):
        result = self.teach(["MOVE:frog-1:STEP-E", "ANIMATE:frog-1:hop"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["pattern"]["label"], "happy dance")
        self.assertEqual(result["pattern"]["asset"], "frog")
        self.assertEqual(
            [s["verb"] for s in result["pattern"]["steps"]],
            [MOVE, ANIMATE])
        self.assertEqual(len(self.library), 1)

    def test_rejected_trace_cannot_become_learned_behavior(self):
        # An agent may not act on a human-owned sticker, so this key is not
        # in its table and the kernel refuses it.
        trace = self.perform(
            ["MOVE:frog-1:STEP-E"], actor=AGENT_ID, prefix="nope")
        self.assertFalse(trace[0]["receipt"]["accepted"])
        result = self.controller.remember_trace(
            label="bad dance", subject_id="frog-1", trace=trace,
            learned_by=AGENT_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no-accepted-pattern-steps")
        self.assertEqual(len(self.library), 0)

    def test_noop_is_not_remembered_as_movement(self):
        trace = self.perform(["ANIMATE:frog-1:hop", "NOOP"])
        self.assertTrue(all(e["receipt"]["accepted"] for e in trace))
        result = self.controller.remember_trace(
            label="just a hop", subject_id="frog-1", trace=trace,
            learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["pattern"]["steps"]), 1)
        self.assertEqual(result["pattern"]["steps"][0]["verb"], ANIMATE)

    def test_only_accepted_steps_survive_a_mixed_trace(self):
        good = self.perform(["ANIMATE:frog-1:hop"])
        bad = self.perform(["ANIMATE:frog-1:nonexistent-clip"], prefix="bad")
        self.assertTrue(good[0]["receipt"]["accepted"])
        self.assertFalse(bad[0]["receipt"]["accepted"])
        result = self.controller.remember_trace(
            label="mixed", subject_id="frog-1", trace=good + bad,
            learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["pattern"]["steps"]), 1)

    def test_forged_receipt_action_is_refused(self):
        """A MOVE key claiming an ANIMATE receipt cannot be learned."""
        trace = [{
            "turn": 1,
            "choice": "MOVE:frog-1:STEP-E",
            "receipt": {"accepted": True, "action": "animate-own-sticker",
                        "object": "frog-1"},
        }]
        steps, error = steps_from_trace(trace, "frog-1")
        self.assertIsNone(steps)
        self.assertEqual(error, "pattern-step-action-mismatch")

    def test_capture_from_a_deterministic_jev_run(self):
        """The seam a live OmegaJev will use, proven with a test double."""
        self.jev.script = ["ANIMATE:frog-1:hop"]
        run = self.controller.run_goal(
            {"subject": "frog-1", "intent": "animate"},
            actor=HUMAN_ID, command_prefix="jev-run",
            requested_by=HUMAN_ID, max_turns=1)
        self.assertTrue(run["ok"], run)
        result = self.controller.remember_trace(
            label="jev taught dance", subject_id="frog-1",
            trace=run["trace"], learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["pattern"]["steps"],
                         [{"verb": ANIMATE, "suffix": "hop"}])


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

class Bounds(PatternCase):

    def test_maximum_pattern_count_is_enforced(self):
        library = PatternLibrary(max_patterns=2)
        steps = (PatternStep(verb=ANIMATE, suffix="hop"),)
        for index in range(2):
            pattern, error = library.remember(
                label="dance %d" % index, asset="frog", steps=steps,
                subject_id="frog-1", learned_by=HUMAN_ID, revision=1)
            self.assertIsNone(error)
        pattern, error = library.remember(
            label="one too many", asset="frog", steps=steps,
            subject_id="frog-1", learned_by=HUMAN_ID, revision=1)
        self.assertIsNone(pattern)
        self.assertEqual(error, "pattern-memory-full")
        self.assertEqual(len(library), 2)

    def test_maximum_pattern_length_is_enforced(self):
        library = PatternLibrary(max_steps=3)
        steps = tuple(
            PatternStep(verb=MOVE, suffix="STEP-E") for _ in range(4))
        pattern, error = library.remember(
            label="too long", asset="frog", steps=steps,
            subject_id="frog-1", learned_by=HUMAN_ID, revision=1)
        self.assertIsNone(pattern)
        self.assertEqual(error, "pattern-too-long")

    def test_label_must_be_bounded_and_key_safe(self):
        library = PatternLibrary()
        steps = (PatternStep(verb=ANIMATE, suffix="hop"),)
        for bad in ("", "   ", "x" * 200, "MOVE:frog-1:STEP-E"):
            pattern, error = library.remember(
                label=bad, asset="frog", steps=steps, subject_id="frog-1",
                learned_by=HUMAN_ID, revision=1)
            self.assertIsNone(pattern, bad)
            self.assertEqual(error, "invalid-pattern-label")


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

class Replay(PatternCase):

    def remember(self, keys, label="happy dance"):
        result = self.teach(keys, label=label)
        self.assertTrue(result["ok"], result)
        return result["pattern"]["id"]

    def test_replay_on_a_fresh_compatible_instance(self):
        pattern_id = self.remember(
            ["MOVE:frog-1:STEP-E", "ANIMATE:frog-1:hop"])
        self.place_frog("frog-2", x=0.20, y=0.20)
        before = self.kernel.sticker("frog-2")

        result = self.controller.replay_pattern(
            pattern_id, subject_id="frog-2", actor=HUMAN_ID,
            command_prefix="replay", requested_by=HUMAN_ID)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["completed"], 2)
        self.assertTrue(
            all(e["receipt"]["accepted"] for e in result["replay"]["steps"]))
        after = self.kernel.sticker("frog-2")
        self.assertGreater(after.x, before.x)
        self.assertEqual(after.animation, "hop")

    def test_edge_clamped_movement_stops_closed(self):
        """Two steps east near the eastern edge: one runs, then it stops."""
        pattern_id = self.remember(
            ["MOVE:frog-1:STEP-E", "MOVE:frog-1:STEP-E"])
        self.place_frog("frog-edge", x=0.97, y=0.50)

        result = self.controller.replay_pattern(
            pattern_id, subject_id="frog-edge", actor=HUMAN_ID,
            command_prefix="edge", requested_by=HUMAN_ID)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "pattern-step-unavailable")
        self.assertEqual(result["completed"], 1)
        self.assertTrue(result["replay"]["steps"][0]["receipt"]["accepted"])
        self.assertEqual(self.kernel.sticker("frog-edge").x, 1.0)

    def test_world_state_change_between_steps_affects_legality(self):
        """A clip already playing is not offered again."""
        library = PatternLibrary()
        controller = JevController(self.kernel, self.jev, patterns=library)
        pattern, error = library.remember(
            label="double hop", asset="frog",
            steps=(PatternStep(verb=ANIMATE, suffix="hop"),
                   PatternStep(verb=ANIMATE, suffix="hop")),
            subject_id="frog-1", learned_by=HUMAN_ID, revision=1)
        self.assertIsNone(error)

        result = controller.replay_pattern(
            pattern.pattern_id, subject_id="frog-1", actor=HUMAN_ID,
            command_prefix="twice", requested_by=HUMAN_ID)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "pattern-step-unavailable")
        self.assertEqual(result["completed"], 1)

    def test_incompatible_definition_cannot_inherit_a_pattern(self):
        pattern_id = self.remember(["ANIMATE:frog-1:hop"])
        # cow-1 exists on the farm and is a different StickerDefinition.
        result = self.controller.replay_pattern(
            pattern_id, subject_id="cow-1", actor=HUMAN_ID,
            command_prefix="wrong", requested_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "pattern-definition-mismatch")
        self.assertEqual(result["completed"], 0)
        self.assertEqual(self.kernel.sticker("cow-1").animation, "rest")

    def test_clip_absent_from_this_definition_never_executes(self):
        """Even a same-asset instance refuses a clip the definition lacks."""
        library = PatternLibrary()
        controller = JevController(self.kernel, self.jev, patterns=library)
        pattern, error = library.remember(
            label="impossible", asset="frog",
            steps=(PatternStep(verb=ANIMATE, suffix="spin"),),
            subject_id="frog-1", learned_by=HUMAN_ID, revision=1)
        self.assertIsNone(error)
        result = controller.replay_pattern(
            pattern.pattern_id, subject_id="frog-1", actor=HUMAN_ID,
            command_prefix="spin", requested_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "pattern-step-unavailable")
        self.assertEqual(self.kernel.sticker("frog-1").animation, "rest")

    def test_unauthorized_actor_still_loses_to_kernel_authority(self):
        pattern_id = self.remember(["ANIMATE:frog-1:hop"])
        # frog-1 is human-owned; the agent may not act on it at all.
        before = self.kernel.sticker("frog-1")
        result = self.controller.replay_pattern(
            pattern_id, subject_id="frog-1", actor=AGENT_ID,
            command_prefix="agent", requested_by=AGENT_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "pattern-step-unavailable")
        self.assertEqual(result["completed"], 0)
        # The replay changed nothing at all.
        after = self.kernel.sticker("frog-1")
        self.assertEqual(after.animation, before.animation)
        self.assertEqual((after.x, after.y), (before.x, before.y))
        self.assertEqual(after.revision, before.revision)

    def test_replay_requires_an_accepted_receipt_before_advancing(self):
        """An exhausted agent budget stops replay mid-pattern."""
        self.kernel.register_principal(Principal(
            "agent:tiny", AGENT, tools=farm.AGENT_TOOLS,
            delegable=frozenset(), max_actions=1))
        self.place_frog("frog-agent", x=0.40, y=0.40, owner="agent:tiny")

        library = PatternLibrary()
        controller = JevController(self.kernel, self.jev, patterns=library)
        pattern, error = library.remember(
            label="two moves", asset="frog",
            steps=(PatternStep(verb=MOVE, suffix="STEP-E"),
                   PatternStep(verb=MOVE, suffix="STEP-E")),
            subject_id="frog-agent", learned_by=HUMAN_ID, revision=1)
        self.assertIsNone(error)

        result = controller.replay_pattern(
            pattern.pattern_id, subject_id="frog-agent", actor="agent:tiny",
            command_prefix="budget", requested_by="agent:tiny")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "pattern-step-refused")
        self.assertEqual(result["result"], "partial")
        # `completed` counts ACCEPTED steps; two were attempted.
        self.assertEqual(result["completed"], 1)
        self.assertEqual(len(result["replay"]["steps"]), 2)
        self.assertTrue(result["replay"]["steps"][0]["receipt"]["accepted"])
        self.assertFalse(result["replay"]["steps"][1]["receipt"]["accepted"])
        self.assertEqual(result["replay"]["steps"][1]["receipt"]["reason"],
                         "action-budget-exhausted")

    def test_unknown_pattern_is_refused(self):
        result = self.controller.replay_pattern(
            "pattern-999", subject_id="frog-1", actor=HUMAN_ID,
            command_prefix="ghost", requested_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unknown-pattern")

    def test_every_replayed_step_produces_its_own_receipt(self):
        pattern_id = self.remember(
            ["MOVE:frog-1:STEP-E", "ANIMATE:frog-1:hop"])
        self.place_frog("frog-3", x=0.30, y=0.30)
        result = self.controller.replay_pattern(
            pattern_id, subject_id="frog-3", actor=HUMAN_ID,
            command_prefix="receipts", requested_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        ids = [e["receipt"]["commandId"] for e in result["replay"]["steps"]]
        self.assertEqual(ids, ["receipts-1", "receipts-2"])
        self.assertEqual(len(set(ids)), 2)


# ---------------------------------------------------------------------------
# Jev remains non-authoritative
# ---------------------------------------------------------------------------

class JevStaysNonAuthoritative(PatternCase):

    def test_known_patterns_carry_no_complete_action_keys(self):
        self.teach(["MOVE:frog-1:STEP-E", "ANIMATE:frog-1:hop"])
        self.jev.script = ["NOOP"]
        self.controller.run_goal(
            {"subject": "frog-1", "intent": "animate"},
            actor=HUMAN_ID, command_prefix="scene",
            requested_by=HUMAN_ID, max_turns=1)

        scene = self.jev.scenes[0]
        self.assertIn("known_patterns", scene)
        self.assertEqual(len(scene["known_patterns"]), 1)

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    yield from strings(item)

        table_keys = set(scene["available_actions"])
        for text in strings(scene["known_patterns"]):
            # Every complete legal key contains a colon; no exposed string
            # may be one, nor name the transient instance.
            self.assertNotIn(":", text)
            self.assertNotIn("frog-1", text)
            self.assertNotIn(text, table_keys)

    def test_pattern_memory_does_not_widen_the_choice_surface(self):
        """Known patterns must not add keys to the legal table.

        Memory is populated directly rather than by teaching, so both tables
        are taken at the same world state and the only difference under test
        is the presence of pattern memory.
        """
        goal = {"subject": "frog-1", "intent": "animate"}

        library = PatternLibrary()
        pattern, error = library.remember(
            label="happy dance", asset="frog",
            steps=(PatternStep(verb=MOVE, suffix="STEP-E"),
                   PatternStep(verb=ANIMATE, suffix="hop")),
            subject_id="frog-1", learned_by=HUMAN_ID, revision=1)
        self.assertIsNone(error)

        bare = JevController(self.kernel, StubJev([]), patterns=None)
        remembering = JevController(
            self.kernel, StubJev([]), patterns=library)

        without, _ = bare._table(HUMAN_ID, goal, animate_only=False)
        with_memory, _ = remembering._table(
            HUMAN_ID, goal, animate_only=False)

        self.assertEqual(set(without), set(with_memory))
        self.assertTrue(with_memory)

    def test_a_pattern_fragment_is_not_submittable(self):
        """A stored fragment is not a key the kernel will accept."""
        result = self.teach(["ANIMATE:frog-1:hop"])
        pattern = self.library.get(result["pattern"]["id"])
        fragment = pattern.steps[0].suffix
        receipt = self.kernel.propose_key(
            HUMAN_ID, fragment, "fragment-1")
        self.assertFalse(receipt.accepted)
        self.assertEqual(receipt.reason, "unknown-action-key")

    def test_controller_without_memory_still_works(self):
        controller = JevController(
            self.kernel, StubJev(["ANIMATE:frog-1:hop"]), patterns=None)
        run = controller.run_goal(
            {"subject": "frog-1", "intent": "animate"},
            actor=HUMAN_ID, command_prefix="nomem",
            requested_by=HUMAN_ID, max_turns=1)
        self.assertTrue(run["ok"], run)
        result = controller.remember_trace(
            label="nowhere", subject_id="frog-1", trace=run["trace"],
            learned_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "pattern-memory-unavailable")


# ---------------------------------------------------------------------------
# The worked example
# ---------------------------------------------------------------------------

class FroggyLearnsAHappyDance(PatternCase):
    """A child teaches Froggy a happy dance, then asks for it again."""

    def test_froggy_learns_and_replays_a_happy_dance(self):
        # 1. The child moves Froggy about and makes it hop. Every one of
        #    these is an ordinary accepted kernel mutation.
        trace = self.perform([
            "MOVE:frog-1:STEP-E",
            "MOVE:frog-1:STEP-N",
            "ANIMATE:frog-1:hop",
        ])
        self.assertTrue(all(e["receipt"]["accepted"] for e in trace))

        # 2. "Remember that as your happy dance." Eventually OmegaLLM turns
        #    the child's sentence into exactly this bounded host request.
        remembered = self.controller.remember_trace(
            label="happy dance", subject_id="frog-1", trace=trace,
            learned_by=HUMAN_ID)
        self.assertTrue(remembered["ok"], remembered)
        pattern_id = remembered["pattern"]["id"]
        self.assertEqual(
            remembered["pattern"]["steps"],
            [{"verb": MOVE, "suffix": "STEP-E"},
             {"verb": MOVE, "suffix": "STEP-N"},
             {"verb": ANIMATE, "suffix": "hop"}])

        # 3. A second frog, elsewhere on the page, in its rest pose.
        froggy = self.place_frog("frog-2", x=0.35, y=0.65)
        self.assertEqual(froggy.animation, "rest")

        # 4. "Froggy, do your happy dance!" Three fresh proposals follow.
        result = self.controller.replay_pattern(
            pattern_id, subject_id="frog-2", actor=HUMAN_ID,
            command_prefix="happy", requested_by=HUMAN_ID)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["label"], "happy dance")
        self.assertEqual(result["completed"], 3)

        # 5. The kernel decided each mutation, one receipt at a time.
        self.assertEqual(
            [e["receipt"]["action"] for e in result["replay"]["steps"]],
            ["move-sticker", "move-sticker", "animate-own-sticker"])
        self.assertTrue(all(e["receipt"]["accepted"] for e in result["replay"]["steps"]))

        danced = self.kernel.sticker("frog-2")
        self.assertGreater(danced.x, froggy.x)
        self.assertLess(danced.y, froggy.y)
        self.assertEqual(danced.animation, "hop")

        # 6. The first frog was not touched by the replay.
        self.assertEqual(self.kernel.sticker("frog-1").animation, "hop")


if __name__ == "__main__":
    unittest.main()
