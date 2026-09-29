"""
Tests for the multimodal interaction record.

StickerBook is voice-interface-forward, and a child's meaning may be spread
across speech, typing, pointing, boxing an area and dragging a sticker. An
`InteractionEpisode` says **which bounded signals took part in one
conversational turn**. It does not say what they meant:

    Omega talks. Jev chooses. The kernel decides.
    Input history is not world history.

These tests prove the facts arrive at OmegaLLM through a bounded, stable
interface, that the host never interprets them, and that nothing here touches
authority.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge as bridge_mod  # noqa: E402
import farm  # noqa: E402
from interaction import (  # noqa: E402
    MAX_EPISODES, MAX_SIGNALS_PER_EPISODE, SIGNAL_STICKER_DRAG,
    InteractionLog, valid_input_mode,
)

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "core"))

from stickerbook_core import (  # noqa: E402
    ALL_ACTIONS, MUTATING_ACTIONS, StickerInstance,
)

HUMAN_ID = farm.HUMAN_ID


class FakeOmegaLLM:
    """The linguistic Omega loop, deterministically.

    It records the scene it was given so tests can inspect exactly what
    multimodal context reached it.
    """

    def __init__(self, goal=None):
        self.scenes = []
        self.texts = []
        self.references = []
        self.goal = goal

    def capabilities(self):
        return {"creator_agent": False, "conversational_agent": True}

    def inference_options(self):
        return [{
            "id": "openrouter", "label": "OpenRouter",
            "description": "Configured OpenRouter.",
            "default_model": "z-ai/glm-5.2", "model_locked": False,
            "sponsored": False, "available": True,
        }]

    def creator_draft(self, **kwargs):
        return {"ok": False, "error": "creator-agent-unavailable"}

    def converse(self, *, text, principal, scene, reference=None,
                 inference=None):
        self.scenes.append(scene)
        self.texts.append(text)
        self.references.append(reference)
        reply = {"ok": True, "reply": "Okay!"}
        if self.goal is not None:
            reply["goal"] = dict(self.goal)
        return reply


class FakeOmegaJev:
    def __init__(self):
        self.calls = []

    def available(self):
        return True

    def choose(self, *, goal, scene, actions, turn, max_turns):
        self.calls.append({"goal": dict(goal), "actions": dict(actions)})
        if goal.get("intent") == "animate":
            for key in sorted(actions):
                if key.startswith("ANIMATE:") \
                        and not key.endswith(":none") \
                        and not key.endswith(":rest"):
                    return {"ok": True, "choice": key}
        return {"ok": True, "choice": "NOOP"}


class FailingOmegaLLM(FakeOmegaLLM):
    def converse(self, **kwargs):
        super().converse(**kwargs)
        raise RuntimeError("inference failed")


class InteractionCase(unittest.TestCase):

    def setUp(self):
        self.kernel = farm.build_world()
        self.llm = FakeOmegaLLM()
        self.jev = FakeOmegaJev()
        self.bridge = bridge_mod.Bridge(
            self.kernel, agent_runtime=self.llm, jev_runtime=self.jev)
        self.place("frog-1", x=0.30, y=0.40)

    def place(self, sticker_id, *, x, y, asset="frog"):
        self.kernel.place_sticker(StickerInstance(
            sticker_id, HUMAN_ID, HUMAN_ID, asset, 1, x=x, y=y,
            animation="rest"))
        return self.kernel.sticker(sticker_id)

    def drag(self, sticker="frog-1", *, command_id="d-1",
             points=((0.34, 0.32), (0.44, 0.36)), release=(0.50, 0.50),
             duration_ms=1100):
        last = max(1, len(points))
        return self.bridge.propose_move({
            "sticker": sticker,
            "command_id": command_id,
            "point": {"x": release[0], "y": release[1]},
            "drag": {
                "samples": [
                    {"t": (index + 1) / (last + 1), "x": x, "y": y}
                    for index, (x, y) in enumerate(points)
                ],
                "duration_ms": duration_ms,
            },
        })

    def say(self, text, **extra):
        body = {"text": text}
        body.update(extra)
        return self.bridge.converse(body)

    def last_scene_interaction(self):
        return self.llm.scenes[-1]["interaction"]


# ---------------------------------------------------------------------------
# Voice / text alone
# ---------------------------------------------------------------------------

class UtteranceOnly(InteractionCase):

    def test_a_plain_utterance_creates_an_episode_with_no_gestures(self):
        result = self.say("Hello StickerBook", input_mode="voice")
        self.assertTrue(result["ok"], result)

        episode = result["interaction"]
        self.assertEqual(episode["episodeId"], "episode-1")
        self.assertEqual(episode["utterance"], "Hello StickerBook")
        self.assertEqual(episode["inputMode"], "voice")
        self.assertIsNone(episode["deicticReference"])
        self.assertEqual(episode["signals"], [])

    def test_typed_input_mode_is_recorded_as_text(self):
        result = self.say("hello there", input_mode="text")
        self.assertEqual(result["interaction"]["inputMode"], "text")

    def test_an_unknown_input_mode_is_simply_not_recorded(self):
        """Descriptive metadata, so a bad claim is dropped, not fatal."""
        result = self.say("hello", input_mode="telepathy")
        self.assertTrue(result["ok"])
        self.assertIsNone(result["interaction"]["inputMode"])

    def test_input_mode_confers_no_authority(self):
        self.assertIsNone(valid_input_mode("operator"))
        self.assertIsNone(valid_input_mode(True))
        self.assertEqual(valid_input_mode("voice"), "voice")

    def test_omegallm_sees_the_episode_in_its_scene(self):
        self.say("Hello", input_mode="voice")
        scene = self.llm.scenes[-1]
        self.assertIn("interaction", scene)
        self.assertEqual(scene["interaction"]["utterance"], "Hello")


# ---------------------------------------------------------------------------
# Point / box deixis
# ---------------------------------------------------------------------------

class DeicticReference(InteractionCase):

    def test_a_point_appears_in_the_turn_context(self):
        result = self.say(
            "Put him over there",
            reference={"kind": "point", "point": {"x": 0.7, "y": 0.2}})
        reference = result["interaction"]["deicticReference"]
        self.assertEqual(reference["kind"], "point")
        self.assertEqual(reference["point"], {"x": 0.7, "y": 0.2})
        # The host stamps the page itself.
        self.assertIn("page", reference)

    def test_a_box_appears_in_the_turn_context(self):
        result = self.say(
            "Go around here",
            reference={"kind": "box",
                       "box": {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.5}})
        reference = result["interaction"]["deicticReference"]
        self.assertEqual(reference["kind"], "box")
        self.assertEqual(reference["box"]["x2"], 0.4)

    def test_the_reference_is_not_classified(self):
        """A box is an observed area, not a named shape or a meaning."""
        result = self.say(
            "around here",
            reference={"kind": "box",
                       "box": {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.5}})
        record = result["interaction"]
        blob = json.dumps({"reference": record["deicticReference"],
                           "signals": record["signals"]}).lower()
        for word in ("circle", "loop", "zigzag", "zig-zag", "swoop",
                     "around", "region", "route"):
            self.assertNotIn(word, blob)

    def test_the_reference_changes_no_world_state(self):
        before = self.kernel.revision
        self.say("over there",
                 reference={"kind": "point", "point": {"x": 0.7, "y": 0.2}})
        self.assertEqual(self.kernel.revision, before)
        self.assertEqual(len(self.bridge.receipts(limit=50)), 0)

    def test_an_invalid_reference_is_still_a_bad_request(self):
        result = self.say("there", reference={"kind": "elsewhere"})
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.bridge.interactions), 0)

    def test_the_existing_reference_argument_still_reaches_omegallm(self):
        self.say("over there",
                 reference={"kind": "point", "point": {"x": 0.7, "y": 0.2}})
        self.assertIsNotNone(self.llm.references[-1])
        self.assertEqual(self.llm.references[-1]["kind"], "point")


# ---------------------------------------------------------------------------
# Sticker drag as conversational context
# ---------------------------------------------------------------------------

class DragContext(InteractionCase):

    def test_failed_inference_still_records_and_consumes_the_turn(self):
        self.drag()
        self.bridge.agent_runtime = FailingOmegaLLM()
        result = self.say("like this")
        self.assertEqual(result["error"], "agent-runtime-error")
        self.assertEqual(self.bridge.interactions.latest().signals[0].ref,
                         "drag-1")
        self.bridge.agent_runtime = self.llm
        retry = self.say("try again")
        self.assertEqual(retry["interaction"]["signals"], [])

    def test_evicted_marker_uses_retained_newer_traces(self):
        self.drag(command_id="first")
        self.say("first")
        for index in range(33):
            self.drag(command_id="later-%d" % index)
        result = self.say("recent")
        self.assertEqual([s["ref"] for s in result["interaction"]["signals"]],
                         ["drag-31", "drag-32", "drag-33", "drag-34"])

    def test_a_recent_drag_becomes_bounded_context(self):
        self.drag()
        result = self.say("Make Froggy go like this", input_mode="voice")

        signals = result["interaction"]["signals"]
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0], {
            "kind": SIGNAL_STICKER_DRAG,
            "ref": "drag-1",
            "subject": "frog-1",
            "durationMs": 1100,
        })

    def test_raw_trajectory_samples_never_reach_omegallm(self):
        self.drag()
        self.say("like this")
        blob = json.dumps(self.llm.scenes[-1])
        self.assertNotIn("samples", blob)
        self.assertNotIn("\"dx\"", blob)
        self.assertNotIn("\"dy\"", blob)
        # The host still holds the whole trajectory.
        trace = self.bridge.traces.get("drag-1")
        self.assertGreaterEqual(len(trace.samples), 2)

    def test_no_shape_label_is_invented(self):
        self.drag(points=((0.34, 0.30), (0.44, 0.30), (0.44, 0.50),
                          (0.31, 0.41)))
        self.say("remember that")
        blob = json.dumps(self.last_scene_interaction()["signals"]).lower()
        for word in ("circle", "loop", "zigzag", "zig-zag", "swoop",
                     "curve", "arc", "shape"):
            self.assertNotIn(word, blob)

    def test_a_drag_is_offered_once_then_the_window_moves_on(self):
        self.drag()
        first = self.say("like this")
        self.assertEqual(len(first["interaction"]["signals"]), 1)
        second = self.say("and again")
        self.assertEqual(second["interaction"]["signals"], [])

    def test_drags_after_the_previous_turn_are_associated_in_order(self):
        self.say("first turn")
        self.drag(command_id="d-a", release=(0.50, 0.50))
        self.drag(command_id="d-b", release=(0.60, 0.60))
        result = self.say("both of those")
        refs = [s["ref"] for s in result["interaction"]["signals"]]
        self.assertEqual(refs, ["drag-1", "drag-2"])

    def test_association_is_bounded_to_the_most_recent(self):
        for index in range(MAX_SIGNALS_PER_EPISODE + 3):
            self.drag(command_id="d-%d" % index,
                      release=(0.40 + 0.02 * index, 0.50))
        result = self.say("all that")
        signals = result["interaction"]["signals"]
        self.assertEqual(len(signals), MAX_SIGNALS_PER_EPISODE)
        # The most recent ones, in host-observed order.
        self.assertEqual([s["ref"] for s in signals],
                         ["drag-4", "drag-5", "drag-6", "drag-7"])

    def test_a_refused_drag_never_becomes_context(self):
        self.bridge.propose_move({
            "sticker": "frog-1", "command_id": "stale",
            "point": {"x": 0.5, "y": 0.5}, "based_on_revision": 0,
            "drag": {"samples": [{"t": 0.5, "x": 0.4, "y": 0.4}],
                     "duration_ms": 500},
        })
        result = self.say("that")
        self.assertEqual(result["interaction"]["signals"], [])


# ---------------------------------------------------------------------------
# The browser cannot fabricate history
# ---------------------------------------------------------------------------

class HostOwnsAssociation(InteractionCase):

    def test_a_fabricated_trace_reference_is_not_associated(self):
        result = self.say("that", drags=["drag-999"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["interaction"]["signals"], [])
        self.assertEqual(self.last_scene_interaction()["signals"], [])

    def test_a_fabricated_reference_does_not_break_the_conversation(self):
        """Association failing closed is not a reason to refuse to talk."""
        result = self.say("hello", drags=["nope", 17, None])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["reply"], "Okay!")

    def test_client_list_cannot_suppress_recent_host_drag(self):
        self.drag()
        result = self.say("this", drags=[])
        self.assertEqual([s["ref"] for s in result["interaction"]["signals"]],
                         ["drag-1"])

    def test_a_client_list_cannot_select_an_old_trace(self):
        self.drag()
        self.say("first turn")
        result = self.say("that one", drags=["drag-1"])
        self.assertEqual(result["interaction"]["signals"], [])

    def test_the_browser_cannot_name_another_principal(self):
        result = self.say("hello", principal="operator", actor="operator")
        self.assertEqual(result["interaction"]["episodeId"], "episode-1")
        episode = self.bridge.interactions.latest()
        self.assertEqual(episode.principal, HUMAN_ID)

    def test_the_browser_cannot_forge_a_subject_on_a_signal(self):
        self.drag()
        result = self.say("that", drags=["drag-1"], subject="forged")
        # Subject comes from the host's own trace, not from the request.
        self.assertEqual(result["interaction"]["signals"][0]["subject"],
                         "frog-1")

    def test_episode_ids_and_sequence_are_host_issued(self):
        self.say("one", episode_id="episode-hack", sequence=99)
        self.say("two")
        ids = [e.episode_id for e in self.bridge.interactions.episodes()]
        self.assertEqual(ids, ["episode-1", "episode-2"])
        self.assertEqual(
            [e.sequence for e in self.bridge.interactions.episodes()], [1, 2])


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

class Bounds(InteractionCase):

    def test_the_episode_log_is_bounded(self):
        log = InteractionLog(max_episodes=3)
        from interaction import InteractionEpisode
        for index in range(6):
            log.add(InteractionEpisode(
                episode_id=log.next_episode_id(), principal=HUMAN_ID,
                sequence=index, scene_revision=0))
        self.assertEqual(len(log), 3)
        self.assertEqual(log.episodes()[0].episode_id, "episode-4")

    def test_sequence_remains_monotonic_after_eviction(self):
        self.bridge.interactions = InteractionLog(max_episodes=2)
        for index in range(4):
            self.say("turn %d" % index)
        self.assertEqual([e.sequence for e in self.bridge.interactions.episodes()],
                         [3, 4])

    def test_the_default_bound_is_small(self):
        self.assertLessEqual(MAX_EPISODES, 64)
        self.assertLessEqual(MAX_SIGNALS_PER_EPISODE, 8)

    def test_existing_utterance_length_limit_still_applies(self):
        result = self.say("x" * 2001)
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.bridge.interactions), 0)


# ---------------------------------------------------------------------------
# Authority did not move
# ---------------------------------------------------------------------------

class AuthorityUnchanged(InteractionCase):

    def test_an_episode_creates_no_kernel_receipt(self):
        before_receipts = len(self.bridge.receipts(limit=100))
        before_revision = self.kernel.revision
        self.say("hello", input_mode="voice")
        self.assertEqual(len(self.bridge.receipts(limit=100)),
                         before_receipts)
        self.assertEqual(self.kernel.revision, before_revision)
        self.assertEqual(len(self.bridge.interactions), 1)

    def test_a_drag_plus_utterance_still_makes_exactly_one_mutation(self):
        before = self.kernel.revision
        self.drag()
        self.say("like this")
        self.assertEqual(self.kernel.revision, before + 1)
        moves = [r for r in self.bridge.receipts(limit=100)
                 if r["action"] == "move-sticker"]
        self.assertEqual(len(moves), 1)

    def test_core_action_vocabulary_is_unchanged(self):
        self.assertEqual(ALL_ACTIONS, frozenset({
            "noop", "observe", "add-own-sticker", "move-sticker",
            "animate-own-sticker", "resize-own-sticker",
            "set-sticker-facing", "remove-own-sticker",
            "remove-agent-sticker", "create-agent",
        }))
        self.assertEqual(len(MUTATING_ACTIONS), 8)

    def test_the_episode_holds_no_authority_object(self):
        self.drag()
        self.say("that")
        episode = self.bridge.interactions.latest()
        for value in episode.to_dict().values():
            self.assertNotIsInstance(value, type(self.kernel))
        blob = json.dumps(episode.to_dict())
        self.assertNotIn("propose", blob)
        self.assertNotIn("tools", blob)


# ---------------------------------------------------------------------------
# The direct path is untouched
# ---------------------------------------------------------------------------

class DirectPathUnchanged(InteractionCase):

    def test_double_click_still_reaches_jev_without_omegallm(self):
        result = self.bridge.animate(
            {"sticker": "frog-1", "command_id": "dbl-1"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.llm.scenes, [])
        self.assertEqual(len(self.bridge.interactions), 0)
        self.assertTrue(self.jev.calls)
        for key in self.jev.calls[-1]["actions"]:
            self.assertTrue(key == "NOOP" or key.startswith("ANIMATE:"))

    def test_a_drag_alone_starts_no_conversation(self):
        self.drag()
        self.assertEqual(self.llm.scenes, [])
        self.assertEqual(len(self.bridge.interactions), 0)
        self.assertEqual(len(self.bridge.traces), 1)

    def test_referencing_a_drag_later_does_not_reroute_the_original(self):
        """The move was a direct human action and stays one."""
        self.drag()
        entry = self.bridge.history.entries()[-1]
        self.assertEqual(entry.origin, "human-gesture")
        self.assertIsNone(entry.translated_by)
        self.assertIsNone(entry.selected_by)

        self.say("like this")
        entry_after = self.bridge.history.entries()[-1]
        self.assertEqual(entry_after.origin, "human-gesture")
        self.assertIsNone(entry_after.translated_by)


# ---------------------------------------------------------------------------
# Existing behaviour is unchanged
# ---------------------------------------------------------------------------

class ExistingBehaviourGreen(InteractionCase):

    def test_discrete_pattern_memory_still_works(self):
        for index, key in enumerate(
                ["ANIMATE:frog-1:hop", "MOVE:frog-1:STEP-E"]):
            receipt = self.kernel.propose_key(
                HUMAN_ID, key, "k-%d" % index, requested_by=HUMAN_ID,
                move_candidates=self.bridge.jev_controller._move_candidates(
                    self.kernel.sticker("frog-1")))
            self.bridge.history.record(
                receipt, origin="gesture-jev", key=key, subject_id="frog-1")
        result = self.bridge.jev_controller.remember_recent(
            subject_id="frog-1", label="happy dance", learned_by=HUMAN_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["pattern"]["steps"]), 2)

    def test_a_drag_is_still_not_learnable(self):
        self.drag()
        result = self.bridge.jev_controller.remember_recent(
            subject_id="frog-1", label="swoop", learned_by=HUMAN_ID)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no-accepted-pattern-steps")

    def test_sticker_drag_capture_is_unchanged(self):
        self.drag()
        trace = self.bridge.traces.get("drag-1")
        self.assertEqual(trace.kind, "sticker-drag")
        self.assertEqual(trace.samples[0].t, 0.0)
        self.assertEqual(trace.samples[-1].t, 1.0)
        self.assertTrue(trace.terminal_move_accepted)

    def test_a_goal_still_flows_to_jev(self):
        self.llm.goal = {"subject": "frog-1", "intent": "animate"}
        result = self.say("make him hop")
        self.assertIn("jev", result)
        self.assertTrue(self.jev.calls)
        self.assertIn("interaction", result)


if __name__ == "__main__":
    unittest.main()
