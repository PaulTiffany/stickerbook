"""
Localhost bridge between the browser and the StickerBook authority kernel.

    pointer action
        -> browser POSTs a PROPOSAL (sticker id + where the pointer was)
        -> bridge validates the shape and fixes the acting principal
        -> bridge builds the Command; the kernel validates and decides
        -> kernel returns a Receipt
        -> bridge returns receipt + authoritative state
        -> browser re-renders from that state

The browser is a proposer and a renderer. It is not the authority boundary.

What the browser is NOT trusted with, enforced here:

  * its own identity -- the acting principal is fixed by the bridge; an
    `actor` field in the request body is ignored entirely;
  * the position it claims -- the kernel checks the coordinate is on the
    page before anything moves;
  * choosing an action -- this endpoint performs exactly one kind of
    command, a move of an existing sticker;
  * being believed about success -- every response carries authoritative
    state, and the renderer draws that rather than its own proposal.

There is one kernel. This process holds it; nothing is reimplemented here.
The bridge holds no provider credential and never talks to OpenRouter directly.
An optional page-image runtime may call a separately started loopback gateway.
The server itself binds loopback only.
"""

from __future__ import annotations

import json
import os
import re
import sys
from functools import wraps
from threading import Lock, RLock
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import book  # noqa: E402
import farm  # noqa: E402
import help_content  # noqa: E402
from agent_runtime import (  # noqa: E402
    DisabledAgentRuntime, agent_runtime_from_env,
)
from jev_controller import JevController, OMEGA_LLM_ID  # noqa: E402
from jev_runtime import DisabledJevRuntime, jev_runtime_from_env  # noqa: E402
from page_assets import supported_upload  # noqa: E402
from page_image_runtime import (  # noqa: E402
    DisabledPageImageRuntime, page_image_runtime_from_env,
)
from governed_history import (  # noqa: E402
    ORIGIN_HUMAN_GESTURE, GovernedHistory,
)
import interaction  # noqa: E402
import page_path  # noqa: E402
import sticker_drag  # noqa: E402
import trajectory_execution  # noqa: E402
import trajectory_reference  # noqa: E402
from semantic_reference import PendingSemanticReference  # noqa: E402
from pattern_memory import PatternLibrary, ReplayLog  # noqa: E402
from trajectory_execution import (  # noqa: E402
    TrajectoryExecutionLog,
)
from stickerbook_core import (  # noqa: E402
    ADD_OWN_STICKER, ANIMATE_OWN_STICKER, Command, MOVE_STICKER,
    REMOVE_OWN_STICKER, RESIZE_OWN_STICKER, SET_STICKER_FACING,
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
GENERATED_PAGE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "generated_pages")

# The only principal this bridge will ever act as. Not client-selectable.
BROWSER_PRINCIPAL = farm.HUMAN_ID

CONTENT_TYPES = {".html": "text/html; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8",
                 ".json": "application/json; charset=utf-8",
                 ".svg": "image/svg+xml",
                 ".png": "image/png",
                 ".jpg": "image/jpeg",
                 ".jpeg": "image/jpeg",
                 ".webp": "image/webp"}

MAX_BODY_BYTES = 8192
MAX_PAGE_UPLOAD_BYTES = 20 * 1024 * 1024
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")
_INPUT_EVENT_RE = re.compile(r"^input-event-[1-9][0-9]{0,15}$")


def _world_locked(method):
    """Serialize bridge mutation paths and coherent world reads."""
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._world_lock:
            return method(self, *args, **kwargs)
    return locked


