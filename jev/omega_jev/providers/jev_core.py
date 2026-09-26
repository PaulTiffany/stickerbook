"""
Jev decision core -- the trusted, host-owned part of the Jev/Omega adapter.

This module deliberately has NO Omega imports and NO network code, so that the
whole security argument can be unit-tested with plain Python on any machine.

The central claim this module implements:

    Jev chooses.  The host compiles.  Omega executes.

Jev returns an ACTION_ID (a key).  The host looks that key up in a frozen,
host-owned table and emits a fixed literal string.  Nothing Jev sends is ever
concatenated into, substituted into, or used to construct the string that
Omega will parse and evaluate.

Every abnormal condition returns FAIL_CLOSED_OUTPUT, which compiles to the
empty Omega expression "()" and therefore executes nothing at all.
"""

from __future__ import annotations

import json
import re

# ---------------------------------------------------------------------------
# THE AUTHORITY TABLE
# ---------------------------------------------------------------------------
# ACTION_ID -> the EXACT literal command text handed to Omega.
#
# This dict is the authority boundary of the whole experiment.  Jev may select
# one of its KEYS.  Jev can never add a key, alter a value, or cause any string
# outside this table to reach Omega's parser.
#
# Keep it absurdly small.  Growing it is a deliberate, reviewable act by a
# human developer, never a runtime event.
ACTIONS = {
    "VERSION": "version",
    "NOOP": "jev-noop",
}

# Descriptions shown to Jev so it can discriminate. These are advisory text for
# the decision only; they carry no authority and are never executed.
ACTION_CRITERIA = {
    "VERSION": (
        "Report the Omega version string. Choose this when the state does not "
        "yet contain a version result, to confirm the agent can execute a real skill."
    ),
    "NOOP": (
        "Do nothing this turn. Choose this when the state already shows a "
        "version result, so no further action is warranted."
    ),
}

# ---------------------------------------------------------------------------
# STAGE 3: a tiny StickerBook-flavoured action set.
# ---------------------------------------------------------------------------
# Same authority rule. The sticker id ("butterfly") and the animation names
# ("flutter", "rest") are HOST-OWNED enumerations baked into these skill names.
# Jev never supplies a sticker id, an animation name, a coordinate, a duration
# or any other argument -- the skills take none. Jev only picks which of three
# fixed, pre-authorised motions happens next.
ACTIONS_BUTTERFLY = {
    "BUTTERFLY_FLUTTER": "butterfly-flutter",
    "BUTTERFLY_REST": "butterfly-rest",
    "NOOP": "jev-noop",
}

CRITERIA_BUTTERFLY = {
    "BUTTERFLY_FLUTTER": (
        "Make the butterfly flutter: a gentle, gradual motion. Choose this when "
        "the human wants movement and the butterfly is currently resting."
    ),
    "BUTTERFLY_REST": (
        "Let the butterfly settle and rest. Choose this when the human wants it "
        "to be still, or it has been fluttering and should now settle."
    ),
    "NOOP": (
        "Do nothing this turn. Choose this when the butterfly is already in the "
        "state the human asked for."
    ),
}

# Selectable by the jevActionSet config parameter. Adding a set here is a
# deliberate act by a human editing source; nothing at runtime can add one.
ACTION_SETS = {
    "generic": (ACTIONS, ACTION_CRITERIA),
    "butterfly": (ACTIONS_BUTTERFLY, CRITERIA_BUTTERFLY),
}


def get_action_set(name):
    """Return (actions, criteria) for a named set, or fail closed."""
    if name not in ACTION_SETS:
        raise JevFailClosed("unknown action set: " + repr(name))
    return ACTION_SETS[name]


# What the provider returns when anything at all goes wrong.
# Omega's helper.balance_parentheses("") returns "()", which sread parses as the
# empty expression, over which the loop iterates zero commands. No execution.
FAIL_CLOSED_OUTPUT = ""

# Fields a typed `choice` answer may carry. Anything else (notably free-form
# prose) is treated as a protocol violation and fails closed.
ALLOWED_ANSWER_FIELDS = {"type", "choice", "confidence", "probabilities"}

# Backstop cap. With a projected view (project_view) the state is far smaller
# than this; the cap only matters if a caller passes raw text.
MAX_STATE_CHARS = 12000

# A view is a small record, not a transcript. Enforced by project_view.
VIEW_MAX_CHARS = 1200
LAST_RESULT_MAX_CHARS = 300


class JevFailClosed(Exception):
    """Raised internally whenever no action may be taken."""


