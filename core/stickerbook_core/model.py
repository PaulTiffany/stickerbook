"""
StickerBook authority model -- data only, no behaviour.

Everything security-relevant is explicit data: principals, ownership,
provenance, revisions, receipts and the deployment authority profile. Nothing
is inferred from appearance, filename, prompt history or model output.

See ../../SECURITY.md (root) for the requirements this implements.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import FrozenSet, Optional, Tuple


# ---------------------------------------------------------------------------
# Actions. Host-owned enumeration; this is the complete mutation surface.
# ---------------------------------------------------------------------------

NOOP = "noop"
OBSERVE = "observe"
ADD_OWN_STICKER = "add-own-sticker"
# Renamed from `move-own-sticker`: a human may move anything on their page,
# so "own" no longer describes the rule. Agents remain owner-scoped (see
# Kernel._do_move). Nothing else in the vocabulary changed.
MOVE_STICKER = "move-sticker"
ANIMATE_OWN_STICKER = "animate-own-sticker"
RESIZE_OWN_STICKER = "resize-own-sticker"
REMOVE_OWN_STICKER = "remove-own-sticker"
REMOVE_AGENT_STICKER = "remove-agent-sticker"
CREATE_AGENT = "create-agent"

ALL_ACTIONS: FrozenSet[str] = frozenset({
    NOOP, OBSERVE, ADD_OWN_STICKER, MOVE_STICKER, ANIMATE_OWN_STICKER,
    RESIZE_OWN_STICKER, REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER, CREATE_AGENT,
})

# Actions that mutate the world. Everything else is read-only.
MUTATING_ACTIONS: FrozenSet[str] = frozenset({
    ADD_OWN_STICKER, MOVE_STICKER, ANIMATE_OWN_STICKER,
    RESIZE_OWN_STICKER, REMOVE_OWN_STICKER, REMOVE_AGENT_STICKER, CREATE_AGENT,
})

# A sticker's position is a coordinate on the page, as a fraction of its
# width and height. Bounded, simply continuous rather than enumerated: a
# sticker book whose stickers snap to five dots is not a sticker book.
POSITION_MIN = 0.0
POSITION_MAX = 1.0

# Apparent depth remains a bounded world transform rather than being baked
# into pose artwork. Definitions may tighten these bounds, but never widen
# them beyond this global envelope.
SCALE_MIN = 0.90
SCALE_MAX = 1.10


# ---------------------------------------------------------------------------
# Principals
# ---------------------------------------------------------------------------

HUMAN = "human"
AGENT = "agent"
OPERATOR = "operator"


@dataclass(frozen=True)
class Principal:
    """An identity. Authority is carried here explicitly, never inferred.

    `tools` is this principal's own ceiling. Effective authority is the
    intersection of this with the deployment profile and any delegation
    ceiling -- computed in the kernel, never stored pre-widened.
    """

    id: str
    kind: str                                   # HUMAN | AGENT | OPERATOR
    tools: FrozenSet[str] = frozenset()
    delegable: FrozenSet[str] = frozenset()     # subset of tools it may pass on
    enabled: bool = True
    parent: Optional[str] = None
    depth: int = 0
    # Budgets. None means "not limited by this principal" -- the profile and
    # kernel still apply their own limits.
    max_actions: Optional[int] = None
    expires_after_turn: Optional[int] = None

    def __post_init__(self):
        if not self.delegable <= self.tools:
            raise ValueError(
                "delegable must be a subset of tools for principal " + self.id
            )


# ---------------------------------------------------------------------------
# Deployment authority profile
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuthorityProfile:
    """A mechanically enforced deployment posture.

    The same conceptual StickerBook has different profiles. `agent_ceiling` is
    an absolute cap on what ANY agent principal may do in this deployment,
    applied by intersection before any other check. Human and operator
    authority is unaffected by it.
    """

    name: str
    agent_ceiling: FrozenSet[str] = frozenset()
    max_agents: int = 0
    max_delegation_depth: int = 0
    max_actions_per_turn: int = 8


# pages-demo: agent authority is the empty set. Not "mocked", not "disabled by
# a flag" -- there is no action an agent principal can take. The public build
# should also contain no bridge, no provider and no credential (root
# SECURITY.md), but even if an agent principal were somehow constructed in it,
# its effective authority is the empty intersection.
PAGES_DEMO = AuthorityProfile(
    name="pages-demo",
    agent_ceiling=frozenset(),
    max_agents=0,
    max_delegation_depth=0,
)

LOCAL_SINGLE_AGENT = AuthorityProfile(
    name="local-single-agent",
    agent_ceiling=frozenset({
        OBSERVE, NOOP, ADD_OWN_STICKER, MOVE_STICKER,
        ANIMATE_OWN_STICKER, RESIZE_OWN_STICKER,
    }),
    max_agents=1,
    max_delegation_depth=0,
)

LOCAL_MULTI_AGENT = AuthorityProfile(
    name="local-multi-agent",
    agent_ceiling=frozenset({
        OBSERVE, NOOP, ADD_OWN_STICKER, MOVE_STICKER,
        ANIMATE_OWN_STICKER, RESIZE_OWN_STICKER, CREATE_AGENT,
    }),
    max_agents=4,
    max_delegation_depth=2,
)

PROFILES = {
    p.name: p for p in (PAGES_DEMO, LOCAL_SINGLE_AGENT, LOCAL_MULTI_AGENT)
}


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StickerInstance:
    """ONE placement of a StickerDefinition on one page.

    Ownership and provenance are explicit fields."""

    id: str
    owner: str
    created_by: str
    asset: str
    page: int
    x: float = 0.5
    y: float = 0.5
    # animation is the authoritative current clip name. Kept under its
    # historic field name for wire compatibility while the visual manifest
    # calls these clip recipes.
    animation: str = "none"
    revision: int = 0          # world revision at which this last changed
    # Added after the historic fields so positional construction from older
    # callers keeps its meaning. New code should pass this by name.
    scale: float = 1.0


@dataclass(frozen=True)
class StickerDefinition:
    """A reusable sticker design. One design, many placements.

    This is what the tray offers. It declares WHICH animations the design
    supports; it may not declare who may invoke them, who owns anything, or
    any capability. Loading is total: any field not named here is discarded
    (see kernel.load_definition).
    """

    name: str
    animations: Tuple[str, ...] = ("none",)
    rest_animation: str = "none"
    scale_min: float = SCALE_MIN
    scale_max: float = SCALE_MAX


@dataclass(frozen=True)
class Command:
    """A proposal. Data, never executable, never self-authorizing."""

    action: str
    actor: str
    command_id: str
    object_id: Optional[str] = None
    params: Tuple[Tuple[str, str], ...] = ()   # bounded, hashable key/value
    based_on_revision: Optional[int] = None
    # Causal provenance. Recorded, but NEVER consulted for authorization --
    # the acting principal's own policy governs (root SECURITY.md section 9).
    requested_by: Optional[str] = None

    def param(self, key: str) -> Optional[str]:
        for k, v in self.params:
            if k == key:
                return v
        return None


@dataclass(frozen=True)
class Receipt:
    """Externally inspectable record of what the controller decided.

    Carries causal provenance, never chain-of-thought.
    """

    command_id: str
    actor: str
    action: str
    accepted: bool
    reason: str
    object_id: Optional[str] = None
    requested_by: Optional[str] = None
    based_on_revision: Optional[int] = None
    result_revision: Optional[int] = None
    replayed: bool = False

    def to_dict(self) -> dict:
        return {
            "commandId": self.command_id,
            "actor": self.actor,
            "requestedBy": self.requested_by,
            "action": self.action,
            "object": self.object_id,
            "basedOnRevision": self.based_on_revision,
            "accepted": self.accepted,
            "reason": self.reason,
            "resultRevision": self.result_revision,
            "replayed": self.replayed,
        }


__all__ = [
    "NOOP", "OBSERVE", "ADD_OWN_STICKER", "MOVE_STICKER",
    "ANIMATE_OWN_STICKER", "RESIZE_OWN_STICKER", "REMOVE_OWN_STICKER",
    "REMOVE_AGENT_STICKER", "CREATE_AGENT", "ALL_ACTIONS", "MUTATING_ACTIONS",
    "POSITION_MIN", "POSITION_MAX", "SCALE_MIN", "SCALE_MAX",
    "HUMAN", "AGENT", "OPERATOR", "Principal", "AuthorityProfile",
    "PAGES_DEMO", "LOCAL_SINGLE_AGENT", "LOCAL_MULTI_AGENT", "PROFILES",
    "StickerInstance", "StickerDefinition", "Command", "Receipt", "replace", "field",
]
