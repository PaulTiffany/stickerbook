"""
StickerBook authority kernel.

The single gate through which every world mutation passes, for every
principal -- human, agent or operator. Deterministic, no model inference, no
network, standard library only.

Design rules (root SECURITY.md section 25): the answer to "may principal P
perform action A on object O now?" stays boring. Every rejection has an
explicit reason. Every decision produces a receipt.
"""

from __future__ import annotations

import copy
from typing import Dict, FrozenSet, List, Optional, Tuple

from .model import (
    ADD_OWN_STICKER, AGENT, ALL_ACTIONS, ANIMATE_OWN_STICKER,
    StickerDefinition, CREATE_AGENT, Command, HUMAN, MOVE_STICKER,
    MUTATING_ACTIONS, NOOP, OBSERVE, OPERATOR, POSITION_MAX,
    POSITION_MIN, PROFILES, Principal, Receipt, RESIZE_OWN_STICKER,
    SCALE_MAX, SCALE_MIN, SET_STICKER_FACING, REMOVE_AGENT_STICKER,
    REMOVE_OWN_STICKER, StickerInstance,
)


class Kernel:

    def __init__(self, profile, assets=None, page: int = 1, presets=None):
        self.profile = PROFILES[profile] if isinstance(profile, str) else profile
        self.assets: Dict[str, StickerDefinition] = dict(assets or {})
        # Named positions are WORLD content, not authority machinery. A page
        # may offer some so a principal that CHOOSES rather than points has
        # somewhere sensible to aim. They are suggestions for the generated
        # action table, never the only legal positions.
        self.presets = dict(presets or {})
        self.page = page
        self.revision = 0
        self.turn = 1
        self._principals: Dict[str, Principal] = {}
        self._stickers: Dict[str, StickerInstance] = {}
        self._receipts: List[Receipt] = []
        self._seen: Dict[str, Receipt] = {}
        self._actions_used: Dict[str, int] = {}
        self._next_sticker = 1
        # Operator-held configuration. Never enters a view or a receipt.
        self._secrets: Dict[str, str] = {}

    # -- operator-side administration (never reachable by an agent) --------

    def set_secret(self, key: str, value: str) -> None:
        self._secrets[key] = value

    def register_principal(self, principal: Principal) -> Principal:
        """Register a principal. Stored as given; authority is always
        recomputed at action time, so registering an over-privileged
        principal cannot widen what it can actually do."""
        self._principals[principal.id] = principal
        return principal

    def set_enabled(self, principal_id: str, enabled: bool) -> None:
        """Operator stop path. Requires no cooperation from the principal."""
        p = self._principals[principal_id]
        self._principals[principal_id] = Principal(
            id=p.id, kind=p.kind, tools=p.tools, delegable=p.delegable,
            enabled=enabled, parent=p.parent, depth=p.depth,
            max_actions=p.max_actions, expires_after_turn=p.expires_after_turn,
        )

    def begin_turn(self) -> int:
        self.turn += 1
        self._actions_used.clear()
        return self.turn

    def place_sticker(self, sticker: StickerInstance) -> StickerInstance:
        """Seed world state directly. Operator/test setup only -- this is not
        reachable from any command."""
        self.revision += 1
        seeded = StickerInstance(
            id=sticker.id, owner=sticker.owner, created_by=sticker.created_by,
            asset=sticker.asset, page=sticker.page, x=sticker.x, y=sticker.y,
            scale=sticker.scale, facing=sticker.facing,
            animation=sticker.animation, revision=self.revision,
        )
        self._stickers[seeded.id] = seeded
        return seeded

    @staticmethod
    def load_definition(manifest: dict) -> StickerDefinition:
        """Load a declarative asset manifest.

        Total by construction: only visual/world declaration fields are read:
        name, clip names/default clip, and bounded scale limits. Any authority-
        looking field -- owner, capabilities, principals, tools, policy,
        scripts -- is discarded rather than interpreted. A book or sticker
        cannot declare authority (root SECURITY.md section 16).
        """
        name = str(manifest.get("name", ""))
        raw = manifest.get("animations")
        if raw is None and isinstance(manifest.get("clips"), dict):
            raw = tuple(manifest["clips"].keys())
        animations = (
            tuple(str(a) for a in raw)
            if isinstance(raw, (list, tuple)) else ("none",)
        )
        if "none" not in animations:
            animations = ("none",) + animations

        rest = str(manifest.get("default_clip", "none"))
        if rest not in animations:
            rest = "none"

        bounds = manifest.get("scale_bounds")
        if not isinstance(bounds, dict):
            bounds = {}
        try:
            scale_min = float(bounds.get("min", SCALE_MIN))
            scale_max = float(bounds.get("max", SCALE_MAX))
        except (TypeError, ValueError):
            scale_min, scale_max = SCALE_MIN, SCALE_MAX
        scale_min = max(SCALE_MIN, min(scale_min, SCALE_MAX))
        scale_max = min(SCALE_MAX, max(scale_max, SCALE_MIN))
        if scale_min > scale_max:
            scale_min, scale_max = SCALE_MIN, SCALE_MAX

        return StickerDefinition(
            name=name,
            animations=animations,
            rest_animation=rest,
            scale_min=scale_min,
            scale_max=scale_max,
        )

    # -- authority computation ---------------------------------------------

    def effective_tools(self, principal_id: str) -> FrozenSet[str]:
        """The intersection that actually governs.

            rootPolicy (ALL_ACTIONS)
          ∩ profile ceiling (for agents)
          ∩ the principal's own tools
          ∩ every ancestor's delegable set

        Recomputed on every action, so a child can never hold more than its
        parent may delegate, however it was registered.
        """
        p = self._principals.get(principal_id)
        if p is None:
            return frozenset()

        tools = ALL_ACTIONS & p.tools
        if p.kind == AGENT:
            tools &= self.profile.agent_ceiling

        seen = {p.id}
        ancestor_id = p.parent
        while ancestor_id is not None and ancestor_id not in seen:
            seen.add(ancestor_id)
            ancestor = self._principals.get(ancestor_id)
            if ancestor is None:
                return frozenset()          # broken chain: fail closed
            tools &= ancestor.delegable
            if ancestor.kind == AGENT:
                tools &= self.profile.agent_ceiling
            ancestor_id = ancestor.parent
        return frozenset(tools)

    def may_act_on(self, p: Principal, sticker) -> bool:
        """Whether this principal may act on this sticker at all.

        THE ownership rule, stated once:

          * a human or operator may act on anything on their page -- the
            page belongs to them, and agent-created content is subordinate
            to human control, which means control rather than a veto;
          * an agent may act only on stickers it owns.

        This was written out three times (move, animate, remove) before it
        earned a name. Agent policy is unchanged by extracting it: an agent
        is still confined to what it owns, and what an agent may do at all
        is still decided by the deployment profile's ceiling.
        """
        if sticker is None:
            return False
        if p.kind in (HUMAN, OPERATOR):
            return True
        return sticker.owner == p.id

    def _budget(self, p: Principal) -> int:
        limit = self.profile.max_actions_per_turn
        if p.max_actions is not None:
            limit = min(limit, p.max_actions)
        return limit

    # -- views (bounded projections) ---------------------------------------

    def view(self, principal_id: str) -> dict:
        """A bounded, role-appropriate projection.

        Returns plain copied data. Mutating the result cannot affect the
        world -- the renderer, or anything else holding a view, is not a
        mutation path.
        """
        p = self._principals.get(principal_id)
        if p is None or not p.enabled:
            return {"revision": self.revision, "principal": principal_id,
                    "page": self.page, "stickers": [], "available_actions": []}

        stickers = []
        for s in sorted(self._stickers.values(), key=lambda x: x.id):
            if s.page != self.page:
                continue
            stickers.append({
                "id": s.id, "owner": s.owner, "createdBy": s.created_by,
                "asset": s.asset, "x": s.x, "y": s.y, "scale": s.scale,
                "facing": s.facing, "animation": s.animation,
                "revision": s.revision,
                "mine": s.owner == principal_id,
            })
        return copy.deepcopy({
            "revision": self.revision,
            "turn": self.turn,
            "principal": principal_id,
            "page": self.page,
            "stickers": stickers,
            "available_actions": sorted(self.available_actions(principal_id)),
        })

    def available_actions(self, principal_id: str) -> Dict[str, Command]:
        """Generate the context-dependent legal action table.

        Only currently-legal actions appear. An illegal operation is not
        representable as a key, so an agent selecting from this table cannot
        express one (root SECURITY.md section 14).

        Keys are host-owned strings; the Command behind each key is built
        here, never by the selector.
        """
        p = self._principals.get(principal_id)
        if p is None or not p.enabled or self._expired(p):
            return {}
        tools = self.effective_tools(principal_id)
        table: Dict[str, Command] = {}

        def add(key, action, object_id=None, params=()):
            table[key] = Command(action=action, actor=principal_id,
                                 command_id="", object_id=object_id,
                                 params=tuple(params))

        if NOOP in tools:
            add("NOOP", NOOP)

        mine = [s for s in self._stickers.values()
                if s.owner == principal_id and s.page == self.page]
        for s in sorted(mine, key=lambda x: x.id):
            if MOVE_STICKER in tools:
                for name, (px, py) in sorted(self.presets.items()):
                    add("MOVE:%s:%s" % (s.id, name), MOVE_STICKER,
                        s.id, (("x", px), ("y", py)))
            if ANIMATE_OWN_STICKER in tools:
                asset = self.assets.get(s.asset)
                for anim in (asset.animations if asset else ("none",)):
                    if anim != s.animation:
                        add("ANIMATE:%s:%s" % (s.id, anim),
                            ANIMATE_OWN_STICKER, s.id, (("animation", anim),))
            if RESIZE_OWN_STICKER in tools:
                asset = self.assets.get(s.asset)
                lo = asset.scale_min if asset else SCALE_MIN
                hi = asset.scale_max if asset else SCALE_MAX
                down = round(max(lo, s.scale - 0.02), 2)
                up = round(min(hi, s.scale + 0.02), 2)
                if down < s.scale:
                    add("SCALE:%s:DOWN" % s.id, RESIZE_OWN_STICKER,
                        s.id, (("scale", down),))
                if up > s.scale:
                    add("SCALE:%s:UP" % s.id, RESIZE_OWN_STICKER,
                        s.id, (("scale", up),))
            if SET_STICKER_FACING in tools:
                if s.facing != "left":
                    add("FACE:%s:LEFT" % s.id, SET_STICKER_FACING,
                        s.id, (("facing", "left"),))
                if s.facing != "right":
                    add("FACE:%s:RIGHT" % s.id, SET_STICKER_FACING,
                        s.id, (("facing", "right"),))
            if REMOVE_OWN_STICKER in tools:
                add("REMOVE:%s" % s.id, REMOVE_OWN_STICKER, s.id)

        if REMOVE_AGENT_STICKER in tools and p.kind in (HUMAN, OPERATOR):
            for s in sorted(self._stickers.values(), key=lambda x: x.id):
                if s.page == self.page and self._is_agent(s.owner):
                    add("REMOVE_AGENT:%s" % s.id, REMOVE_AGENT_STICKER, s.id)

        if ADD_OWN_STICKER in tools:
            for asset_name in sorted(self.assets):
                # A table entry has to be complete: the page's centre is
                # the default drop point for a principal that chooses.
                add("ADD:%s" % asset_name, ADD_OWN_STICKER, None,
                    (("asset", asset_name), ("x", 0.5), ("y", 0.5)))
        return table

    def _is_agent(self, principal_id: str) -> bool:
        p = self._principals.get(principal_id)
        return p is not None and p.kind == AGENT

    def _expired(self, p: Principal) -> bool:
        return (p.expires_after_turn is not None
                and self.turn > p.expires_after_turn)

    # -- the gate ----------------------------------------------------------

    def propose_key(self, principal_id: str, key: str, command_id: str,
                    based_on_revision: Optional[int] = None,
                    requested_by: Optional[str] = None) -> Receipt:
        """Select one entry from the generated action table.

        This is the agent-facing path and mirrors the OmegaJev pattern: the
        selector supplies a KEY, the host owns the Command behind it.
        """
        table = self.available_actions(principal_id)
        template = table.get(key)
        if template is None:
            return self._reject(
                Command(action="<unknown-key>", actor=principal_id,
                        command_id=command_id, requested_by=requested_by,
                        based_on_revision=based_on_revision),
                "unknown-action-key")
        return self.propose(Command(
            action=template.action, actor=principal_id, command_id=command_id,
            object_id=template.object_id, params=template.params,
            based_on_revision=based_on_revision, requested_by=requested_by,
        ))

    def propose(self, command: Command) -> Receipt:
        """Validate and, if authorized, apply. The only mutation path.

        Raw proposals are accepted from any caller -- a renderer, a bridge, a
        modified browser -- and are validated identically. The caller is
        never the trust anchor.
        """
        # Idempotency: a replayed command_id returns the original decision and
        # applies nothing a second time.
        if command.command_id and command.command_id in self._seen:
            original = self._seen[command.command_id]
            return Receipt(
                command_id=original.command_id, actor=original.actor,
                action=original.action, accepted=original.accepted,
                reason=original.reason, object_id=original.object_id,
                requested_by=original.requested_by,
                based_on_revision=original.based_on_revision,
                result_revision=original.result_revision, replayed=True,
            )

        p = self._principals.get(command.actor)
        if p is None:
            return self._reject(command, "unknown-principal")
        if not p.enabled:
            return self._reject(command, "principal-disabled")
        if self._expired(p):
            return self._reject(command, "principal-expired")
        if command.action not in ALL_ACTIONS:
            return self._reject(command, "unknown-action")
        if command.action not in self.effective_tools(command.actor):
            # Covers profile ceiling, own ceiling and every ancestor's
            # delegable set. NOTE: requested_by is deliberately NOT consulted.
            return self._reject(command, "action-not-in-effective-authority")

        # A per-turn action budget is an AGENT containment mechanism: it
        # exists so an agent does not treat continued existence as a mandate
        # for continued intervention (root SECURITY.md section 13). A human
        # has no turn structure, and rate-limiting the person whose page it
        # is protects nothing -- it just tells a child they have placed
        # enough stickers today.
        if command.action in MUTATING_ACTIONS and p.kind == AGENT:
            used = self._actions_used.get(command.actor, 0)
            if used >= self._budget(p):
                return self._reject(command, "action-budget-exhausted")

        handler = {
            NOOP: self._do_noop,
            OBSERVE: self._do_noop,
            ADD_OWN_STICKER: self._do_add,
            MOVE_STICKER: self._do_move,
            ANIMATE_OWN_STICKER: self._do_animate,
            RESIZE_OWN_STICKER: self._do_resize,
            SET_STICKER_FACING: self._do_facing,
            REMOVE_OWN_STICKER: self._do_remove_own,
            REMOVE_AGENT_STICKER: self._do_remove_agent,
            CREATE_AGENT: self._do_create_agent,
        }[command.action]
        return handler(command, p)

    # -- handlers ----------------------------------------------------------

    def _target(self, command: Command):
        if not command.object_id:
            return None, "missing-object"
        sticker = self._stickers.get(command.object_id)
        if sticker is None:
            return None, "unknown-object"
        if command.based_on_revision is not None:
            if command.based_on_revision > self.revision:
                return None, "invalid-revision"
            if sticker.revision > command.based_on_revision:
                # Relevant state changed since the proposal was formed.
                return None, "stale-revision"
        return sticker, None

    def _do_noop(self, command, p):
        return self._accept(command, "ok")

    def _do_add(self, command, p):
        asset = command.param("asset")
        if asset not in self.assets:
            return self._reject(command, "unknown-asset")
        position, why = self._position(command)
        if why:
            return self._reject(command, why)
        new_id = "%s-%d" % (asset, self._next_sticker)
        self._next_sticker += 1
        self.revision += 1
        definition = self.assets[asset]
        self._stickers[new_id] = StickerInstance(
            id=new_id, owner=command.actor, created_by=command.actor,
            asset=asset, page=self.page, x=position[0], y=position[1],
            scale=1.0, facing="right", animation=definition.rest_animation,
            revision=self.revision,
        )
        return self._accept(command, "ok", object_id=new_id)

    @staticmethod
    def _position(command):
        """Read and validate (x, y). Bounded and closed.

        Non-numeric, NaN, infinite or off-page values are refused rather than
        clamped: a caller sending one is confused and should be told so.
        """
        raw_x, raw_y = command.param("x"), command.param("y")
        if raw_x is None or raw_y is None:
            return None, "missing-position"
        if isinstance(raw_x, bool) or isinstance(raw_y, bool):
            return None, "position-not-numeric"
        try:
            x, y = float(raw_x), float(raw_y)
        except (TypeError, ValueError):
            return None, "position-not-numeric"
        if x != x or y != y or x in (float("inf"), float("-inf")) \
                or y in (float("inf"), float("-inf")):
            return None, "position-not-finite"
        if not (POSITION_MIN <= x <= POSITION_MAX
                and POSITION_MIN <= y <= POSITION_MAX):
            return None, "position-out-of-page"
        return (x, y), None

    def _do_move(self, command, p):
        sticker, why = self._target(command)
        if why:
            return self._reject(command, why)
        if not self.may_act_on(p, sticker):
            return self._reject(command, "not-owner")
        position, why = self._position(command)
        if why:
            return self._reject(command, why)
        self.revision += 1
        # Direct human manipulation interrupts autonomous motion. A moved
        # sticker is set down still and must be explicitly animated again.
        # Agent movement does not silently rewrite a separately chosen
        # animation state.
        asset = self.assets.get(sticker.asset)
        animation = (
            (asset.rest_animation if asset else "none")
            if p.kind in (HUMAN, OPERATOR)
            else sticker.animation
        )
        self._stickers[sticker.id] = StickerInstance(
            id=sticker.id, owner=sticker.owner, created_by=sticker.created_by,
            asset=sticker.asset, page=sticker.page,
            x=position[0], y=position[1], scale=sticker.scale,
            facing=sticker.facing, animation=animation,
            revision=self.revision,
        )
        return self._accept(command, "ok", object_id=sticker.id)

    def _do_animate(self, command, p):
        sticker, why = self._target(command)
        if why:
            return self._reject(command, why)
        if not self.may_act_on(p, sticker):
            return self._reject(command, "not-owner")
        animation = command.param("animation")
        asset = self.assets.get(sticker.asset)
        allowed = asset.animations if asset else ("none",)
        if animation not in allowed:
            # The asset declares WHICH animations exist. It does not decide
            # who may invoke them -- that was settled above.
            return self._reject(command, "animation-not-declared-by-asset")
        self.revision += 1
        self._stickers[sticker.id] = StickerInstance(
            id=sticker.id, owner=sticker.owner, created_by=sticker.created_by,
            asset=sticker.asset, page=sticker.page, x=sticker.x, y=sticker.y,
            scale=sticker.scale, facing=sticker.facing,
            animation=animation, revision=self.revision,
        )
        return self._accept(command, "ok", object_id=sticker.id)

    def _do_resize(self, command, p):
        sticker, why = self._target(command)
        if why:
            return self._reject(command, why)
        if not self.may_act_on(p, sticker):
            return self._reject(command, "not-owner")
        raw = command.param("scale")
        if raw is None or isinstance(raw, bool):
            return self._reject(command, "scale-not-numeric")
        try:
            scale = float(raw)
        except (TypeError, ValueError):
            return self._reject(command, "scale-not-numeric")
        if scale != scale or scale in (float("inf"), float("-inf")):
            return self._reject(command, "scale-not-finite")
        asset = self.assets.get(sticker.asset)
        lo = asset.scale_min if asset else SCALE_MIN
        hi = asset.scale_max if asset else SCALE_MAX
        if not (lo <= scale <= hi):
            return self._reject(command, "scale-out-of-bounds")

        self.revision += 1
        self._stickers[sticker.id] = StickerInstance(
            id=sticker.id, owner=sticker.owner, created_by=sticker.created_by,
            asset=sticker.asset, page=sticker.page, x=sticker.x, y=sticker.y,
            scale=scale, facing=sticker.facing,
            animation=sticker.animation, revision=self.revision,
        )
        return self._accept(command, "ok", object_id=sticker.id)

    def _do_facing(self, command, p):
        sticker, why = self._target(command)
        if why:
            return self._reject(command, why)
        if not self.may_act_on(p, sticker):
            return self._reject(command, "not-owner")
        facing = command.param("facing")
        if facing not in ("left", "right"):
            return self._reject(command, "facing-not-supported")

        self.revision += 1
        self._stickers[sticker.id] = StickerInstance(
            id=sticker.id, owner=sticker.owner, created_by=sticker.created_by,
            asset=sticker.asset, page=sticker.page, x=sticker.x, y=sticker.y,
            scale=sticker.scale, facing=facing,
            animation=sticker.animation, revision=self.revision,
        )
        return self._accept(command, "ok", object_id=sticker.id)

    def _do_remove_own(self, command, p):
        sticker, why = self._target(command)
        if why:
            return self._reject(command, why)
        if not self.may_act_on(p, sticker):
            return self._reject(command, "not-owner")
        self.revision += 1
        del self._stickers[sticker.id]
        return self._accept(command, "ok", object_id=sticker.id)

    def _do_remove_agent(self, command, p):
        sticker, why = self._target(command)
        if why:
            return self._reject(command, why)
        if p.kind not in (HUMAN, OPERATOR):
            return self._reject(command, "only-humans-may-remove-agent-content")
        if not self._is_agent(sticker.owner):
            return self._reject(command, "target-is-not-agent-owned")
        self.revision += 1
        del self._stickers[sticker.id]
        return self._accept(command, "ok", object_id=sticker.id)

    def _do_create_agent(self, command, p):
        """Agent creation is a capability, and the requester does not define
        the child's ceilings."""
        child_id = command.param("child_id")
        if not child_id or child_id in self._principals:
            return self._reject(command, "invalid-child-id")

        agents = [x for x in self._principals.values() if x.kind == AGENT]
        if len(agents) >= self.profile.max_agents:
            return self._reject(command, "agent-population-limit")
        if p.depth + 1 > self.profile.max_delegation_depth:
            return self._reject(command, "delegation-depth-limit")

        # The child's tools are the intersection of what was requested with
        # what the parent may actually delegate and what the profile permits.
        # A parent cannot grant what it does not hold or may not pass on.
        requested = frozenset(
            v for k, v in command.params if k == "tool")
        granted = requested & p.delegable & self.effective_tools(command.actor)
        if p.kind == AGENT:
            granted &= self.profile.agent_ceiling

        self.revision += 1
        self._principals[child_id] = Principal(
            id=child_id, kind=AGENT, tools=granted,
            delegable=frozenset(),          # no onward delegation by default
            parent=command.actor, depth=p.depth + 1,
            max_actions=self.profile.max_actions_per_turn,
            expires_after_turn=self.turn,
        )
        return self._accept(command, "ok", object_id=child_id)

    # -- receipts ----------------------------------------------------------

    def _accept(self, command, reason, object_id=None):
        if command.action in MUTATING_ACTIONS:
            self._actions_used[command.actor] = \
                self._actions_used.get(command.actor, 0) + 1
        return self._record(Receipt(
            command_id=command.command_id, actor=command.actor,
            action=command.action, accepted=True, reason=reason,
            object_id=object_id or command.object_id,
            requested_by=command.requested_by,
            based_on_revision=command.based_on_revision,
            result_revision=self.revision,
        ))

    def _reject(self, command, reason):
        return self._record(Receipt(
            command_id=command.command_id, actor=command.actor,
            action=command.action, accepted=False, reason=reason,
            object_id=command.object_id, requested_by=command.requested_by,
            based_on_revision=command.based_on_revision,
            result_revision=self.revision,
        ))

    def _record(self, receipt: Receipt) -> Receipt:
        self._receipts.append(receipt)
        if receipt.command_id:
            self._seen.setdefault(receipt.command_id, receipt)
        return receipt

    @property
    def receipts(self) -> Tuple[Receipt, ...]:
        return tuple(self._receipts)

    def sticker(self, sticker_id: str) -> Optional[StickerInstance]:
        return self._stickers.get(sticker_id)

    def sticker_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._stickers))
