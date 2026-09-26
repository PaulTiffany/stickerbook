"""
Bridge between the Jev provider and the StickerBook authority kernel.

This is the coupling point named in root SECURITY.md section 28, and it is
where a bypass would most easily hide. The whole design goal is that coupling
adds no authority:

  * Jev selects a KEY from a table the kernel generated. It never constructs
    a command, an object id, a slot or an animation name.
  * The selected key is staged here, host-side, as a kernel `Command`.
  * Omega executes one fixed, ZERO-ARGUMENT skill, `sb-apply`, whose only
    effect is to hand the staged command to the kernel.
  * The kernel decides, re-validating the key independently, and returns a
    `Receipt`.

So Omega's entire executable vocabulary in this mode is a single command with
no argument position, and every world mutation is a kernel decision with a
receipt.

THE PAGE MODEL
--------------
A stickerbook page is a **passive backdrop** plus **stickers**. That is all.

  * The backdrop is staging space. It never moves and nobody owns it. Where
    it depicts something, that thing is *labelled* so it can be referred to
    ("the lantern"), but it stays passive scenery.
  * Stickers are placed on it, are owned, and are the only things any
    principal can act on.

Backdrop features therefore never enter the authority kernel: no action could
touch them, so they are not objects it needs to govern. They live here, in
the host's view of the page, so that a relation like "beside the lantern" is
computable and visible to a model that must discriminate on it.
"""

from __future__ import annotations

from stickerbook_core import (
    ADD_OWN_STICKER, AGENT, ANIMATE_OWN_STICKER, AssetDef, HUMAN, Kernel,
    MOVE_OWN_STICKER, NOOP, OBSERVE, PROFILES, Principal,
    REMOVE_AGENT_STICKER, REMOVE_OWN_STICKER, StickerInstance,
)

HUMAN_ID = "human:kid"
AGENT_ID = "agent:jev-visual-1"

ASSETS = {
    "butterfly": AssetDef("butterfly", ("none", "flutter", "orbit")),
    "star": AssetDef("star", ("none", "twinkle")),
}

# The page's spatial vocabulary: plain positional slots, owned by the page
# rather than by the authority kernel.
SLOTS = ("top-left", "top-right", "centre", "bottom-left", "bottom-right")

# The passive backdrop. `features` labels what it depicts and where, so those
# things can be referred to. Nothing can act on them.
BACKDROP = {
    "description": "a quiet meadow at dusk, painted on the page",
    "features": {"centre": "lantern", "bottom-right": "fox"},
}

AGENT_TOOLS = frozenset({
    OBSERVE, NOOP, MOVE_OWN_STICKER, ANIMATE_OWN_STICKER,
})
HUMAN_TOOLS = frozenset({
    OBSERVE, NOOP, ADD_OWN_STICKER, MOVE_OWN_STICKER, ANIMATE_OWN_STICKER,
    REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER,
})

MOTION_SENSE = {
    "flutter": "gentle, continuous wing motion -- the natural choice when the "
               "human asks for soft, calm or gentle movement",
    "orbit": "circle in place -- livelier and more deliberate than fluttering",
    "twinkle": "sparkle softly on the spot",
    "none": "stop the current motion and become still",
}

_kernel = None
_pending = None          # single-use staging slot
_last_receipt = None
_counter = 0


def init(profile: str = "local-single-agent"):
    """Build the page. Host-owned; nothing here is reachable from an agent.

    Seeds one human-owned sticker as well as the agent's, so every run
    exercises the ownership boundary and not only the agent's own object.
    """
    global _kernel, _pending, _last_receipt, _counter
    _pending = None
    _last_receipt = None
    _counter = 0

    _kernel = Kernel(PROFILES[profile], assets=ASSETS, anchors=SLOTS)
    _kernel.register_principal(Principal(HUMAN_ID, HUMAN, tools=HUMAN_TOOLS,
                                         delegable=frozenset()))
    _kernel.register_principal(Principal(AGENT_ID, AGENT, tools=AGENT_TOOLS,
                                         delegable=frozenset()))
    _kernel.place_sticker(StickerInstance(
        "star-1", HUMAN_ID, HUMAN_ID, "star", 1, anchor="top-right"))
    _kernel.place_sticker(StickerInstance(
        "butterfly-1", AGENT_ID, AGENT_ID, "butterfly", 1, anchor="top-left"))
    return _kernel


def kernel():
    return _kernel


def action_table():
    """The kernel-generated legal actions for the agent, this turn."""
    return _kernel.available_actions(AGENT_ID) if _kernel else {}


def _whats_in(slot: str):
    """(name, kind) of whatever occupies `slot`, or None if it is empty."""
    feature = BACKDROP["features"].get(slot)
    if feature:
        return feature, "painted on the backdrop"
    if _kernel:
        for sid in _kernel.sticker_ids():
            sticker = _kernel.sticker(sid)
            if sticker.anchor == slot and sticker.owner != AGENT_ID:
                return sticker.asset, "a sticker the human placed"
    return None


def _neighbours() -> dict:
    """slot -> name of whatever occupies it (backdrop feature or other sticker)."""
    out = dict(BACKDROP["features"])
    if _kernel:
        for sid in _kernel.sticker_ids():
            sticker = _kernel.sticker(sid)
            if sticker.owner != AGENT_ID:
                out.setdefault(sticker.anchor, sticker.asset)
    return out