class Bridge:
    """Kernel-facing logic, kept free of HTTP so it can be tested directly."""

    def __init__(
            self, kernel=None, agent_runtime=None, jev_runtime=None,
            page_image_runtime=None, pattern_library=None,
            governed_history=None, replay_log=None, drag_log=None,
            trajectory_execution_log=None,
            interaction_log=None, page_path_log=None, observed_input_log=None):
        self.kernel = kernel or farm.build_world()
        self._world_lock = RLock()
        # One inspectable host-only snapshot, replaced on successful resolution.
        # No historical lookup endpoint or execution consumer.
        self.last_trajectory_reference = None
        # OmegaLLM is the conversational/linguistic loop. OmegaJev is a
        # separate discriminative control loop with its own narrow runtime.
        self.agent_runtime = agent_runtime or DisabledAgentRuntime()
        self.jev_runtime = jev_runtime or DisabledJevRuntime()
        # Host-owned movement memory. In-memory for this tranche: a pattern
        # is remembered for the life of the process and is not shared between
        # children. It is passed to the controller, never to a runtime.
        self.patterns = pattern_library or PatternLibrary()
        # What actually happened, so a child can say "remember that" and the
        # host -- not OmegaLLM -- knows what "that" was. Plus the host-side
        # audit of attempts to perform remembered behaviour.
        self.history = governed_history or GovernedHistory()
        self.replays = replay_log or ReplayLog()
        # Audit of trajectory-following attempts. No lookup route and no
        # authority; the mechanical follower is a host reference path.
        self.trajectory_executions = (
            trajectory_execution_log or TrajectoryExecutionLog())
        # Bounded record of what the child physically demonstrated by
        # dragging a sticker. Input history, kept separate from world history
        # on purpose. This is one input type, not a gesture ontology.
        self.traces = drag_log or sticker_drag.StickerDragLog()
        self.page_paths = page_path_log or page_path.PagePathLog()
        self.observed_inputs = observed_input_log or interaction.ObservedInputLog()
        # Which bounded child inputs took part in each conversational turn.
        # Facts about co-occurrence, never an interpretation of them.
        self.interactions = interaction_log or interaction.InteractionLog()
        # Host arrival sequence consumed by the previous linguistic turn.
        self._input_marker = 0
        self.pending_reference = None
        # A carry belongs to one linguistic turn even with concurrent HTTP
        # callers. Direct gestures and auxiliary observations remain separate.
        self._conversation_lock = Lock()
        self.jev_controller = JevController(
            self.kernel, self.jev_runtime, patterns=self.patterns,
            history=self.history, replays=self.replays,
            world_lock=self._world_lock,
            executions=self.trajectory_executions)
        self._jev_counter = 0
        self.page_image_runtime = (
            page_image_runtime or DisabledPageImageRuntime())
        self._inference_selection = self._default_inference_selection()

    # -- reads -------------------------------------------------------------

    def state(self) -> dict:
        """Authoritative state, as the browser's principal may observe it.

        Only the kernel read is world-locked. kernel.view() already returns a
        detached deep copy, and the capability probes below are runtime and
        network availability checks: the browser's polling endpoint must not
        hold the world lock across those.
        """
        with self._world_lock:
            view = self.kernel.view(BROWSER_PRINCIPAL)
        capabilities = self._agent_capabilities()
        chrome = farm.page_chrome()
        stickers = []
        for s in view["stickers"]:
            stickers.append({
                "id": s["id"],
                "definition": s["asset"],
                "x": s["x"],
                "y": s["y"],
                "scale": s["scale"],
                "facing": s["facing"],
                "owner": s["owner"],
                "mine": s["mine"],
                "animation": s["animation"],
                "revision": s["revision"],
            })
        return {
            "revision": view["revision"],
            "principal": BROWSER_PRINCIPAL,
            "page": {"id": book.DEFAULT_PAGE,
                     "name": book.PAGES[book.DEFAULT_PAGE]["name"]},
            "picture": chrome["picture"],
            # StickerDefinitions: reusable designs the tray offers. One
            # design, many instances.
            "definitions": [
                {
                    "id": name,
                    "animations": list(d.animations),
                    "rest_clip": d.rest_animation,
                    "scale_bounds": {
                        "min": d.scale_min,
                        "max": d.scale_max,
                    },
                }
                for name, d in sorted(farm.ASSETS.items())
            ],
            "capabilities": capabilities,
            "stickers": stickers,
        }

    def _conversation_scene(self, episode=None) -> dict:
        """Bounded OmegaLLM scene plus child-facing help.

        Responsible-adult/operator documentation is intentionally excluded.
        OmegaLLM can answer child questions about StickerBook from the same
        source the child can read in-app, without seeing operator instructions.
        """
        scene = self.state()
        if episode is not None:
            # Which bounded inputs took part in this turn. Facts only: no
            # shape labels, no raw trajectory samples, no interpretation.
            scene["interaction"] = episode.describe()
        scene["child_help"] = help_content.child_help_for_omega()
        # Bounded recent governed history, so OmegaLLM can resolve "that".
        # Declarative only: no complete action keys, so OmegaLLM can refer to
        # what happened without being able to reconstruct or author it.
        scene["recent_actions"] = self.history.describe_for_scene()
        return scene

    def _runtime_inference_options(self) -> list:
        try:
            raw = self.agent_runtime.inference_options()
        except Exception:
            raw = []
        return raw if isinstance(raw, list) else []

    def _default_inference_selection(self) -> dict:
        options = self._runtime_inference_options()
        available = {
            item.get("id"): item for item in options
            if isinstance(item, dict) and item.get("available") is True
        }
        for provider_id in ("asicloud", "openrouter"):
            item = available.get(provider_id)
            if item:
                return {
                    "provider": provider_id,
                    "model": item.get("default_model", ""),
                }
        for item in options:
            if isinstance(item, dict) and item.get("available") is True:
                return {
                    "provider": item.get("id"),
                    "model": item.get("default_model", ""),
                }
        return {"provider": "off", "model": ""}

    def inference_settings(self) -> dict:
        options = [{
            "id": "off",
            "label": "Off",
            "description": "Disable conversational OmegaLLM for this session.",
            "default_model": "",
            "model_locked": True,
            "sponsored": False,
            "available": True,
        }]
        options.extend(self._runtime_inference_options())
        return {
            "selected": dict(self._inference_selection),
            "options": options,
        }

    def set_inference(self, body: dict) -> dict:
        if not isinstance(body, dict) or set(body) != {"provider", "model"}:
            return {"ok": False, "error": "invalid-inference-selection",
                    "inference": self.inference_settings()}

        provider_id = body.get("provider")
        model = body.get("model")
        if provider_id == "off":
            self._inference_selection = {"provider": "off", "model": ""}
            return {"ok": True, "inference": self.inference_settings(),
                    "state": self.state()}

        option = next((
            item for item in self._runtime_inference_options()
            if isinstance(item, dict) and item.get("id") == provider_id
        ), None)
        if not option or option.get("available") is not True:
            return {"ok": False, "error": "inference-provider-unavailable",
                    "inference": self.inference_settings()}
        if not isinstance(model, str) or not _MODEL_RE.fullmatch(model.strip()):
            return {"ok": False, "error": "invalid-inference-model",
                    "inference": self.inference_settings()}
        model = model.strip()
        if option.get("model_locked") and model != option.get("default_model"):
            return {"ok": False, "error": "inference-model-locked",
                    "inference": self.inference_settings()}

        self._inference_selection = {"provider": provider_id, "model": model}
        return {"ok": True, "inference": self.inference_settings(),
                "state": self.state()}

    def receipts(self, limit: int = 12) -> list:
        return [r.to_dict() for r in self.kernel.receipts[-limit:]]

    def _agent_capabilities(self) -> dict:
        """Expose only small boolean feature flags to the browser."""
        try:
            raw = self.agent_runtime.capabilities()
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        try:
            page_image_creator = bool(self.page_image_runtime.available())
        except Exception:
            page_image_creator = False
        return {
            "creator_agent": bool(raw.get("creator_agent", False)),
            "conversational_agent": bool(
                raw.get("conversational_agent", False))
                and self._inference_selection.get("provider") != "off",
            "jev_controller": self.jev_controller.available(),
            "page_image_creator": page_image_creator,
        }

    @_world_locked
    def _gesture(self, command):
        """Apply one direct human gesture and note it in host history.

        A freehand drag is a real governed mutation, so it is recorded for
        audit. It carries no legal-action key, though, because an arbitrary
        coordinate has no instance-independent typed form -- so it stays
        visible to OmegaLLM without ever becoming a learned PatternStep.
        """
        receipt = self.kernel.propose(command)
        self.history.record(receipt, origin=ORIGIN_HUMAN_GESTURE)
        return receipt

    def converse(self, body: dict) -> dict:
        with self._conversation_lock:
            return self._converse(body)

    def _converse(self, body: dict) -> dict:
        """Run the OmegaLLM language loop and validate its optional goal.

        OmegaLLM never emits a kernel command.  It may return one bounded goal;
        the host validates that goal, OmegaJev selects only from host-generated
        choices, and the authority kernel still decides every mutation.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")

        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._bad_request("missing conversation text")
        text = text.strip()
        if len(text) > 2000:
            return self._bad_request("conversation text too long")

        reference = self._deictic_reference(body.get("reference"))
        if isinstance(reference, str):
            return self._bad_request(reference)

        if not self._agent_capabilities()["conversational_agent"]:
            return {"ok": False,
                    "error": "conversational-agent-unavailable",
                    "state": self.state()}

        episode = self._begin_episode(
            text=text, reference=reference,
            input_mode=body.get("input_mode"))
        pending = self.pending_reference
        scene = self._conversation_scene(episode)
        if pending is not None:
            scene["pendingReference"] = pending.describe()

        try:
            result = self.agent_runtime.converse(
                text=text,
                principal=BROWSER_PRINCIPAL,
                scene=scene,
                reference=reference,
                inference=dict(self._inference_selection))
        except Exception:
            return {"ok": False, "error": "agent-runtime-error",
                    "state": self.state()}

        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}

        if not result.get("ok"):
            error = result.get("error")
            return {"ok": False,
                    "error": error if isinstance(error, str)
                    else "agent-runtime-error",
                    "state": self.state()}

        reply = result.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}

        payload = {"ok": True, "reply": reply.strip(),
                   "interaction": episode.describe()}
        # A valid linguistic response consumes the carry even if its goal is
        # refused. All runtime/invalid-response exits above preserve it.
        self.pending_reference = None

        goal = result.get("goal")
        if goal is not None:
            if isinstance(goal, dict) and goal.get("intent") == "bind-demonstration":
                # Legacy result key also holds non-Jev semantic work such as
                # remember-pattern. Binding is validation only: no Jev call.
                payload["jev"] = self._bind_demonstration(goal, episode, pending)
            elif isinstance(goal, dict) and goal.get("intent") == "reference-trajectory":
                payload["jev"] = self._reference_trajectory(goal, episode, pending)
            elif isinstance(goal, dict) and goal.get("intent") == "perform-trajectory":
                payload["jev"] = self._perform_trajectory(goal, episode, pending)
            else:
                self._jev_counter += 1
                # Unlocked on purpose: this path can run several OmegaJev
                # inferences. The controller holds the same world lock
                # briefly around each coherent read and each kernel
                # proposal, so a child's gesture is never queued behind
                # model latency.
                payload["jev"] = self.jev_controller.run_semantic_goal(
                    goal,
                    actor=BROWSER_PRINCIPAL,
                    command_prefix="omega-jev-%d" % self._jev_counter,
                    requested_by=BROWSER_PRINCIPAL,
                    translated_by=OMEGA_LLM_ID,
                )

        payload["state"] = self.state()
        return payload

    def _bind_demonstration(self, goal: dict, episode, pending=None) -> dict:
        """Admit current evidence or the exact carry exposed to this turn."""
        if set(goal) != {"subject", "intent", "demonstration"}:
            return {"ok": False, "error": "invalid-demonstration-goal"}
        admitted, error = self._admitted_demonstration(goal, episode, pending)
        if error:
            return {"ok": False, "error": error}
        self.pending_reference = admitted
        return {"ok": True, "result": "bound", "subject": admitted.subject,
                "demonstration": admitted.demonstration, "pathRef": admitted.path_ref}

    @_world_locked
    def _admitted_demonstration(self, goal, episode, pending):
        """Select no evidence: validate the model's exact current/carry choice."""
        subject = goal["subject"]
        event_id = goal["demonstration"]
        sticker = self.kernel.sticker(subject) if isinstance(subject, str) else None
        if not isinstance(subject, str) or not subject or len(subject) > 160 \
                or sticker is None or sticker.page != self.kernel.page:
            return None, "invalid-demonstration-subject"
        if not isinstance(event_id, str) or not _INPUT_EVENT_RE.fullmatch(event_id):
            return None, "invalid-demonstration-reference"
        for signal in episode.signals:
            if signal.kind != interaction.SIGNAL_PAGE_PATH \
                    or signal.source_event != event_id:
                continue
            trace = self.page_paths.get(signal.ref)
            if trace is not None and trace.principal == episode.principal \
                    and trace.page == book.DEFAULT_PAGE:
                return PendingSemanticReference(
                    subject, event_id, signal.ref, episode.episode_id,
                    episode.principal, trace.page), None
        if pending is not None and pending.subject == subject \
                and pending.demonstration == event_id \
                and pending.principal == episode.principal == BROWSER_PRINCIPAL \
                and pending.page == book.DEFAULT_PAGE:
            # Explicit successful rebinding renews the single slot, retaining
            # its original provenance. No historical episode/trace search.
            return pending, None
        return None, "demonstration-not-in-current-episode"

    def _resolve_trajectory(self, goal, episode, pending, frames):
        """Admit the demonstration and resolve it. Returns (resolved, error).

        The single admission and resolution path shared by every trajectory
        intent. `frames` is what THIS intent accepts, so a referring intent
        and an executing one can differ on coordinate frames without there
        being a second way to admit path evidence.
        """
        if set(goal) != {"subject", "intent", "demonstration", "frame"} \
                or goal.get("frame") not in frames:
            return None, "invalid-trajectory-goal"
        admitted, error = self._admitted_demonstration(goal, episode, pending)
        if error:
            return None, error
        # Exact dereference AFTER admission, not a search of historical events.
        trace = self.page_paths.get(admitted.path_ref)
        if trace is None:
            return None, "trajectory-evidence-unavailable"
        if trace.kind != interaction.SIGNAL_PAGE_PATH \
                or trace.principal != admitted.principal or trace.page != admitted.page:
            return None, "trajectory-provenance-mismatch"
        # OmegaLLM inference ran outside this lock: a child may have moved the
        # sticker meanwhile. Read position/visibility and revision together now.
        with self._world_lock:
            view = self.kernel.view(BROWSER_PRINCIPAL)
            subject = next((s for s in view["stickers"]
                            if s["id"] == admitted.subject), None)
            if subject is None:
                return None, "invalid-demonstration-subject"
            start = trajectory_reference.Point(subject["x"], subject["y"])
            revision = view["revision"]
        resolved = trajectory_reference.resolve(
            admitted, trace, frame=goal["frame"], subject_start=start,
            resolution_scene_revision=revision)
        # The one inspectable slot. It is NOT execution state: an attempt
        # holds its own frozen reference and never reads this back.
        self.last_trajectory_reference = resolved
        return resolved, None

    def _reference_trajectory(self, goal, episode, pending):
        """Resolve coordinate semantics only. Nothing moves."""
        resolved, error = self._resolve_trajectory(
            goal, episode, pending, ("page", "subject"))
        if error:
            return {"ok": False, "error": error}
        return {"ok": True, "result": "resolved", "subject": resolved.subject,
                "demonstration": resolved.demonstration, "pathRef": resolved.path_ref,
                "frame": resolved.frame, "reference": resolved.describe()}

    def _perform_trajectory(self, goal, episode, pending):
        """Resolve, then follow the demonstrated course with OmegaJev.

        Subject frame only: a page-frame path can begin far from the subject,
        and what that should mean is still an open semantic question.
        """
        resolved, error = self._resolve_trajectory(
            goal, episode, pending, (trajectory_execution.FRAME_SUBJECT,))
        if error:
            return {"ok": False, "error": error}
        self._jev_counter += 1
        # The frozen object resolved above is handed over directly. Model
        # think-time happens inside the follower, with no world lock held.
        result = self.jev_controller.follow_trajectory_with_jev(
            resolved,
            actor=BROWSER_PRINCIPAL,
            command_prefix="omega-jev-%d" % self._jev_counter,
            requested_by=BROWSER_PRINCIPAL,
            translated_by=OMEGA_LLM_ID,
        )
        result["reference"] = resolved.describe()
        return result

    def _associate_inputs(self):
        """Newest observed inputs since the previous turn, in host order."""
        return self.observed_inputs.after(self._input_marker)

    def _begin_episode(self, *, text, reference, input_mode):
        """Record which bounded inputs took part in this conversational turn.

        This creates no kernel receipt and changes no world revision: it is a
        statement about input, not about the world.
        """
        recent = self._associate_inputs()
        signals = tuple(item.signal for item in
                        recent[-interaction.MAX_SIGNALS_PER_EPISODE:])
        episode = self.interactions.add(interaction.InteractionEpisode(
            episode_id=self.interactions.next_episode_id(),
            principal=BROWSER_PRINCIPAL,
            sequence=self.interactions.next_sequence(),
            scene_revision=self.kernel.revision,
            utterance_text=text,
            input_mode=interaction.valid_input_mode(input_mode),
            deictic=reference,
            signals=signals,
        ))
        # The child supplied this turn even if inference later fails.
        if recent:
            self._input_marker = recent[-1].sequence
        return episode

    def observe_page_path(self, body: dict) -> dict:
        """Keep an auxiliary bare-page observation; never propose a mutation."""
        if not isinstance(body, dict) or set(body) - {
                "samples", "duration_ms", "box"}:
            return {"ok": False, "pathIgnored": "malformed page-path telemetry"}
        samples, duration, error = page_path.parse_path({
            key: body[key] for key in ("samples", "duration_ms") if key in body})
        if error:
            return {"ok": False, "pathIgnored": error}
        deictic_box = None
        if "box" in body:
            reference = self._deictic_reference({
                "kind": "box", "box": body["box"]})
            if isinstance(reference, str) or not self._box_matches_path(
                    reference["box"], samples):
                return {"ok": False,
                        "pathIgnored": "page-path box does not match endpoints"}
            deictic_box = reference["box"]
        trace = self.page_paths.add(page_path.PagePathTrace(
            trace_id=self.page_paths.next_trace_id(),
            principal=BROWSER_PRINCIPAL,
            page=book.DEFAULT_PAGE,
            scene_revision_at_recording=self.kernel.revision,
            duration_ms=duration,
            samples=samples,
            observed_sample_count=len(body["samples"]),
            deictic_box=deictic_box,
        ))
        observed = self.observed_inputs.add(
            BROWSER_PRINCIPAL, interaction.InputSignal(
                kind=interaction.SIGNAL_PAGE_PATH, ref=trace.trace_id,
                duration_ms=trace.duration_ms), issue_event=True)
        return {"ok": True, "path": trace.summary(),
                "sourceEvent": observed.signal.source_event}

    def _deictic_reference(self, raw):
        """Validate one transient page-space reference for this language turn.

        This is conversational context, not kernel/world state. The bridge
        accepts only a normalized point or normalized rectangular box and
        attaches the currently governed page id itself.
        """
        if raw is None:
            return None
        if not isinstance(raw, dict):
            return "invalid deictic reference"

        kind = raw.get("kind")
        values = None
        if kind == "point":
            point = raw.get("point")
            if not isinstance(point, dict):
                return "invalid deictic point"
            values = ("x", "y"), point
        elif kind == "box":
            box = raw.get("box")
            if not isinstance(box, dict):
                return "invalid deictic box"
            values = ("x1", "y1", "x2", "y2"), box
        else:
            return "invalid deictic kind"

        names, source = values
        clean = {}
        for name in names:
            raw_value = source.get(name)
            if isinstance(raw_value, bool):
                return "invalid deictic coordinate"
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return "invalid deictic coordinate"
            if value != value or value in (float("inf"), float("-inf")):
                return "invalid deictic coordinate"
            if value < 0.0 or value > 1.0:
                return "deictic coordinate outside page"
            clean[name] = value

        if kind == "box":
            if clean["x1"] > clean["x2"] or clean["y1"] > clean["y2"]:
                return "invalid deictic box ordering"
            reference = {
                "kind": "box",
                "page": book.DEFAULT_PAGE,
                "box": clean,
            }
            source_event = raw.get("source_event")
            if self._valid_box_source(source_event, clean):
                reference["sourceEvent"] = source_event
            return reference

        return {
            "kind": "point",
            "page": book.DEFAULT_PAGE,
            "point": clean,
        }

    def _valid_box_source(self, event_id, box):
        """Check the host-issued event against its stored capture pair."""
        if not isinstance(event_id, str):
            return False
        recent = self._associate_inputs()[
            -interaction.MAX_SIGNALS_PER_EPISODE:]
        paths = [item for item in recent
                 if item.principal == BROWSER_PRINCIPAL
                 and item.signal.kind == interaction.SIGNAL_PAGE_PATH]
        if not paths or paths[-1].signal.source_event != event_id:
            return False
        trace = self.page_paths.get(paths[-1].signal.ref)
        if trace is None or trace.principal != BROWSER_PRINCIPAL \
                or trace.page != book.DEFAULT_PAGE:
            return False
        return trace.deictic_box is not None and all(
            abs(box[key] - trace.deictic_box[key]) <= 0.00015
            for key in ("x1", "y1", "x2", "y2"))

    @staticmethod
    def _box_matches_path(box, samples):
        start, end = samples[0], samples[-1]
        expected = {"x1": min(start.x, end.x),
                    "y1": min(start.y, end.y),
                    "x2": max(start.x, end.x),
                    "y2": max(start.y, end.y)}
        return all(abs(box[key] - value) <= 0.00015
                   for key, value in expected.items())

    def creator_draft(self, body: dict) -> dict:
        """Return a non-authoritative page/sticker draft description."""
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")

        kind = body.get("kind")
        prompt = body.get("prompt")
        animation_intent = body.get("animation_intent")
        schema = body.get("asset_schema_version")

        if kind not in ("page", "sticker"):
            return self._bad_request("unknown creator kind")
        if not isinstance(prompt, str) or not prompt.strip():
            return self._bad_request("missing creator prompt")
        prompt = prompt.strip()
        if len(prompt) > 500:
            return self._bad_request("creator prompt too long")

        if kind == "sticker":
            if animation_intent not in ("still", "move", "animate"):
                return self._bad_request("invalid animation intent")
            if schema != 2:
                return self._bad_request("unsupported asset schema")
        else:
            animation_intent = None
            schema = None

        if not self._agent_capabilities()["creator_agent"]:
            return {"ok": False, "error": "creator-agent-unavailable",
                    "state": self.state()}

        try:
            result = self.agent_runtime.creator_draft(
                kind=kind,
                prompt=prompt,
                animation_intent=animation_intent,
                asset_schema_version=schema,
                principal=BROWSER_PRINCIPAL,
                scene=self.state())
        except Exception:
            return {"ok": False, "error": "agent-runtime-error",
                    "state": self.state()}

        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}

        try:
            encoded = json.dumps(result)
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid-agent-response",
                    "state": self.state()}
        if len(encoded.encode("utf-8")) > 65536:
            return {"ok": False, "error": "agent-response-too-large",
                    "state": self.state()}

        if not result.get("ok") or not isinstance(result.get("draft"), dict):
            error = result.get("error")
            return {"ok": False,
                    "error": error if isinstance(error, str)
                    else "invalid-agent-response",
                    "state": self.state()}

        return {"ok": True, "draft": result["draft"], "state": self.state()}

    def page_image_draft(
            self, image_bytes: bytes, content_type: str, filename: str) -> dict:
        """Create non-authoritative horizontal + portrait page-image drafts."""
        if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
            return {"ok": False, "error": "empty-page-image",
                    "state": self.state()}
        if len(image_bytes) > MAX_PAGE_UPLOAD_BYTES:
            return {"ok": False, "error": "page-image-too-large",
                    "state": self.state()}
        if not isinstance(filename, str) or not filename:
            return {"ok": False, "error": "missing-page-image-name",
                    "state": self.state()}
        if not supported_upload(filename, content_type):
            return {"ok": False, "error": "unsupported-page-image-type",
                    "state": self.state()}

        try:
            available = self.page_image_runtime.available()
        except Exception:
            available = False
        if not available:
            return {"ok": False, "error": "page-image-creator-unavailable",
                    "state": self.state()}

        try:
            result = self.page_image_runtime.reframe_page(
                image_bytes=bytes(image_bytes),
                content_type=content_type,
                filename=filename,
            )
        except Exception:
            return {"ok": False, "error": "page-image-runtime-error",
                    "state": self.state()}

        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid-page-image-response",
                    "state": self.state()}

        if not result.get("ok") or not isinstance(result.get("draft"), dict):
            error = result.get("error")
            return {"ok": False,
                    "error": error if isinstance(error, str)
                    else "invalid-page-image-response",
                    "state": self.state()}

        try:
            encoded = json.dumps(result["draft"])
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid-page-image-response",
                    "state": self.state()}
        if len(encoded.encode("utf-8")) > 131072:
            return {"ok": False, "error": "page-image-response-too-large",
                    "state": self.state()}

        return {"ok": True, "draft": result["draft"], "state": self.state()}

    # -- the one write path ------------------------------------------------

    def propose_move(self, body: dict) -> dict:
        """Validate the request shape, then let the kernel decide.

        Shape failures are refused here without reaching the kernel; they are
        malformed HTTP, not proposals. Everything that *is* a well-formed
        proposal goes to the kernel, including ones certain to be refused, so
        the refusal is recorded as a receipt.

        The world lock brackets the before-read, the proposal and the
        after-read, because a gesture must be measured against the same world
        it mutated. It is released before the response state is projected.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")

        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        point = body.get("point")
        based_on = body.get("based_on_revision")

        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if not isinstance(point, dict):
            return self._bad_request("missing pointer position")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")

        with self._world_lock:
            # The authoritative starting position, read BEFORE anything is
            # proposed. A gesture is measured against this, never against a start
            # the browser asserted.
            before = self.kernel.sticker(sticker_id)

            # Drag telemetry is auxiliary observation, not authority. If it is
            # unusable the observation is discarded, but the child's move is still
            # adjudicated normally: failure to observe must not become failure to
            # act.
            raw_drag = body.get("drag")
            interior = duration_ms = None
            drag_error = None
            if raw_drag is not None:
                if before is None:
                    drag_error = "no such sticker"
                else:
                    interior, duration_ms, drag_error = sticker_drag.parse_drag(
                        raw_drag,
                        start=sticker_drag.Point(x=before.x, y=before.y))

            # NOTE: actor is NOT taken from the request. Whatever the browser
            # claims about who it is has no effect.
            receipt = self.kernel.propose(Command(
                action=MOVE_STICKER,
                actor=BROWSER_PRINCIPAL,
                command_id=command_id,
                object_id=sticker_id,
                params=(("x", point.get("x")), ("y", point.get("y"))),
                based_on_revision=based_on,
            ))

            # A demonstration is retained only when its terminal governed move was
            # accepted. A refused move demonstrates nothing that happened.
            trace = None
            if interior is not None and drag_error is None and receipt.accepted:
                after = self.kernel.sticker(sticker_id)
                start = sticker_drag.Point(x=before.x, y=before.y)
                # Both endpoints are bound by the host from authoritative state.
                # The browser's own first and last samples are not trusted to
                # coincide with them.
                end = sticker_drag.Point(x=after.x, y=after.y)
                trace = self.traces.add(sticker_drag.StickerDragTrace(
                    trace_id=self.traces.next_trace_id(),
                    subject_id=sticker_id,
                    asset=before.asset,
                    demonstrated_by=BROWSER_PRINCIPAL,
                    starting_revision=before.revision,
                    start=start,
                    end=end,
                    duration_ms=duration_ms,
                    samples=sticker_drag.anchor(
                        interior, start=start, end=end),
                    observed_sample_count=len(interior),
                    terminal_command_id=command_id,
                    terminal_move_accepted=True,
                ))
                self.observed_inputs.add(BROWSER_PRINCIPAL, interaction.InputSignal(
                    kind=interaction.SIGNAL_STICKER_DRAG,
                    ref=trace.trace_id, subject=trace.subject_id,
                    duration_ms=trace.duration_ms))

            self.history.record(
                receipt, origin=ORIGIN_HUMAN_GESTURE,
                gesture_trace=trace.trace_id if trace else None,
                gesture_kind=trace.kind if trace else None)

        payload = {"ok": True, "receipt": receipt.to_dict(),
                   "state": self.state()}
        if trace is not None:
            payload["drag"] = trace.summary()
        elif drag_error is not None:
            # Say so, but do not fail the move over it.
            payload["dragIgnored"] = drag_error
        return payload

    def place(self, body: dict) -> dict:
        """Put a new sticker on the page, from the tray."""
        fields = self._common(body, ("asset",))
        if isinstance(fields, dict):
            return fields
        command_id, point, based_on, (asset,) = fields
        receipt = self._gesture(Command(
            action=ADD_OWN_STICKER,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            params=(("asset", asset), ("x", point.get("x")),
                    ("y", point.get("y"))),
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def remove(self, body: dict) -> dict:
        """Take a sticker off the page, back to the tray."""
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        based_on = body.get("based_on_revision")
        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")
        receipt = self._gesture(Command(
            action=REMOVE_OWN_STICKER,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            object_id=sticker_id,
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def animate(self, body: dict) -> dict:
        """Handle the child's double-click/tap animation intent.

        When OmegaJev is connected, the gesture becomes a one-turn Jev goal
        with an animation-only choice surface. Jev chooses the declared clip;
        it does not receive command arguments or bypass the kernel. When no
        Jev runtime is connected, the historical mechanical toggle remains so
        local/public interaction does not depend on model availability.

        Deliberately not world-locked as a whole: available() is a network
        health probe and double_click can run OmegaJev inference. The reads
        and the one mutation below are each serialized on their own.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        based_on = body.get("based_on_revision")
        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")

        sticker = self.kernel.sticker(sticker_id)
        if sticker is None:
            return self._bad_request("no such sticker")

        if self.jev_controller.available():
            result = self.jev_controller.double_click(
                sticker_id,
                actor=BROWSER_PRINCIPAL,
                command_prefix=command_id,
                requested_by=BROWSER_PRINCIPAL,
            )
            return {
                "ok": bool(result.get("ok")),
                "jev": result,
                "receipt": (
                    result["trace"][-1]["receipt"]
                    if result.get("trace") else None),
                "state": self.state(),
            }

        # The settled clip is read from the same world the toggle proposes
        # against, so a concurrent gesture cannot invert the intended flip.
        with self._world_lock:
            sticker = self.kernel.sticker(sticker_id)
            if sticker is None:
                return self._bad_request("no such sticker")
            definition = self.kernel.assets.get(sticker.asset)
            rest = definition.rest_animation if definition else "none"
            active = [
                a for a in (definition.animations if definition else ())
                if a not in ("none", rest)
            ]
            # A toggle: use the definition's living rest clip as the settled
            # state, and the first declared active clip as the simple child
            # double-tap behavior.
            wanted = rest if sticker.animation != rest else (
                active[0] if active else rest)

            receipt = self._gesture(Command(
                action=ANIMATE_OWN_STICKER,
                actor=BROWSER_PRINCIPAL,
                command_id=command_id,
                object_id=sticker_id,
                params=(("animation", wanted),),
                based_on_revision=based_on,
            ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def resize(self, body: dict) -> dict:
        """Set a sticker's bounded apparent scale.

        This is an authoritative world transform. The bridge forwards the
        proposed value unchanged; the kernel validates it against definition bounds
        and receipts either acceptance or refusal.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        based_on = body.get("based_on_revision")
        scale = body.get("scale")
        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")

        receipt = self._gesture(Command(
            action=RESIZE_OWN_STICKER,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            object_id=sticker_id,
            params=(("scale", scale),),
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def facing(self, body: dict) -> dict:
        """Set a sticker's horizontal facing without altering its sprite pack."""
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        sticker_id = body.get("sticker")
        command_id = body.get("command_id")
        based_on = body.get("based_on_revision")
        facing = body.get("facing")
        if not isinstance(sticker_id, str) or not sticker_id:
            return self._bad_request("missing sticker id")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")

        receipt = self._gesture(Command(
            action=SET_STICKER_FACING,
            actor=BROWSER_PRINCIPAL,
            command_id=command_id,
            object_id=sticker_id,
            params=(("facing", facing),),
            based_on_revision=based_on,
        ))
        return {"ok": True, "receipt": receipt.to_dict(), "state": self.state()}

    def _common(self, body, extra=()):
        """Shape validation shared by the pointer-driven write paths.

        Shape is the bridge's business; VALUES are the kernel's. A coordinate
        that is off the page or not a number is a well-formed proposal with a
        bad value, so it goes to the kernel and the refusal is receipted.
        """
        if not isinstance(body, dict):
            return self._bad_request("body is not a JSON object")
        command_id = body.get("command_id")
        point = body.get("point")
        based_on = body.get("based_on_revision")
        if not isinstance(command_id, str) or not command_id:
            return self._bad_request("missing command id")
        if not isinstance(point, dict):
            return self._bad_request("missing pointer position")
        if based_on is not None and not isinstance(based_on, int):
            return self._bad_request("based_on_revision must be an integer")
        values = []
        for name in extra:
            value = body.get(name)
            if not isinstance(value, str) or not value:
                return self._bad_request("missing " + name)
            values.append(value)
        return command_id, point, based_on, tuple(values)

    def _bad_request(self, reason: str) -> dict:
        """Malformed input never reaches the kernel and never mutates."""
        return {"ok": False, "error": reason, "state": self.state()}


def make_handler(bridge: Bridge, quiet: bool = False):

    class Handler(BaseHTTPRequestHandler):
        server_version = "StickerBookBridge/0.1"

        def address_string(self):
            # Skip the reverse DNS lookup BaseHTTPRequestHandler does by
            # default; on loopback it is pure latency.
            return self.client_address[0]

        def _send(self, code, payload, content_type="application/json"):
            data = payload if isinstance(payload, bytes) else \
                json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            # The page needs no third-party anything; forbid it outright.
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path == "/api/state":
                return self._send(200, bridge.state())
            if path == "/api/book":
                return self._send(200, book.listing())
            if path == "/api/receipts":
                return self._send(200, {"receipts": bridge.receipts()})
            if path == "/api/adult/inference":
                return self._send(200, bridge.inference_settings())
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            if path.startswith("/generated-pages/"):
                return self._generated(path[len("/generated-pages/"):])
            return self._send(404, {"error": "not found"})

        ROUTES = {"/api/propose-move": "propose_move",
                  "/api/place": "place",
                  "/api/remove": "remove",
                  "/api/animate": "animate",
                  "/api/resize": "resize",
                  "/api/facing": "facing",
                  "/api/agent/converse": "converse",
                  "/api/observe-page-path": "observe_page_path",
                  "/api/adult/inference": "set_inference",
                  "/api/creator/draft": "creator_draft"}

        def do_POST(self):
            path = self.path.split("?")[0]

            if path == "/api/creator/page-image":
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    return self._send(
                        400, {"ok": False, "error": "bad length"})
                if length <= 0:
                    return self._send(
                        400, {"ok": False, "error": "empty-page-image"})
                if length > MAX_PAGE_UPLOAD_BYTES:
                    return self._send(
                        413, {"ok": False, "error": "page-image-too-large"})
                content_type = (
                    self.headers.get("Content-Type") or "").split(";")[0]
                raw_name = (
                    self.headers.get("X-StickerBook-Filename") or "page.png")
                filename = urllib.parse.unquote(raw_name)
                raw = self.rfile.read(length)
                result = bridge.page_image_draft(
                    raw, content_type, filename)
                return self._send(
                    200 if result.get("ok") else 400, result)

            route = self.ROUTES.get(path)
            if route is None:
                return self._send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, {"ok": False, "error": "bad length"})
            if length > MAX_BODY_BYTES:
                return self._send(413, {"ok": False, "error": "body too large"})
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else None
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"ok": False, "error": "body is not JSON",
                                        "state": bridge.state()})
            result = getattr(bridge, route)(body)
            return self._send(200 if result.get("ok") else 400, result)

        def _static(self, name):
            # Root browser code remains exact-name only. Visual assets may live
            # below static/assets/, but path resolution is contained there.
            if name in ("index.html", "app.js", "style.css", "help.json"):
                path = os.path.join(STATIC_DIR, name)
            elif name.startswith("assets/"):
                asset_root = os.path.realpath(os.path.join(STATIC_DIR, "assets"))
                relative = name[len("assets/"):]
                path = os.path.realpath(os.path.join(asset_root, relative))
                try:
                    contained = os.path.commonpath((asset_root, path)) == asset_root
                except ValueError:
                    contained = False
                if not relative or not contained:
                    return self._send(404, {"error": "not found"})
            else:
                return self._send(404, {"error": "not found"})

            if not os.path.isfile(path):
                return self._send(404, {"error": "not found"})

            ext = os.path.splitext(path)[1].lower()
            if ext not in CONTENT_TYPES:
                return self._send(404, {"error": "not found"})

            with open(path, "rb") as handle:
                self._send(200, handle.read(), CONTENT_TYPES[ext])

        def _generated(self, name):
            root = os.path.realpath(GENERATED_PAGE_DIR)
            path = os.path.realpath(os.path.join(root, name))
            try:
                contained = os.path.commonpath((root, path)) == root
            except ValueError:
                contained = False
            if not name or not contained or not os.path.isfile(path):
                return self._send(404, {"error": "not found"})
            ext = os.path.splitext(path)[1].lower()
            if ext not in CONTENT_TYPES or ext not in (
                    ".png", ".jpg", ".jpeg", ".webp"):
                return self._send(404, {"error": "not found"})
            with open(path, "rb") as handle:
                self._send(200, handle.read(), CONTENT_TYPES[ext])

        def address_string(self):
            # Skip the reverse DNS lookup BaseHTTPRequestHandler does
            # by default; on loopback it is pure latency.
            return self.client_address[0]

        def log_message(self, fmt, *args):
            if not quiet:
                sys.stderr.write("[bridge] %s\n" % (fmt % args))

    return Handler