# ---------------------------------------------------------------------------
# Allowlist derivation
# ---------------------------------------------------------------------------

def allowed_command_heads(actions=None) -> set:
    """The set of Omega command names our table can possibly produce.

    Used to narrow Omega's global LLM_COMMANDS allowlist, so that even a bug in
    this adapter cannot let `shell`, `metta`, `write-file` etc. execute.
    """
    actions = ACTIONS if actions is None else actions
    return {value.split()[0] for value in actions.values()}


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------

def truncate_state(state: str, limit: int = MAX_STATE_CHARS) -> str:
    """Keep the TAIL of Omega's context.

    The tail is what carries LAST_SKILL_USE_RESULTS, HISTORY and the human
    message -- i.e. the feedback that must influence the next decision.
    """
    text = str(state)
    if len(text) <= limit:
        return text
    return "...[truncated]...\n" + text[-limit:]


def extract_last_result(prompt, limit: int = LAST_RESULT_MAX_CHARS) -> str:
    """Pull ONLY the LAST_SKILL_USE_RESULTS field out of Omega's prompt.

    This is the single field the host cannot already supply for itself. Every
    other part of Omega's constructed prompt -- the system preamble, the
    SKILLS advertisement, OUTPUT_FORMAT, SAVE_PERMANENT_FILES_DIR, HISTORY,
    TIME -- is discarded and never reaches Jev.

    Fails closed to "": if the markers are absent or the prompt is not a
    string, the result is empty. It never falls back to returning the blob.
    """
    try:
        text = str(prompt)
    except Exception:
        return ""
    start = text.find("LAST_SKILL_USE_RESULTS:")
    if start < 0:
        return ""
    start += len("LAST_SKILL_USE_RESULTS:")
    end = text.find("HISTORY:", start)
    segment = text[start:end] if end > start else text[start:]
    return " ".join(segment.split())[:limit]


def project_view(prompt, intent, scene, turn, max_turns, actions) -> dict:
    """Compose the bounded, host-owned view handed to Jev.

    Everything here is either host state (intent from config, scene from the
    host-owned file, turn counter, action table) or one narrowly extracted
    field. The result is a small enumerable record whose keys are fixed.

    Root SECURITY.md section 5: the agent gets a view sufficient to reason,
    not a copy of the machinery being observed.
    """
    view = {
        "turn": int(turn),
        "turns_remaining": max(0, int(max_turns) - int(turn)),
        "operator_intent": str(intent or "")[:200],
        "scene": dict(scene or {}),
        "last_action_result": extract_last_result(prompt),
        "available_actions": sorted(actions or ()),
    }
    # Hard size bound. Trim the only variable-length field first, then give up
    # on it entirely rather than emit an oversized view.
    if len(json.dumps(view)) > VIEW_MAX_CHARS:
        view["last_action_result"] = view["last_action_result"][:80]
    if len(json.dumps(view)) > VIEW_MAX_CHARS:
        view["last_action_result"] = ""
    return view


class JevPosingError(JevFailClosed):
    """The request violates Decisions-API usage rules. Fails closed.

    Posing mistakes are silent quality failures: the request succeeds, the
    answer is worse, and nothing reports it. These rules turn that class of
    mistake into a loud, mechanical failure instead.
    """


VALID_QUESTION_TYPES = ("choice", "noul", "score")
FALLBACK_KEY = "NOOP"
MIN_INSTRUCTION_CHARS = 25
MIN_CRITERION_CHARS = 12
MAX_STATE_BYTES = 4000


def _resolve_path(state, path: str) -> bool:
    """Is `path` (dotted) reachable in the state object?"""
    node = state
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, dict) and node and all(
                isinstance(v, dict) for v in node.values()):
            # one level of per-object fan-out, e.g. scene.<sticker>.motion
            if all(part in v for v in node.values()):
                node = next(iter(node.values()))[part]
            else:
                return False
        else:
            return False
    return True


