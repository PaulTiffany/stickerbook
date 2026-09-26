#!/usr/bin/env python3
"""
Stage 1: standalone Jev smoke test.

Proves, WITHOUT involving Omega at all, that:
  1. a Decisions API request succeeds;
  2. a typed `choice` answer is returned;
  3. the returned choice is one of the keys WE supplied;
  4. probabilities / confidence are observable;
  5. no free text generation is involved;
  6. every failure mode (network, timeout, HTTP error, malformed body,
     out-of-vocabulary choice) FAILS CLOSED -- i.e. yields no action.

Deliberately uses only the Python standard library, so nothing has to be
installed in order to run it.

The API key is read from the OPENROUTER_API_KEY environment variable and is
never printed, logged or written to disk.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

# Pinned model. Deliberately NOT the moving "~typesafe/jev-latest" alias, so
# that this experiment stays reproducible.
JEV_MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-1.13")

# Overridable only because the endpoint is still marked alpha upstream.
DECISIONS_URL = os.environ.get(
    "JEV_DECISIONS_URL", "https://openrouter.ai/api/alpha/decisions"
)

TIMEOUT_SECONDS = 30

# The host owns this vocabulary. Jev may only pick a key from it.
ACTION_CRITERIA = {
    "A": "ALPHA - pick this when the state calls for the first letter of the Greek alphabet",
    "B": "BETA - pick this when the state calls for the second letter of the Greek alphabet",
    "C": "NOOP - pick this when neither ALPHA nor BETA is clearly indicated",
}

# Fields a typed choice answer is allowed to carry. Anything outside this set
# (notably free-form prose) is treated as a protocol violation.
ALLOWED_ANSWER_FIELDS = {"type", "choice", "confidence", "probabilities"}


class JevError(RuntimeError):
    """Raised on any condition that must fail closed (produce no action)."""


def _require_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise JevError(
            "OPENROUTER_API_KEY is not set in the environment of this process. "
            "Refusing to continue; no request was made."
        )
    return key


def ask_jev(state: str, criteria: dict, question: str) -> dict:
    """Send one Decisions request and return the parsed response body.

    Raises JevError on every failure path, so that a caller cannot
    accidentally treat a failure as a decision.
    """
    api_key = _require_api_key()

    payload = {
        "model": JEV_MODEL,
        "state": state,
        "questions": {
            "action": {
                "type": "choice",
                "instructions": question,
                "criteria": criteria,
            }
        },
    }

    request = urllib.request.Request(
        DECISIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise JevError("HTTP " + str(exc.code) + " from Decisions API: " + detail) from exc
    except urllib.error.URLError as exc:
        raise JevError("Network failure contacting Decisions API: " + str(exc.reason)) from exc
    except TimeoutError as exc:
        raise JevError("Timeout contacting Decisions API") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JevError("Malformed (non-JSON) response body: " + str(exc)) from exc


def extract_choice(body: dict, allowed_keys: set) -> tuple:
    """Validate the response and extract (choice, confidence, probabilities).

    Every validation failure raises JevError -- fail closed.
    """
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise JevError("Response contains no 'answers' object")

    answer = answers.get("action")
    if not isinstance(answer, dict):
        raise JevError("Response contains no 'action' answer")

    if answer.get("type") != "choice":
        raise JevError("Expected a typed 'choice' answer, got type=" + repr(answer.get("type")))

    # No text generation: reject anything carrying unexpected (e.g. prose) fields.
    unexpected = set(answer) - ALLOWED_ANSWER_FIELDS
    if unexpected:
        raise JevError("Answer carried unexpected non-typed fields: " + repr(sorted(unexpected)))

    choice = answer.get("choice")
    if not isinstance(choice, str):
        raise JevError("'choice' is not a string: " + repr(choice))

    # THE critical check: the choice must be one of the keys the host supplied.
    if choice not in allowed_keys:
        raise JevError(
            "Jev returned " + repr(choice) + ", which is NOT one of the host-supplied keys "
            + repr(sorted(allowed_keys)) + ". Failing closed."
        )

    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict):
        raise JevError("Answer carried no observable probability distribution")

    confidence = answer.get("confidence")
    if not isinstance(confidence, (int, float)):
        raise JevError("Answer carried no observable confidence value")

    return choice, float(confidence), probabilities


def run_case(label: str, state: str, expect) -> bool:
    print("\n--- case: " + label + " ---")
    print("  state              : " + repr(state))
    print("  offered ACTION_IDs : " + repr(sorted(ACTION_CRITERIA)))
    try:
        body = ask_jev(
            state=state,
            criteria=ACTION_CRITERIA,
            question="Which action should be taken for this state?",
        )
        choice, confidence, probabilities = extract_choice(body, set(ACTION_CRITERIA))
    except JevError as exc:
        print("  RESULT             : FAILED CLOSED -- " + str(exc))
        return False

    print("  model reported     : " + str(body.get("model")))
    print("  selected ACTION_ID : " + choice)
    print("  confidence         : " + str(confidence))
    print("  probabilities      : " + str(probabilities))
    usage = body.get("usage") or {}
    if usage:
        print("  cost               : $" + str(usage.get("cost")))

    if expect is not None and choice != expect:
        print("  RESULT             : UNEXPECTED (wanted " + expect + ")")
        return False
    print("  RESULT             : OK")
    return True


def main() -> int:
    print("Stage 1 - standalone Jev Decisions smoke test")
    print("  endpoint : " + DECISIONS_URL)
    print("  model    : " + JEV_MODEL)
    present = "present in environment" if os.environ.get("OPENROUTER_API_KEY") else "ABSENT"
    print("  api key  : " + present)

    results = []
    results.append(run_case("state indicates ALPHA", "The situation clearly calls for alpha.", "A"))
    results.append(run_case("state indicates BETA", "The situation clearly calls for beta.", "B"))
    results.append(run_case("state indicates neither", "Nothing relevant is happening.", None))

    print("\n--- negative control: out-of-vocabulary enforcement ---")
    forged = {
        "answers": {
            "action": {
                "type": "choice",
                "choice": "shell",
                "confidence": 0.99,
                "probabilities": {"shell": 1.0},
            }
        }
    }
    try:
        extract_choice(forged, set(ACTION_CRITERIA))
        print("  RESULT : *** FAILED *** an out-of-vocabulary choice was accepted")
        results.append(False)
    except JevError as exc:
        print("  a forged choice of 'shell' was rejected: " + str(exc))
        print("  RESULT : OK (failed closed)")
        results.append(True)

    ok = all(results)
    print("\nSTAGE 1 " + ("PASSED" if ok else "FAILED")
          + " (" + str(sum(results)) + "/" + str(len(results)) + " checks)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