def serve(host="127.0.0.1", port=8756, kernel=None, quiet=False,
          agent_runtime=None, jev_runtime=None, page_image_runtime=None):
    bridge = Bridge(
        kernel,
        agent_runtime=agent_runtime,
        jev_runtime=jev_runtime,
        page_image_runtime=page_image_runtime,
    )
    httpd = ThreadingHTTPServer((host, port), make_handler(bridge, quiet))
    return httpd, bridge


if __name__ == "__main__":
    # Loopback only. This is a local development surface, not a service.
    PORT = int(os.environ.get("STICKERBOOK_PORT", "8756"))
    try:
        httpd, _ = serve(
            "127.0.0.1",
            PORT,
            agent_runtime=agent_runtime_from_env(),
            jev_runtime=jev_runtime_from_env(),
            page_image_runtime=page_image_runtime_from_env(),
        )
    except OSError as exc:
        # Fail LOUDLY. A silent bind failure leaves an OLDER process
        # serving: it hands out the current static files but the Python
        # it imported at startup is stale, so the page looks updated
        # while the kernel behind it is not. That has cost real
        # debugging time twice in one sitting.
        sys.stderr.write(
            "\nStickerBook: cannot listen on 127.0.0.1:%d -- %s\n"
            "Something already serves that port, probably an older bridge.\n"
            "Stop it first; do NOT assume this one is running.\n\n"
            % (PORT, exc))
        raise SystemExit(2)
    print("StickerBook farm on http://127.0.0.1:%d/  (Ctrl-C to stop)" % PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        httpd.server_close()