def validate_request(request: dict) -> None:
    """Enforce OpenRouter Decisions usage rules. Raises JevPosingError.

    Rules, each corresponding to published guidance:

    1. `state` must be an object or array -- never a serialized JSON string.
    2. `state` must be bounded.
    3. Every question needs real `instructions`, not its own id.
    4. Backtick-quoted field paths in instructions must exist in `state`.
    5. A `choice` needs >= 2 options, each with a real description.
    6. A `choice` must offer an explicit fallback, so the model is never
       forced to pick something arbitrary.
    7. A `noul` must describe BOTH sides.
    8. A `score` must describe its levels as a list.
    """
    state = request.get("state")
    if isinstance(state, str):
        stripped = state.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            raise JevPosingError(
                "state is a serialized JSON string; send the object itself so "
                "instructions can reference its field paths")
    elif not isinstance(state, (dict, list)):
        raise JevPosingError("state must be an object, array or plain string")

    size = len(json.dumps(state, sort_keys=True, default=str))
    if size > MAX_STATE_BYTES:
        raise JevPosingError("state is %d bytes; bound it to %d"
                             % (size, MAX_STATE_BYTES))

    questions = request.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise JevPosingError("request carries no questions")

    for name, question in questions.items():
        where = "question %r" % name
        if not isinstance(question, dict):
            raise JevPosingError("%s is not an object" % where)
        qtype = question.get("type")
        if qtype not in VALID_QUESTION_TYPES:
            raise JevPosingError("%s has invalid type %r" % (where, qtype))

        instructions = question.get("instructions")
        if not isinstance(instructions, str) or                 len(instructions.strip()) < MIN_INSTRUCTION_CHARS:
            raise JevPosingError(
                "%s needs instructions of at least %d characters; a question "
                "id is not an instruction" % (where, MIN_INSTRUCTION_CHARS))
        if instructions.strip().strip("`") == name:
            raise JevPosingError("%s uses its own id as its instruction" % where)

        if isinstance(state, dict):
            for path in re.findall(r"`([A-Za-z0-9_.]+)`", instructions):
                if not _resolve_path(state, path):
                    raise JevPosingError(
                        "%s references `%s`, which does not exist in state"
                        % (where, path))

        criteria = question.get("criteria")
        if qtype == "choice":
            if not isinstance(criteria, dict) or len(criteria) < 2:
                raise JevPosingError("%s needs at least two options" % where)
            for key, text in criteria.items():
                if not isinstance(text, str) or                         len(text.strip()) < MIN_CRITERION_CHARS or                         text.strip() == key:
                    raise JevPosingError(
                        "%s option %r needs a real description, not the key"
                        % (where, key))
            if FALLBACK_KEY not in criteria:
                raise JevPosingError(
                    "%s has no explicit %r option; without a fallback the "
                    "model is forced to pick something arbitrary"
                    % (where, FALLBACK_KEY))
        elif qtype == "noul":
            if not isinstance(criteria, dict) or                     not str(criteria.get("true", "")).strip() or                     not str(criteria.get("false", "")).strip():
                raise JevPosingError(
                    "%s must describe both the true and false sides" % where)
        elif qtype == "score":
            if not isinstance(criteria, (list, tuple)) or len(criteria) < 2:
                raise JevPosingError("%s needs a list of levels" % where)


DEFAULT_INSTRUCTIONS = (
    "Choose the single action to take this turn so that the scene in `scene` "
    "moves closer to what `operator_intent` asks for. Prefer an action that "
    "addresses a part of `operator_intent` that `scene` does not yet satisfy."
)


def build_request(state, model: str, actions=None, criteria=None,
                  instructions: str = "", probes=None) -> dict:
    """Build the Decisions API payload.

    `state` is sent as a JSON **object** when a mapping is given, not as a
    serialized string: the Decisions API supports object state and its
    instructions can then reference field paths such as `operator_intent`.

    `probes` are additional read-only questions (typically `noul`). They are
    answered alongside the choice at no extra round trip and are recorded in
    the trace for inspectability. **They carry no authority**: only the
    `action` answer is ever actuated.
    """
    actions = ACTIONS if actions is None else actions
    criteria = ACTION_CRITERIA if criteria is None else criteria

    # Only ever offer keys that exist in the authority table.
    offered = {key: criteria.get(key, key) for key in actions}

    questions = {
        "action": {
            "type": "choice",
            "instructions": instructions or DEFAULT_INSTRUCTIONS,
            "criteria": offered,
        }
    }
    for name, question in (probes or {}).items():
        if name != "action":          # the action question is not overridable
            questions[name] = question

    request = {
        "model": model,
        "state": state if isinstance(state, (dict, list)) else truncate_state(state),
        "questions": questions,
    }
    validate_request(request)      # fails closed on a posing mistake
    return request


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