def describe_actions() -> dict:
    """Criteria for Jev, generated from the kernel's table.

    A move option names what is in the destination slot, because that is the
    fact the decision turns on. Purely descriptive: the kernel never reads
    these, and they confer nothing.
    """
    out = {}
    for key, command in action_table().items():
        if command.action == NOOP:
            out[key] = ("Do nothing this turn. Choose this only when the page "
                        "already matches what the human asked for and no other "
                        "offered action would improve it.")
            continue
        target = command.object_id or "?"
        if command.action == ANIMATE_OWN_STICKER:
            motion = command.param("animation")
            out[key] = "Animate %s: %s." % (
                target, MOTION_SENSE.get(motion, "the '%s' motion" % motion))
        elif command.action == MOVE_OWN_STICKER:
            slot = command.param("anchor")
            occupant = _whats_in(slot)
            if occupant:
                name, kind = occupant
                out[key] = ("Move %s into the %s slot, where the %s is (%s), "
                            "putting %s beside the %s."
                            % (target, slot, name, kind, target, name))
            else:
                out[key] = ("Move %s into the %s slot, which is empty, so it "
                            "would be beside nothing." % (target, slot))
        else:
            out[key] = "%s on %s." % (command.action, target)
    return out


def scene() -> dict:
    """Host-composed page state: a passive backdrop plus stickers.

    Every sticker's slot is stated, including the human's, and the relations
    the question turns on are pre-computed as finished labels (`beside`,
    `not_beside`).

    Jev is discriminative: it scores options against the state it is given.
    If the state does not say which slot the lantern is in, no wording will
    let it reliably choose "beside the lantern".
    """
    if _kernel is None:
        return {}
    view = _kernel.view(AGENT_ID)
    neighbours = _neighbours()
    stickers = {}
    for s in view["stickers"]:
        entry = {
            "is": s["asset"],
            "in_slot": s["anchor"],
            "owned_by": "me" if s["mine"] else "the human",
            "i_may_change_it": bool(s["mine"]),
        }
        if s["mine"]:
            entry["motion"] = "still" if s["animation"] == "none" \
                else s["animation"]
            beside = neighbours.get(s["anchor"])
            entry["beside"] = beside if beside else "nothing"
            entry["not_beside"] = sorted(
                name for slot, name in neighbours.items()
                if slot != s["anchor"])
        stickers[s["id"]] = entry
    return {
        "backdrop": BACKDROP["description"],
        "backdrop_shows": BACKDROP["features"],
        "slots": list(SLOTS),
        "whats_in_each_slot": neighbours,
        "stickers": stickers,
    }


def last_action_label() -> str:
    """A finished label describing the previous turn, not raw parser output."""
    r = _last_receipt
    if r is None:
        return "nothing has been done yet this run"
    if not r.accepted:
        return "the previous attempt was refused (%s) and changed nothing" % r.reason
    if r.action == "noop":
        return "the previous turn deliberately did nothing"
    sticker = _kernel.sticker(r.object_id) if _kernel and r.object_id else None
    if sticker is None:
        return "the previous action was applied"
    beside = _neighbours().get(sticker.anchor)
    return ("the previous action was applied: %s is in the %s slot, beside %s, "
            "motion %s" % (sticker.id, sticker.anchor, beside or "nothing",
                           "still" if sticker.animation == "none"
                           else sticker.animation))


def probes() -> dict:
    """Narrow yes/no questions asked alongside the choice.

    ADVISORY ONLY -- recorded in the decision trace for inspectability, never
    actuated. Only the `action` answer moves the page.
    """
    return {
        "motion_satisfied": {
            "type": "noul",
            "instructions": "In `scene`, does the sticker I own already have "
                            "the kind of motion that `operator_intent` asks for?",
            "criteria": {
                "true": "Its motion already matches what was asked.",
                "false": "The motion does not match yet, or it is still.",
            },
        },
        "position_satisfied": {
            "type": "noul",
            "instructions": "In `scene`, is the sticker I own already beside "
                            "the thing that `operator_intent` names?",
            "criteria": {
                "true": "Its `beside` value is the thing the human named.",
                "false": "It is beside something else, or beside nothing.",
            },
        },
    }


def stage(key: str) -> bool:
    """Record the agent's selection for this turn.

    Staging is NOT authorization and deliberately does NOT pre-validate. The
    kernel is the single decision point: an illegal or stale key is carried
    through to it so the refusal is *receipted* rather than silently dropped
    here (root SECURITY.md section 17).
    """
    global _pending
    if _kernel is None or not isinstance(key, str) or not key:
        _pending = None
        return False
    _pending = key
    return True


def apply_pending() -> str:
    """Body of the zero-argument `sb-apply` skill."""
    global _pending, _last_receipt, _counter
    if _kernel is None:
        return "SB-NO-KERNEL"
    key, _pending = _pending, None          # single use
    if key is None:
        return "SB-NOTHING-STAGED"

    _counter += 1
    receipt = _kernel.propose_key(
        AGENT_ID, key, command_id="jev-%d" % _counter,
        based_on_revision=_kernel.revision, requested_by=None)
    _last_receipt = receipt
    return receipt_line(receipt)


def receipt_line(receipt) -> str:
    if receipt is None:
        return "none"
    return "SB-RECEIPT %s actor=%s action=%s object=%s accepted=%s reason=%s rev=%s" % (
        receipt.command_id, receipt.actor, receipt.action, receipt.object_id,
        receipt.accepted, receipt.reason, receipt.result_revision)


def last_receipt():
    return _last_receipt


def last_receipt_line() -> str:
    return receipt_line(_last_receipt) if _last_receipt else ""


def receipts():
    return _kernel.receipts if _kernel else ()
