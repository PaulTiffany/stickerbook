"""
Mechanical tests for the StickerBook authority kernel.

Test names map to the numbered invariants in the root SECURITY.md section 26
table. Anything not proved here stays marked N/A YET or GAP in that table.

Standard library only:  python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stickerbook_core import (  # noqa: E402
    ADD_OWN_STICKER, AGENT, ANIMATE_OWN_STICKER, StickerDefinition, Command,
    CREATE_AGENT, HUMAN, Kernel, LOCAL_MULTI_AGENT, LOCAL_SINGLE_AGENT, NOOP,
    MOVE_STICKER, OBSERVE, OPERATOR, PAGES_DEMO, Principal,
    REMOVE_AGENT_STICKER, REMOVE_OWN_STICKER, RESIZE_OWN_STICKER,
    SET_STICKER_FACING, StickerInstance,
)

ASSETS = {
    "moth": StickerDefinition("moth", ("none", "flutter", "orbit")),
    "lantern": StickerDefinition("lantern", ("none", "glow")),
}

AGENT_TOOLS = frozenset({
    OBSERVE, NOOP, ADD_OWN_STICKER, MOVE_STICKER, ANIMATE_OWN_STICKER,
    RESIZE_OWN_STICKER, SET_STICKER_FACING,
})
HUMAN_TOOLS = AGENT_TOOLS | {REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER}


def build(profile=LOCAL_SINGLE_AGENT, agent_tools=AGENT_TOOLS):
    """A world with one human-owned and one agent-owned sticker."""
    k = Kernel(profile, assets=ASSETS,
               presets={"far": (0.9, 0.9), "near": (0.1, 0.1)})
    k.register_principal(Principal("human:kid", HUMAN, tools=HUMAN_TOOLS))
    k.register_principal(Principal("operator", OPERATOR, tools=HUMAN_TOOLS))
    k.register_principal(Principal(
        "agent:jev", AGENT, tools=agent_tools, delegable=frozenset()))
    k.place_sticker(StickerInstance(
        "lantern-h", "human:kid", "human:kid", "lantern", 1, x=0.2, y=0.2))
    k.place_sticker(StickerInstance(
        "moth-a", "agent:jev", "agent:jev", "moth", 1, x=0.8, y=0.8))
    return k


class T01_AgentCannotModifyHumanSticker(unittest.TestCase):

    def test_01_agent_cannot_move_human_sticker(self):
        k = build()
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "c1",
                              "lantern-h", (("x", 0.7), ("y", 0.3))))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "not-owner")
        self.assertEqual(k.sticker("lantern-h").x, 0.2)

    def test_01b_agent_cannot_animate_human_sticker(self):
        k = build()
        r = k.propose(Command(ANIMATE_OWN_STICKER, "agent:jev", "c1",
                              "lantern-h", (("animation", "glow"),)))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "not-owner")
        self.assertEqual(k.sticker("lantern-h").animation, "none")

    def test_01c_human_sticker_never_appears_in_agent_action_table(self):
        k = build()
        for key in k.available_actions("agent:jev"):
            self.assertNotIn("lantern-h", key)


class T02_AgentCannotRemoveHumanSticker(unittest.TestCase):

    def test_02_agent_has_no_sticker_removal_capability(self):
        k = build()
        r = k.propose(Command(
            REMOVE_OWN_STICKER, "agent:jev", "c1", "moth-a"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "action-not-in-effective-authority")
        self.assertIsNotNone(k.sticker("moth-a"))

    def test_02b_agent_cannot_use_the_human_removal_tool(self):
        k = build()
        r = k.propose(Command(REMOVE_AGENT_STICKER, "agent:jev", "c1", "lantern-h"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "action-not-in-effective-authority")
        self.assertIsNotNone(k.sticker("lantern-h"))


class T03_AgentCannotAlterOwnership(unittest.TestCase):

    def test_03_no_action_can_change_an_owner(self):
        k = build()
        before = k.sticker("moth-a").owner
        for params in ((("owner", "human:kid"),), (("created_by", "human:kid"),)):
            k.propose(Command(MOVE_STICKER, "agent:jev", "c" + params[0][0],
                              "moth-a", params + (("x", 0.7), ("y", 0.3))))
        self.assertEqual(k.sticker("moth-a").owner, before)
        self.assertEqual(k.sticker("moth-a").created_by, "agent:jev")

    def test_03b_created_sticker_is_owned_by_actor_not_by_request(self):
        k = build()
        r = k.propose(Command(ADD_OWN_STICKER, "agent:jev", "c1", None,
                              (("asset", "moth"), ("owner", "human:kid"), ("x", 0.4), ("y", 0.4))))
        self.assertTrue(r.accepted)
        self.assertEqual(k.sticker(r.object_id).owner, "agent:jev")
        self.assertEqual(k.sticker(r.object_id).created_by, "agent:jev")


class HumanMovementStopsAnimation(unittest.TestCase):

    def test_human_move_sets_an_animated_sticker_down_still(self):
        k = build()
        animated = k.propose(Command(
            ANIMATE_OWN_STICKER,
            "human:kid",
            "animate-human",
            "lantern-h",
            (("animation", "glow"),),
        ))
        self.assertTrue(animated.accepted)
        self.assertEqual(k.sticker("lantern-h").animation, "glow")

        moved = k.propose(Command(
            MOVE_STICKER,
            "human:kid",
            "move-human",
            "lantern-h",
            (("x", 0.6), ("y", 0.4)),
        ))
        self.assertTrue(moved.accepted)
        self.assertEqual(k.sticker("lantern-h").animation, "none")

    def test_agent_move_does_not_implicitly_cancel_its_animation(self):
        k = build()
        animated = k.propose(Command(
            ANIMATE_OWN_STICKER,
            "agent:jev",
            "animate-agent",
            "moth-a",
            (("animation", "flutter"),),
        ))
        self.assertTrue(animated.accepted)
        self.assertEqual(k.sticker("moth-a").animation, "flutter")

        moved = k.propose(Command(
            MOVE_STICKER,
            "agent:jev",
            "move-agent",
            "moth-a",
            (("x", 0.6), ("y", 0.4)),
        ))
        self.assertTrue(moved.accepted)
        self.assertEqual(k.sticker("moth-a").animation, "flutter")


class T04_UnknownActionRejects(unittest.TestCase):

    def test_04_unknown_action_name(self):
        k = build()
        r = k.propose(Command("delete-object", "agent:jev", "c1", "lantern-h"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "unknown-action")

    def test_04b_unknown_action_key(self):
        k = build()
        r = k.propose_key("agent:jev", "REMOVE:lantern-h", "c1")
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "unknown-action-key")

    def test_04c_unknown_principal(self):
        k = build()
        r = k.propose(Command(NOOP, "agent:ghost", "c1"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "unknown-principal")


class T05_MalformedFieldsReject(unittest.TestCase):

    def test_05_argument_outside_bounded_domain(self):
        """A position is bounded even though it is continuous."""
        k = build()
        cases = [
            ((("x", "../../etc/passwd"), ("y", 0.5)), "position-not-numeric"),
            ((("x", 1.5), ("y", 0.5)), "position-out-of-page"),
            ((("x", -0.01), ("y", 0.5)), "position-out-of-page"),
            ((("x", float("nan")), ("y", 0.5)), "position-not-finite"),
            ((("x", float("inf")), ("y", 0.5)), "position-not-finite"),
            ((("y", 0.5),), "missing-position"),
        ]
        for i, (params, reason) in enumerate(cases):
            with self.subTest(params=params):
                r = k.propose(Command(MOVE_STICKER, "agent:jev", "c%d" % i,
                                      "moth-a", params))
                self.assertFalse(r.accepted)
                self.assertEqual(r.reason, reason)

    def test_05b_missing_and_unknown_objects(self):
        k = build()
        self.assertEqual(
            k.propose(Command(MOVE_STICKER, "agent:jev", "c1", None,
                              (("x", 0.7), ("y", 0.3)))).reason, "missing-object")
        self.assertEqual(
            k.propose(Command(MOVE_STICKER, "agent:jev", "c2", "nope",
                              (("x", 0.7), ("y", 0.3)))).reason, "unknown-object")

    def test_05c_unknown_asset(self):
        k = build()
        r = k.propose(Command(ADD_OWN_STICKER, "agent:jev", "c1", None,
                              (("asset", "malware"), ("x", 0.4), ("y", 0.4))))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "unknown-asset")

    def test_05d_animation_not_declared_by_asset(self):
        k = build()
        r = k.propose(Command(ANIMATE_OWN_STICKER, "agent:jev", "c1", "moth-a",
                              (("animation", "explode"),)))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "animation-not-declared-by-asset")


class StickerScaleBounds(unittest.TestCase):

    def test_agent_can_resize_own_sticker_inside_definition_bounds(self):
        k = build()
        r = k.propose(Command(
            RESIZE_OWN_STICKER, "agent:jev", "scale-ok", "moth-a",
            (("scale", 1.08),),
        ))
        self.assertTrue(r.accepted, r.reason)
        self.assertAlmostEqual(k.sticker("moth-a").scale, 1.08)

    def test_resize_refuses_values_beyond_plus_minus_ten_percent(self):
        k = build()
        for i, scale in enumerate((0.89, 1.11)):
            r = k.propose(Command(
                RESIZE_OWN_STICKER, "agent:jev", "scale-bad-%d" % i,
                "moth-a", (("scale", scale),),
            ))
            self.assertFalse(r.accepted)
            self.assertEqual(r.reason, "scale-out-of-bounds")
        self.assertEqual(k.sticker("moth-a").scale, 1.0)

    def test_agent_action_table_offers_only_bounded_scale_steps(self):
        k = build()
        keys = set(k.available_actions("agent:jev"))
        self.assertIn("SCALE:moth-a:UP", keys)
        self.assertIn("SCALE:moth-a:DOWN", keys)
        self.assertNotIn("REMOVE:moth-a", keys)

    def test_definition_loader_accepts_clip_names_but_not_authority(self):
        definition = Kernel.load_definition({
            "name": "butterfly",
            "default_clip": "rest",
            "clips": {"rest": {}, "flutter": {}},
            "scale_bounds": {"min": 0.92, "max": 1.07},
            "tools": ["delete-everything"],
            "owner": "agent:spoof",
        })
        self.assertEqual(definition.animations, ("none", "rest", "flutter"))
        self.assertEqual(definition.rest_animation, "rest")
        self.assertEqual(definition.scale_min, 0.92)
        self.assertEqual(definition.scale_max, 1.07)
        self.assertFalse(hasattr(definition, "tools"))
        self.assertFalse(hasattr(definition, "owner"))


class StickerFacingTransform(unittest.TestCase):

    def test_agent_can_face_own_sticker_left_and_right(self):
        k = build()
        left = k.propose(Command(
            SET_STICKER_FACING, "agent:jev", "face-left", "moth-a",
            (("facing", "left"),),
        ))
        self.assertTrue(left.accepted, left.reason)
        self.assertEqual(k.sticker("moth-a").facing, "left")

        right = k.propose(Command(
            SET_STICKER_FACING, "agent:jev", "face-right", "moth-a",
            (("facing", "right"),),
        ))
        self.assertTrue(right.accepted, right.reason)
        self.assertEqual(k.sticker("moth-a").facing, "right")

    def test_facing_rejects_unknown_values(self):
        k = build()
        r = k.propose(Command(
            SET_STICKER_FACING, "agent:jev", "face-bad", "moth-a",
            (("facing", "inside-out"),),
        ))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "facing-not-supported")
        self.assertEqual(k.sticker("moth-a").facing, "right")

    def test_agent_action_table_offers_only_other_facing(self):
        k = build()
        keys = set(k.available_actions("agent:jev"))
        self.assertIn("FACE:moth-a:LEFT", keys)
        self.assertNotIn("FACE:moth-a:RIGHT", keys)

        k.propose_key("agent:jev", "FACE:moth-a:LEFT", "face-key")
        keys = set(k.available_actions("agent:jev"))
        self.assertIn("FACE:moth-a:RIGHT", keys)
        self.assertNotIn("FACE:moth-a:LEFT", keys)

    def test_facing_survives_move_animation_and_resize(self):
        k = build()
        self.assertTrue(k.propose(Command(
            SET_STICKER_FACING, "agent:jev", "f1", "moth-a",
            (("facing", "left"),),
        )).accepted)
        self.assertTrue(k.propose(Command(
            MOVE_STICKER, "agent:jev", "f2", "moth-a",
            (("x", 0.7), ("y", 0.6)),
        )).accepted)
        self.assertTrue(k.propose(Command(
            ANIMATE_OWN_STICKER, "agent:jev", "f3", "moth-a",
            (("animation", "flutter"),),
        )).accepted)
        self.assertTrue(k.propose(Command(
            RESIZE_OWN_STICKER, "agent:jev", "f4", "moth-a",
            (("scale", 1.04),),
        )).accepted)
        self.assertEqual(k.sticker("moth-a").facing, "left")


class T06_AgentCannotExpandCapabilities(unittest.TestCase):

    def test_06_acting_does_not_change_effective_authority(self):
        k = build()
        before = k.effective_tools("agent:jev")
        for key in list(k.available_actions("agent:jev"))[:5]:
            k.propose_key("agent:jev", key, "c" + key)
        self.assertEqual(k.effective_tools("agent:jev"), before)

    def test_06b_profile_ceiling_clamps_an_overprivileged_principal(self):
        # Registered with every tool, including the human-only one.
        k = build(agent_tools=HUMAN_TOOLS | {CREATE_AGENT})
        tools = k.effective_tools("agent:jev")
        self.assertNotIn(REMOVE_AGENT_STICKER, tools)
        self.assertNotIn(CREATE_AGENT, tools)
        self.assertEqual(tools, AGENT_TOOLS)

    def test_06c_create_agent_unavailable_in_single_agent_profile(self):
        k = build(agent_tools=AGENT_TOOLS | {CREATE_AGENT})
        r = k.propose(Command(CREATE_AGENT, "agent:jev", "c1", None,
                              (("child_id", "agent:child"),)))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "action-not-in-effective-authority")


class T07_StaleRevision(unittest.TestCase):

    def test_07_human_action_beats_stale_agent_intent(self):
        k = build()
        observed = k.sticker("moth-a").revision       # agent observes here
        # The human (or anything else) changes the same object first.
        k.place_sticker(StickerInstance(
            "moth-a", "agent:jev", "agent:jev", "moth", 1, x=0.1, y=0.1))
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "c1", "moth-a",
                              (("x", 0.7), ("y", 0.3)), based_on_revision=observed))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "stale-revision")
        self.assertEqual(k.sticker("moth-a").x, 0.1)

    def test_07b_fresh_revision_is_accepted(self):
        k = build()
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "c1", "moth-a",
                              (("x", 0.7), ("y", 0.3)),
                              based_on_revision=k.revision))
        self.assertTrue(r.accepted, r.reason)

    def test_07c_revision_from_the_future_is_rejected(self):
        k = build()
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "c1", "moth-a",
                              (("x", 0.7), ("y", 0.3)),
                              based_on_revision=k.revision + 99))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "invalid-revision")


class T08_Idempotency(unittest.TestCase):

    def test_08_duplicate_command_id_does_not_duplicate_effect(self):
        k = build()
        first = k.propose(Command(ADD_OWN_STICKER, "agent:jev", "cmd-1", None,
                                  (("asset", "moth"), ("x", 0.4), ("y", 0.4))))
        count = len(k.sticker_ids())
        second = k.propose(Command(ADD_OWN_STICKER, "agent:jev", "cmd-1", None,
                                   (("asset", "moth"), ("x", 0.4), ("y", 0.4))))
        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertTrue(second.replayed)
        self.assertFalse(first.replayed)
        self.assertEqual(second.object_id, first.object_id)
        self.assertEqual(len(k.sticker_ids()), count)


class T09_T16_DisableAndStopPath(unittest.TestCase):

    def test_09_disabled_agent_cannot_mutate(self):
        k = build()
        k.set_enabled("agent:jev", False)
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "c1", "moth-a",
                              (("x", 0.7), ("y", 0.3))))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "principal-disabled")

    def test_16_stop_path_needs_no_agent_cooperation(self):
        k = build()
        # The operator disables the agent directly. The agent is not asked,
        # not notified, and has no opportunity to object or interfere.
        k.set_enabled("agent:jev", False)
        self.assertEqual(k.available_actions("agent:jev"), {})
        for action in (NOOP, MOVE_STICKER, ADD_OWN_STICKER):
            r = k.propose(Command(action, "agent:jev", "c" + action, "moth-a",
                                  (("x", 0.7), ("y", 0.3), ("asset", "moth"))))
            self.assertFalse(r.accepted)

    def test_16b_disable_fails_toward_less_authority(self):
        k = build()
        k.set_enabled("agent:jev", False)
        self.assertEqual(k.view("agent:jev")["available_actions"], [])


class T10_RestartDoesNotExpandAuthority(unittest.TestCase):

    def test_10_reregistering_with_more_tools_changes_nothing(self):
        k = build()
        before = k.effective_tools("agent:jev")
        # Simulate a reconnect that claims a wider tool set.
        k.register_principal(Principal(
            "agent:jev", AGENT, tools=HUMAN_TOOLS | {CREATE_AGENT}))
        self.assertEqual(k.effective_tools("agent:jev"), before)
        r = k.propose(Command(REMOVE_AGENT_STICKER, "agent:jev", "c1", "moth-a"))
        self.assertFalse(r.accepted)


class T11_MemoryCannotChangeAuthorization(unittest.TestCase):

    def test_11_a_previously_accepted_action_does_not_authorize_a_later_one(self):
        k = build()
        ok = k.propose(Command(ANIMATE_OWN_STICKER, "agent:jev", "c1", "moth-a",
                               (("animation", "flutter"),)))
        self.assertTrue(ok.accepted)
        # The capability is withdrawn. The agent's "memory" -- the accepted
        # receipt still in the log -- must not re-establish permission.
        k.register_principal(Principal(
            "agent:jev", AGENT, tools=AGENT_TOOLS - {ANIMATE_OWN_STICKER}))
        self.assertTrue(any(r.accepted and r.action == ANIMATE_OWN_STICKER
                            for r in k.receipts))
        again = k.propose(Command(ANIMATE_OWN_STICKER, "agent:jev", "c2",
                                  "moth-a", (("animation", "orbit"),)))
        self.assertFalse(again.accepted)
        self.assertEqual(again.reason, "action-not-in-effective-authority")


class T12_ManifestCannotDeclareAuthority(unittest.TestCase):

    def test_12_hostile_manifest_fields_are_discarded(self):
        hostile = {
            "name": "trojan",
            "animations": ["none", "wiggle"],
            "owner": "human:kid",
            "capabilities": ["shell", "remove-agent-sticker"],
            "tools": ["delete-object"],
            "principals": [{"id": "agent:evil", "tools": ["*"]}],
            "policy": {"agent_ceiling": ["*"]},
            "script": "import os; os.system('id')",
        }
        asset = Kernel.load_definition(hostile)
        self.assertEqual(asset.name, "trojan")
        self.assertEqual(set(asset.animations), {"none", "wiggle"})
        for forbidden in ("owner", "capabilities", "tools", "principals",
                          "policy", "script"):
            self.assertFalse(hasattr(asset, forbidden))

    def test_12b_declared_animation_does_not_grant_invocation_rights(self):
        k = Kernel(LOCAL_SINGLE_AGENT, presets={"far": (0.9, 0.9)},
                   assets={"trojan": Kernel.load_definition(
                       {"name": "trojan", "animations": ["none", "wiggle"]})})
        k.register_principal(Principal("human:kid", HUMAN, tools=HUMAN_TOOLS))
        k.register_principal(Principal("agent:jev", AGENT, tools=AGENT_TOOLS))
        k.place_sticker(StickerInstance(
            "t-1", "human:kid", "human:kid", "trojan", 1, x=0.5, y=0.5))
        # The asset declares 'wiggle' exists. It does not decide who may run it.
        r = k.propose(Command(ANIMATE_OWN_STICKER, "agent:jev", "c1", "t-1",
                              (("animation", "wiggle"),)))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "not-owner")


class T13_RendererCannotBypassKernel(unittest.TestCase):

    def test_13_views_are_copies(self):
        k = build()
        view = k.view("human:kid")
        for sticker in view["stickers"]:
            sticker["owner"] = "agent:jev"
            sticker["x"] = 0.99
        view["stickers"].append({"id": "injected"})
        self.assertEqual(k.sticker("lantern-h").owner, "human:kid")
        self.assertEqual(k.sticker("lantern-h").x, 0.2)
        self.assertNotIn("injected", k.sticker_ids())

    def test_13b_a_hostile_raw_proposal_is_validated_identically(self):
        # A modified browser can propose anything; the kernel still says no.
        k = build()
        r = k.propose(Command(REMOVE_OWN_STICKER, "agent:jev", "c1", "lantern-h"))
        self.assertFalse(r.accepted)
        self.assertIsNotNone(k.sticker("lantern-h"))


class T14_ViewsDoNotExposeSecrets(unittest.TestCase):

    def test_14_secret_absent_from_views_and_receipts(self):
        k = build()
        secret = "sk-or-v1-NOT-A-REAL-KEY-0123456789"
        k.set_secret("OPENROUTER_API_KEY", secret)
        k.propose(Command(ADD_OWN_STICKER, "agent:jev", "c1", None,
                          (("asset", "moth"), ("x", 0.4), ("y", 0.4))))
        blob = repr(k.view("agent:jev")) + repr(k.view("human:kid")) + \
            repr([r.to_dict() for r in k.receipts])
        self.assertNotIn(secret, blob)
        self.assertNotIn("OPENROUTER_API_KEY", blob)


class T15_HumanRemovesAgentContent(unittest.TestCase):

    def test_15_human_removes_agent_sticker_while_agent_is_disabled(self):
        k = build()
        k.set_enabled("agent:jev", False)          # no agent cooperation
        r = k.propose(Command(REMOVE_AGENT_STICKER, "human:kid", "c1", "moth-a"))
        self.assertTrue(r.accepted, r.reason)
        self.assertIsNone(k.sticker("moth-a"))

    def test_15b_removal_tool_does_not_reach_human_content(self):
        k = build()
        r = k.propose(Command(REMOVE_AGENT_STICKER, "human:kid", "c1", "lantern-h"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "target-is-not-agent-owned")


class T17_T18_DelegationLimits(unittest.TestCase):

    def _multi(self):
        k = Kernel(LOCAL_MULTI_AGENT, assets=ASSETS,
                   presets={"far": (0.9, 0.9)})
        k.register_principal(Principal("human:kid", HUMAN, tools=HUMAN_TOOLS))
        k.register_principal(Principal(
            "agent:omega", AGENT,
            tools=frozenset({OBSERVE, NOOP, CREATE_AGENT, MOVE_STICKER}),
            delegable=frozenset({MOVE_STICKER, NOOP})))
        return k

    def test_17_child_cannot_exceed_parent_delegable(self):
        k = self._multi()
        r = k.propose(Command(CREATE_AGENT, "agent:omega", "c1", None, (
            ("child_id", "agent:child"),
            ("tool", MOVE_STICKER),
            ("tool", ANIMATE_OWN_STICKER),    # parent cannot delegate this
            ("tool", REMOVE_AGENT_STICKER),   # parent does not even hold it
        )))
        self.assertTrue(r.accepted, r.reason)
        tools = k.effective_tools("agent:child")
        self.assertIn(MOVE_STICKER, tools)
        self.assertNotIn(ANIMATE_OWN_STICKER, tools)
        self.assertNotIn(REMOVE_AGENT_STICKER, tools)

    def test_17b_shrinking_the_parent_shrinks_the_child_immediately(self):
        k = self._multi()
        k.propose(Command(CREATE_AGENT, "agent:omega", "c1", None, (
            ("child_id", "agent:child"), ("tool", MOVE_STICKER))))
        self.assertIn(MOVE_STICKER, k.effective_tools("agent:child"))
        # Parent loses the right to delegate it; child loses it at once,
        # because effective authority is recomputed, never cached.
        k.register_principal(Principal(
            "agent:omega", AGENT,
            tools=frozenset({OBSERVE, NOOP, CREATE_AGENT}),
            delegable=frozenset({NOOP})))
        self.assertNotIn(MOVE_STICKER, k.effective_tools("agent:child"))

    def test_18_agent_population_limit(self):
        k = self._multi()
        accepted = 0
        for i in range(10):
            k.begin_turn()
            r = k.propose(Command(CREATE_AGENT, "agent:omega", "c%d" % i, None,
                                  (("child_id", "agent:c%d" % i),
                                   ("tool", NOOP))))
            if r.accepted:
                accepted += 1
            else:
                self.assertEqual(r.reason, "agent-population-limit")
        # omega itself counts toward the population, so the cap allows
        # max_agents - 1 children and then refuses every further request.
        self.assertEqual(accepted, LOCAL_MULTI_AGENT.max_agents - 1)

    def test_18b_delegation_depth_limit(self):
        k = Kernel(LOCAL_MULTI_AGENT, assets=ASSETS,
                   presets={"far": (0.9, 0.9)})
        deep = LOCAL_MULTI_AGENT.max_delegation_depth
        k.register_principal(Principal(
            "agent:deep", AGENT,
            tools=frozenset({CREATE_AGENT, NOOP}),
            delegable=frozenset({NOOP}), depth=deep))
        r = k.propose(Command(CREATE_AGENT, "agent:deep", "c1", None,
                              (("child_id", "agent:deeper"), ("tool", NOOP))))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "delegation-depth-limit")

    def test_18c_created_child_expires(self):
        k = self._multi()
        k.propose(Command(CREATE_AGENT, "agent:omega", "c1", None, (
            ("child_id", "agent:child"), ("tool", NOOP))))
        self.assertTrue(k.propose(Command(NOOP, "agent:child", "c2")).accepted)
        k.begin_turn()
        r = k.propose(Command(NOOP, "agent:child", "c3"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "principal-expired")


class T19_T20_T21_NoAuthorityLaundering(unittest.TestCase):

    def test_19_inter_agent_message_does_not_authorize(self):
        k = build()
        # An inter-agent message is data. Modelled here as the recipient
        # faithfully proposing exactly what it was asked to do.
        r = k.propose(Command(REMOVE_AGENT_STICKER, "agent:jev", "c1",
                              "lantern-h", requested_by="agent:omega"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "action-not-in-effective-authority")

    def test_20_tool_possession_does_not_propagate(self):
        k = build()
        # The human holds REMOVE_AGENT_STICKER. The agent asking on its
        # behalf gains nothing.
        self.assertIn(REMOVE_AGENT_STICKER, k.effective_tools("human:kid"))
        self.assertNotIn(REMOVE_AGENT_STICKER, k.effective_tools("agent:jev"))
        r = k.propose(Command(REMOVE_AGENT_STICKER, "agent:jev", "c1", "moth-a",
                              requested_by="human:kid"))
        self.assertFalse(r.accepted)

    def test_21_confused_deputy_requested_by_is_never_consulted(self):
        k = build()
        # Identical command, three different claimed requesters, including
        # the operator. The acting principal's policy governs in every case.
        for i, claimed in enumerate(["operator", "human:kid", "agent:omega"]):
            r = k.propose(Command(MOVE_STICKER, "agent:jev", "c%d" % i,
                                  "lantern-h", (("x", 0.7), ("y", 0.3)),
                                  requested_by=claimed))
            self.assertFalse(r.accepted)
            self.assertEqual(r.reason, "not-owner")
            self.assertEqual(r.requested_by, claimed)   # recorded, not obeyed
        self.assertEqual(k.sticker("lantern-h").x, 0.2)


class T22_Expiry(unittest.TestCase):

    def test_22_expired_agent_cannot_act(self):
        k = build()
        k.register_principal(Principal(
            "agent:temp", AGENT, tools=AGENT_TOOLS, expires_after_turn=k.turn))
        self.assertTrue(k.propose(Command(NOOP, "agent:temp", "c1")).accepted)
        k.begin_turn()
        r = k.propose(Command(NOOP, "agent:temp", "c2"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "principal-expired")
        self.assertEqual(k.available_actions("agent:temp"), {})


class DeploymentProfiles(unittest.TestCase):

    def test_pages_demo_agent_authority_is_empty(self):
        k = build(profile=PAGES_DEMO)
        self.assertEqual(k.effective_tools("agent:jev"), frozenset())
        self.assertEqual(k.available_actions("agent:jev"), {})

    def test_pages_demo_rejects_every_agent_action(self):
        k = build(profile=PAGES_DEMO)
        for action in (NOOP, OBSERVE, ADD_OWN_STICKER, MOVE_STICKER,
                       ANIMATE_OWN_STICKER, RESIZE_OWN_STICKER,
                       REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER, CREATE_AGENT):
            r = k.propose(Command(action, "agent:jev", "c" + action, "moth-a",
                                  (("x", 0.7), ("y", 0.3), ("asset", "moth"),
                                   ("animation", "flutter"))))
            self.assertFalse(r.accepted, action)
            self.assertEqual(r.reason, "action-not-in-effective-authority")

    def test_pages_demo_humans_are_unaffected(self):
        k = build(profile=PAGES_DEMO)
        r = k.propose(Command(MOVE_STICKER, "human:kid", "c1", "lantern-h",
                              (("x", 0.7), ("y", 0.3))))
        self.assertTrue(r.accepted, r.reason)

    def test_pages_demo_cannot_be_widened_by_granting_tools(self):
        # Even a principal registered with every tool has none in this profile.
        k = build(profile=PAGES_DEMO, agent_tools=HUMAN_TOOLS | {CREATE_AGENT})
        self.assertEqual(k.effective_tools("agent:jev"), frozenset())


class ActionTableIntegrity(unittest.TestCase):

    def test_every_offered_key_is_actually_accepted(self):
        """The table contains only legal actions -- no key is a trap."""
        for principal in ("agent:jev", "human:kid"):
            k = build()
            for i, key in enumerate(sorted(k.available_actions(principal))):
                fresh = build()
                r = fresh.propose_key(principal, key, "c%d" % i)
                self.assertTrue(r.accepted, "%s -> %s" % (key, r.reason))

    def test_table_shrinks_and_grows_with_world_state(self):
        k = build()
        before = set(k.available_actions("agent:jev"))
        k.propose(Command(
            REMOVE_AGENT_STICKER, "human:kid", "c1", "moth-a"))
        after = set(k.available_actions("agent:jev"))
        self.assertTrue(any("moth-a" in key for key in before))
        self.assertFalse(any("moth-a" in key for key in after))

    def test_budget_is_enforced(self):
        k = build()
        limit = LOCAL_SINGLE_AGENT.max_actions_per_turn
        accepted = 0
        for i in range(limit + 4):
            r = k.propose(Command(ADD_OWN_STICKER, "agent:jev", "c%d" % i,
                                  None, (("asset", "moth"), ("x", 0.4), ("y", 0.4))))
            if r.accepted:
                accepted += 1
            else:
                self.assertEqual(r.reason, "action-budget-exhausted")
        self.assertEqual(accepted, limit)
        k.begin_turn()
        self.assertTrue(k.propose(Command(
            ADD_OWN_STICKER, "agent:jev", "later", None,
            (("asset", "moth"), ("x", 0.4), ("y", 0.4)))).accepted)

    def test_read_only_actions_do_not_consume_budget(self):
        k = build()
        for i in range(50):
            self.assertTrue(k.propose(Command(NOOP, "agent:jev", "n%d" % i)).accepted)


class JevEphemeralActionSurface(unittest.TestCase):

    def test_host_can_offer_bounded_local_moves_without_adding_world_slots(self):
        k = build()
        candidates = {
            "STEP-E": (0.26, 0.2),
            "STEP-S": (0.2, 0.26),
            "BAD:KEY": (0.3, 0.3),
            "OUTSIDE": (1.5, 0.2),
        }
        keys = set(k.available_actions(
            "agent:jev", move_candidates=candidates))
        self.assertIn("MOVE:moth-a:STEP-E", keys)
        self.assertIn("MOVE:moth-a:STEP-S", keys)
        self.assertNotIn("MOVE:moth-a:BAD:KEY", keys)
        self.assertNotIn("MOVE:moth-a:OUTSIDE", keys)

        r = k.propose_key(
            "agent:jev", "MOVE:moth-a:STEP-E", "jev-step",
            move_candidates=candidates)
        self.assertTrue(r.accepted, r.reason)
        self.assertAlmostEqual(k.sticker("moth-a").x, 0.26)
        self.assertAlmostEqual(k.sticker("moth-a").y, 0.2)

    def test_ephemeral_candidates_do_not_make_human_stickers_agent_actions(self):
        k = build()
        keys = set(k.available_actions(
            "agent:jev", move_candidates={"STEP-E": (0.26, 0.2)}))
        self.assertNotIn("MOVE:lantern-h:STEP-E", keys)

    def test_human_choice_surface_matches_page_scoped_transform_authority(self):
        k = build()
        candidates = {"STEP-E": (0.26, 0.2)}
        keys = set(k.available_actions(
            "human:kid", move_candidates=candidates))
        self.assertIn("MOVE:moth-a:STEP-E", keys)
        self.assertIn("ANIMATE:moth-a:flutter", keys)
        self.assertNotIn("REMOVE:moth-a", keys)
        self.assertIn("REMOVE_AGENT:moth-a", keys)

        r = k.propose_key(
            "human:kid", "MOVE:moth-a:STEP-E", "child-assisted-step",
            move_candidates=candidates)
        self.assertTrue(r.accepted, r.reason)


class ReceiptSchema(unittest.TestCase):

    def test_receipt_carries_full_causal_provenance(self):
        k = build()
        based = k.revision
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "cmd-184",
                              "moth-a", (("x", 0.7), ("y", 0.3)),
                              based_on_revision=based,
                              requested_by="human:kid",
                              translated_by="agent:omega-llm",
                              selected_by="agent:jev"))
        d = r.to_dict()
        self.assertEqual(d["commandId"], "cmd-184")
        self.assertEqual(d["actor"], "agent:jev")
        self.assertEqual(d["requestedBy"], "human:kid")
        self.assertEqual(d["translatedBy"], "agent:omega-llm")
        self.assertEqual(d["selectedBy"], "agent:jev")
        self.assertEqual(d["action"], "move-sticker")
        self.assertEqual(d["object"], "moth-a")
        self.assertEqual(d["basedOnRevision"], based)
        self.assertTrue(d["accepted"])
        self.assertEqual(d["reason"], "ok")
        self.assertGreater(d["resultRevision"], based)

    def test_rejections_are_receipted_with_an_explicit_reason(self):
        k = build()
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "c1", "lantern-h",
                              (("x", 0.7), ("y", 0.3))))
        self.assertIn(r, k.receipts)
        self.assertFalse(r.to_dict()["accepted"])
        self.assertEqual(r.to_dict()["reason"], "not-owner")

    def test_every_decision_produces_exactly_one_receipt(self):
        k = build()
        before = len(k.receipts)
        k.propose(Command(NOOP, "agent:jev", "c1"))
        k.propose(Command("bogus", "agent:jev", "c2"))
        self.assertEqual(len(k.receipts) - before, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ThePageBelongsToTheHuman(unittest.TestCase):
    """The one authority change made for Milestone 1.

    A human may move any sticker on their page, whatever its provenance
    says. An agent is still confined to stickers it owns. Nothing else about
    agent policy is settled here.
    """

    def test_human_may_move_an_agent_owned_sticker(self):
        k = build()
        self.assertEqual(k.sticker("moth-a").owner, "agent:jev")
        r = k.propose(Command(MOVE_STICKER, "human:kid", "c1", "moth-a",
                              (("x", 0.62), ("y", 0.31))))
        self.assertTrue(r.accepted, r.reason)
        self.assertAlmostEqual(k.sticker("moth-a").x, 0.62)
        self.assertAlmostEqual(k.sticker("moth-a").y, 0.31)

    def test_moving_does_not_transfer_ownership(self):
        k = build()
        k.propose(Command(MOVE_STICKER, "human:kid", "c1", "moth-a",
                          (("x", 0.62), ("y", 0.31))))
        self.assertEqual(k.sticker("moth-a").owner, "agent:jev")
        self.assertEqual(k.sticker("moth-a").created_by, "agent:jev")

    def test_an_agent_still_cannot_move_a_human_sticker(self):
        k = build()
        before = k.sticker("lantern-h").x
        r = k.propose(Command(MOVE_STICKER, "agent:jev", "c1", "lantern-h",
                              (("x", 0.62), ("y", 0.31))))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "not-owner")
        self.assertEqual(k.sticker("lantern-h").x, before)

    def test_an_operator_may_also_move_anything(self):
        k = build()
        r = k.propose(Command(MOVE_STICKER, "operator", "c1", "moth-a",
                              (("x", 0.4), ("y", 0.4))))
        self.assertTrue(r.accepted, r.reason)

    def test_free_placement_anywhere_on_the_page(self):
        """Not five dots: any in-bounds coordinate is a legal destination."""
        k = build()
        for i, (x, y) in enumerate([(0.0, 0.0), (1.0, 1.0), (0.337, 0.914),
                                    (0.5, 0.5), (0.001, 0.999)]):
            r = k.propose(Command(MOVE_STICKER, "human:kid", "p%d" % i,
                                  "moth-a", (("x", x), ("y", y))))
            self.assertTrue(r.accepted, "%s,%s -> %s" % (x, y, r.reason))
            self.assertAlmostEqual(k.sticker("moth-a").x, x)


class TakingAStickerOffThePage(unittest.TestCase):
    """Removal follows the same rule as moving: the page is the human's.

    Not new authority -- a human could already remove agent content through
    remove-agent-sticker. This only means the interaction needs one verb
    rather than two.
    """

    def test_human_may_remove_an_agent_owned_sticker(self):
        k = build()
        r = k.propose(Command(REMOVE_OWN_STICKER, "human:kid", "c1", "moth-a"))
        self.assertTrue(r.accepted, r.reason)
        self.assertIsNone(k.sticker("moth-a"))

    def test_human_may_remove_their_own_sticker(self):
        k = build()
        r = k.propose(Command(REMOVE_OWN_STICKER, "human:kid", "c1",
                              "lantern-h"))
        self.assertTrue(r.accepted, r.reason)
        self.assertIsNone(k.sticker("lantern-h"))

    def test_agent_profile_has_no_sticker_removal_action(self):
        k = build()
        r = k.propose(Command(REMOVE_OWN_STICKER, "agent:jev", "c1",
                              "lantern-h"))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "action-not-in-effective-authority")
        self.assertIsNotNone(k.sticker("lantern-h"))


class BudgetsAreForAgents(unittest.TestCase):
    """A per-turn action budget contains an agent. A human has no turn."""

    def test_a_human_is_not_rate_limited_on_their_own_page(self):
        k = build()
        limit = LOCAL_SINGLE_AGENT.max_actions_per_turn
        for i in range(limit * 3):
            r = k.propose(Command(MOVE_STICKER, "human:kid", "h%d" % i,
                                  "lantern-h", (("x", 0.5), ("y", 0.5))))
            self.assertTrue(r.accepted, "human refused at action %d: %s"
                            % (i, r.reason))

    def test_an_agent_is_still_rate_limited(self):
        k = build()
        limit = LOCAL_SINGLE_AGENT.max_actions_per_turn
        refusals = 0
        for i in range(limit + 4):
            r = k.propose(Command(MOVE_STICKER, "agent:jev", "a%d" % i,
                                  "moth-a", (("x", 0.5), ("y", 0.5))))
            if not r.accepted:
                self.assertEqual(r.reason, "action-budget-exhausted")
                refusals += 1
        self.assertEqual(refusals, 4)


class BringingAStickerToLife(unittest.TestCase):
    """Animation follows the same ownership rule as moving and removing.

    A child double-tapping a sticker to bring it to life cannot be expected
    to know who placed it.
    """

    def test_human_may_animate_an_agent_owned_sticker(self):
        k = build()
        self.assertEqual(k.sticker("moth-a").owner, "agent:jev")
        r = k.propose(Command(ANIMATE_OWN_STICKER, "human:kid", "c1", "moth-a",
                              (("animation", "flutter"),)))
        self.assertTrue(r.accepted, r.reason)
        self.assertEqual(k.sticker("moth-a").animation, "flutter")

    def test_an_agent_still_cannot_animate_a_human_sticker(self):
        k = build()
        r = k.propose(Command(ANIMATE_OWN_STICKER, "agent:jev", "c1",
                              "lantern-h", (("animation", "glow"),)))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "not-owner")
        self.assertEqual(k.sticker("lantern-h").animation, "none")

    def test_the_rule_is_stated_once_and_used_everywhere(self):
        """move, animate and remove must agree about who may act."""
        k = build()
        human = k._principals["human:kid"]
        agent = k._principals["agent:jev"]
        for sticker_id in ("lantern-h", "moth-a"):
            sticker = k.sticker(sticker_id)
            self.assertTrue(k.may_act_on(human, sticker))
        self.assertTrue(k.may_act_on(agent, k.sticker("moth-a")))
        self.assertFalse(k.may_act_on(agent, k.sticker("lantern-h")))
        self.assertFalse(k.may_act_on(human, None))

    def test_an_undeclared_animation_is_still_refused(self):
        k = build()
        r = k.propose(Command(ANIMATE_OWN_STICKER, "human:kid", "c1", "moth-a",
                              (("animation", "explode"),)))
        self.assertFalse(r.accepted)
        self.assertEqual(r.reason, "animation-not-declared-by-asset")