def parse_decision(body, actions=None) -> tuple:
    """Validate a Decisions response and return (action_id, confidence, probs).

    Raises JevFailClosed on every malformed or out-of-vocabulary response.
    """
    actions = ACTIONS if actions is None else actions

    if not isinstance(body, dict):
        raise JevFailClosed("response body is not a JSON object")

    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise JevFailClosed("response contains no 'answers' object")

    answer = answers.get("action")
    if not isinstance(answer, dict):
        raise JevFailClosed("response contains no 'action' answer")

    if answer.get("type") != "choice":
        raise JevFailClosed(
            "expected a typed 'choice' answer, got type=" + repr(answer.get("type"))
        )

    unexpected = set(answer) - ALLOWED_ANSWER_FIELDS
    if unexpected:
        raise JevFailClosed(
            "answer carried non-typed fields (possible text generation): "
            + repr(sorted(unexpected))
        )

    action_id = answer.get("choice")
    if not isinstance(action_id, str):
        raise JevFailClosed("'choice' is not a string: " + repr(action_id))

    # THE critical check. The choice must be a key of the authority table.
    if action_id not in actions:
        raise JevFailClosed(
            "Jev returned ACTION_ID " + repr(action_id)
            + " which is not in the host action table "
            + repr(sorted(actions)) + "; refusing to act"
        )

    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict):
        probabilities = {}
    confidence = answer.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = None

    return action_id, confidence, probabilities


# ---------------------------------------------------------------------------
# Compilation -- the only place an executable string is produced
# ---------------------------------------------------------------------------

def compile_action(action_id: str, actions=None) -> str:
    """Return the fixed literal command text for a validated ACTION_ID.

    The returned string is read out of the host table by key. It is never built
    from, concatenated with, or formatted using any bytes Jev sent.
    """
    actions = ACTIONS if actions is None else actions
    if action_id not in actions:
        raise JevFailClosed("unknown ACTION_ID at compile time: " + repr(action_id))
    return actions[action_id]


# ---------------------------------------------------------------------------
# The whole decision step, with an injectable transport so failure modes are
# mechanically testable without a network.
# ---------------------------------------------------------------------------

def read_probes(body, probes) -> dict:
    """Collect probe answers for the trace. Advisory only, never actuated."""
    out = {}
    answers = body.get("answers", {}) if isinstance(body, dict) else {}
    for name in (probes or {}):
        answer = answers.get(name)
        if isinstance(answer, dict):
            out[name] = answer.get("noul", answer.get("choice",
                                                      answer.get("score")))
    return out


def decide(state, model, transport, actions=None, criteria=None, log=None,
           instructions: str = "", probes=None) -> tuple:
    """Run one Jev decision and return (command_text, trace_dict).

    `transport` is a callable taking the request dict and returning the parsed
    response dict. Any exception it raises -- timeout, network error, HTTP
    error, bad JSON -- results in FAIL_CLOSED_OUTPUT.

    Returns FAIL_CLOSED_OUTPUT ("") as the command text on every failure, which
    causes Omega to execute nothing.
    """
    actions = ACTIONS if actions is None else actions
    criteria = ACTION_CRITERIA if criteria is None else criteria

    state_text = json.dumps(state, sort_keys=True) if isinstance(state, dict)         else str(state)
    trace = {
        "offered_actions": sorted(actions),
        "state_chars": len(state_text),
        "probes": {},
        "action_id": None,
        "confidence": None,
        "probabilities": None,
        "compiled": None,
        "failed_closed": None,
    }

    try:
        request = build_request(state, model, actions, criteria,
                                instructions=instructions, probes=probes)
    except JevFailClosed as exc:
        trace["failed_closed"] = "posing error: " + str(exc)
        if log:
            log("Jev request rejected before sending: " + str(exc))
        return FAIL_CLOSED_OUTPUT, trace

    try:
        body = transport(request)
    except Exception as exc:  # noqa: BLE001 -- every transport failure fails closed
        trace["failed_closed"] = type(exc).__name__ + ": " + str(exc)
        if log:
            log("Jev transport failure, executing nothing: " + trace["failed_closed"])
        return FAIL_CLOSED_OUTPUT, trace

    trace["probes"] = read_probes(body, probes)

    try:
        action_id, confidence, probabilities = parse_decision(body, actions)
        command = compile_action(action_id, actions)
    except JevFailClosed as exc:
        trace["failed_closed"] = str(exc)
        if log:
            log("Jev decision rejected, executing nothing: " + str(exc))
        return FAIL_CLOSED_OUTPUT, trace

    trace["action_id"] = action_id
    trace["confidence"] = confidence
    trace["probabilities"] = probabilities
    trace["compiled"] = command
    return command, trace
