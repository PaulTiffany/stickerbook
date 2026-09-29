"""
Jev provider plugin for Omega.

Replaces Omega's generative inference step with typed discriminative action
selection. Registers itself under the provider id "Jev".

Security design (see SECURITY.md):

  * Jev never produces an executable string. It selects an ACTION_ID, which the
    host compiles via the frozen table in jev_core.ACTIONS.
  * Credential handling is deployment-specific. In gateway mode the real key
    and any key-shaped environment value are absent from this process. In
    OpenShell mode the process receives only OpenShell's provider placeholder;
    the real provider credential remains at the OpenShell boundary.
  * On load and again on start, Omega's global LLM_COMMANDS allowlist is
    narrowed to exactly the command heads our table can emit, so that even a
    bug here cannot let `shell`, `metta`, `write-file` or `delete-file` run.
  * Every failure returns the empty string, which Omega compiles to "()" and
    executes as nothing.
  * The run is finite: after jevMaxTurns decisions the process stops outright.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

import providers
from config import config_get_by_key
from src.logger import get_logger

import jev_core
import sb_bridge

logger = get_logger(__name__)

DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_DECISIONS_PATH = "/jev/decisions"
DEFAULT_OPENROUTER_URL = "https://openrouter.ai"
DEFAULT_OPENROUTER_DECISIONS_PATH = "/api/alpha/decisions"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_TURNS = 6


# ---------------------------------------------------------------------------
# Hardening: narrow Omega's global command allowlist.
# ---------------------------------------------------------------------------

def _helper_modules():
    """Every loaded module object that owns an LLM_COMMANDS set.

    helper.py is reachable as both `helper` and `src.helper` depending on how
    it was first imported; those can be distinct module objects, so harden all
    of them rather than guessing.
    """
    found = []
    for name in ("helper", "src.helper"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "LLM_COMMANDS"):
            found.append(module)
    if not found:
        import helper as fallback  # noqa: PLC0415 -- deliberate late import
        found.append(fallback)
    return found


def harden_llm_commands(actions=None):
    """Restrict Omega's executable command vocabulary to our table's heads.

    Skills belonging to an inactive action set are removed here too, so only
    the active set is executable.

    Returns the resulting allowlist so tests and logs can assert on it.
    """
    heads = jev_core.allowed_command_heads(actions)
    result = set()
    for module in _helper_modules():
        module.LLM_COMMANDS.clear()
        module.LLM_COMMANDS.update(heads)
        # STATIC_LLM_COMMANDS is what remove_llm_command refuses to remove.
        # Replacing it means the dangerous built-ins are no longer protected
        # entries, and ours cannot be removed at runtime.
        module.STATIC_LLM_COMMANDS.clear()
        module.STATIC_LLM_COMMANDS.update(heads)
        result |= set(module.LLM_COMMANDS)
    logger.info("[jev] LLM_COMMANDS narrowed to: %s", sorted(result))
    return result


# ---------------------------------------------------------------------------
# Transport: explicit gateway or OpenShell provider boundary.
# ---------------------------------------------------------------------------

class ProxyTransport:
    """POSTs the Decisions request to the in-container credential proxy."""

    def __init__(self, url: str, timeout: int):
        self.url = url
        self.timeout = timeout

    def __call__(self, payload: dict) -> dict:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            # No Authorization header: nginx injects it. This process has no key.
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError("HTTP " + str(exc.code) + ": " + detail) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("network failure: " + str(exc.reason)) from exc
        return json.loads(raw)


class OpenShellProviderTransport:
    """POST Decisions through OpenShell's provider credential boundary.

    OPENROUTER_API_KEY is an OpenShell-injected placeholder, not the real
    provider secret. The placeholder is presented as a bearer token and
    OpenShell substitutes the real credential only for a policy-approved
    request to the configured provider endpoint.
    """

    def __init__(self, url: str, timeout: int,
                 token_env: str = "OPENROUTER_API_KEY"):
        self.url = url
        self.timeout = timeout
        self.token_env = token_env

    def __call__(self, payload: dict) -> dict:
        token = os.environ.get(self.token_env, "").strip()
        if not token:
            raise RuntimeError(
                "OpenShell provider placeholder is unavailable")
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError("HTTP " + str(exc.code) + ": " + detail) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("network failure: " + str(exc.reason)) from exc
        return json.loads(raw)


# ---------------------------------------------------------------------------
# The provider
# ---------------------------------------------------------------------------

class JevProvider(providers.LLMProvider):

    def __init__(self):
        super().__init__()
        self.transport = None
        self.model = DEFAULT_MODEL
        self.max_turns = DEFAULT_MAX_TURNS
        self.turn = 0
        self.actions = jev_core.ACTIONS
        self.criteria = jev_core.ACTION_CRITERIA
        self.scene_path = ""
        self.intent = ""
        self.kernel_mode = False
        self.rpc_mode = False

    def _make_transport(self, timeout: int):
        mode = str(config_get_by_key("jevTransport", "gateway")).strip().lower()
        if mode == "openshell":
            base = str(config_get_by_key(
                "jevOpenShellUrl", DEFAULT_OPENROUTER_URL)).strip()
            path = str(config_get_by_key(
                "jevOpenShellDecisionsPath",
                DEFAULT_OPENROUTER_DECISIONS_PATH))
            if not base:
                raise RuntimeError("jevOpenShellUrl is empty")
            return OpenShellProviderTransport(
                base.rstrip("/") + path, timeout)
        if mode == "gateway":
            gateway = str(config_get_by_key("jevGatewayUrl", "")).strip() \
                or str(config_get_by_key(
                    "GATEWAY_URL", "http://localhost:8080"))
            path = str(config_get_by_key(
                "jevDecisionsPath", DEFAULT_DECISIONS_PATH))
            return ProxyTransport(gateway.rstrip("/") + path, timeout)
        raise RuntimeError("unsupported jevTransport: " + mode)

    def _kernel_actions(self):
        """Every legal key this turn -> the one fixed compilation target.

        The keys change turn by turn as the world changes; the *literal* they
        compile to never does. This is the frozen-table property preserved
        under a dynamic action surface.
        """
        table = sb_bridge.action_table()
        actions = {key: "sb-apply" for key in table}
        return actions, sb_bridge.describe_actions()

    def _scene(self) -> dict:
        """Host-composed scene state.

        The engine owns the world and hands the agent a view. The agent never
        reads it from disk itself and cannot alter how it is described.
        """
        if not self.scene_path:
            return {}
        try:
            with open(self.scene_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return {"butterfly": str(data.get("butterfly", "resting"))}
        except Exception:
            return {"butterfly": "resting"}

    def start(self) -> None:
        # Which host-owned action set is active this run.
        set_name = str(config_get_by_key("jevActionSet", "generic"))
        self.kernel_mode = (set_name == "stickerbook")
        self.rpc_mode = (set_name == "stickerbook-rpc")

        if self.rpc_mode:
            # Live browser service mode: the authoritative world stays in the
            # host bridge. This Omega loop receives only the host-composed
            # goal/scene/finite action descriptions through stickerbookrpc.
            import importlib  # noqa: PLC0415
            rpc = importlib.import_module("stickerbookrpc")
            harden_llm_commands({"_": "sb-return"})
            self.model = str(config_get_by_key("jevModel", DEFAULT_MODEL))
            timeout = int(config_get_by_key("jevTimeout", DEFAULT_TIMEOUT))
            self.transport = self._make_transport(timeout)
            self.turn = 0
            self.scene_path = ""
            self.intent = ""
            rpc.set_provider_ready("omegajev")
            logger.info("[jev] provider started (StickerBook RPC mode)")
            logger.info("[jev]   executable    : ['sb-return']")
            logger.info("[jev]   decisions via : %s", self.transport.url)
            return

        if self.kernel_mode:
            # The table is regenerated by the authority kernel every turn, so
            # there is no fixed action set here -- only a fixed compilation
            # target. Every legal key compiles to the same zero-argument
            # command, `sb-apply`.
            sb_bridge.init(str(config_get_by_key(
                "jevProfile", "local-single-agent")))
            self.actions, self.criteria = self._kernel_actions()
            harden_llm_commands({"_": "sb-apply"})
            self.intent = str(config_get_by_key("jevIntent", ""))
            self.model = str(config_get_by_key("jevModel", DEFAULT_MODEL))
            self.max_turns = int(config_get_by_key("jevMaxTurns",
                                                   DEFAULT_MAX_TURNS))
            timeout = int(config_get_by_key("jevTimeout", DEFAULT_TIMEOUT))
            self.transport = self._make_transport(timeout)
            self.turn = 0
            self.scene_path = ""
            logger.info("[jev] provider started (StickerBook kernel mode)")
            logger.info("[jev]   principal     : %s", sb_bridge.AGENT_ID)
            logger.info("[jev]   profile       : %s",
                        sb_bridge.kernel().profile.name)
            logger.info("[jev]   agent tools   : %s",
                        sorted(sb_bridge.kernel().effective_tools(
                            sb_bridge.AGENT_ID)))
            logger.info("[jev]   executable    : ['sb-apply'] "
                        "(one zero-argument command)")
            logger.info("[jev]   decisions via : %s", self.transport.url)
            return

        try:
            self.actions, self.criteria = jev_core.get_action_set(set_name)
        except jev_core.JevFailClosed as exc:
            logger.error("[jev] %s -- falling back to the generic set", exc)
            set_name = "generic"
            self.actions, self.criteria = jev_core.get_action_set(set_name)

        # Harden again here: start() is guaranteed to run after every plugin
        # has loaded and before the first decision is ever requested.
        harden_llm_commands(self.actions)

        self.scene_path = str(config_get_by_key("jevScenePath", "")) \
            if set_name == "butterfly" else ""

        # The operator's intent is host configuration, read directly. It is
        # never parsed out of Omega's prompt.
        self.intent = str(config_get_by_key("jevIntent", ""))

        self.model = str(config_get_by_key("jevModel", DEFAULT_MODEL))
        self.max_turns = int(config_get_by_key("jevMaxTurns", DEFAULT_MAX_TURNS))
        timeout = int(config_get_by_key("jevTimeout", DEFAULT_TIMEOUT))

        # Transport is an explicit deployment choice. "gateway" preserves the
        # existing split-container experiment; "openshell" uses an OpenShell
        # provider placeholder and policy-mediated direct OpenRouter request.
        self.transport = self._make_transport(timeout)
        url = self.transport.url
        self.turn = 0

        logger.info("[jev] provider started")
        logger.info("[jev]   model         : %s", self.model)
        logger.info("[jev]   decisions via : %s", url)
        logger.info("[jev]   max turns     : %s", self.max_turns)
        logger.info("[jev]   action set    : %s", set_name)
        logger.info("[jev]   action table  : %s", sorted(self.actions))
        if self.scene_path:
            logger.info("[jev]   scene state   : %s", self.scene_path)

    def stop(self) -> None:
        self.transport = None

    def chat(self, prompt: str, max_tokens: int = 6000,
             reasoning_mode: str = "medium") -> str:
        """Called by Omega's loop in place of a generative LLM completion.

        Returns a fixed literal command string from the host action table, or
        the empty string (execute nothing).
        """
        if self.rpc_mode:
            import importlib  # noqa: PLC0415
            rpc = importlib.import_module("stickerbookrpc")
            request = rpc.current_request("omegajev")
            if not isinstance(request, dict):
                return jev_core.FAIL_CLOSED_OUTPUT

            offered = request.get("actions", {})
            if not isinstance(offered, dict) or not offered:
                result = {"ok": False, "error": "no-legal-jev-actions"}
                return "sb-return" if rpc.stage_result(result) else ""

            actions = {key: "sb-return" for key in offered}
            harden_llm_commands({"_": "sb-return"})
            view = {
                "goal": request.get("goal", {}),
                "scene": request.get("scene", {}),
                "turn": request.get("turn"),
                "max_turns": request.get("max_turns"),
            }
            _command, trace = jev_core.decide(
                state=view,
                model=self.model,
                transport=self.transport,
                actions=actions,
                criteria=offered,
                log=lambda message: logger.warning("[jev-rpc] %s", message),
            )
            choice = trace.get("action_id")
            if isinstance(choice, str) and choice in actions:
                result = {"ok": True, "choice": choice}
            else:
                result = {
                    "ok": False,
                    "error": "jev-failed-closed",
                }
                if trace.get("failed_closed"):
                    logger.warning(
                        "[jev-rpc] FAILED CLOSED: %s",
                        trace["failed_closed"])
            if not rpc.stage_result(result):
                logger.warning("[jev-rpc] failed to stage bounded response")
                return jev_core.FAIL_CLOSED_OUTPUT
            # Always execute the same zero-argument return skill. On failure
            # this returns a bounded error promptly instead of making the host
            # wait for the RPC timeout.
            return "sb-return"

        self.turn += 1

        if self.turn > self.max_turns:
            logger.info("[jev] ==========================================")
            logger.info("[jev] TURN LIMIT REACHED (%s). STOPPING.", self.max_turns)
            logger.info("[jev] ==========================================")
            sys.stdout.flush()
            sys.stderr.flush()
            # Decisive, unambiguous stop. The container exits; there is no
            # question about whether the experiment is still running.
            os._exit(0)

        if self.kernel_mode:
            # Regenerate the legal action table from the kernel. It reflects
            # the world as it is NOW: actions appear and disappear as the
            # scene changes, and an illegal action is simply not a key.
            self.actions, self.criteria = self._kernel_actions()
            # Re-harden: whatever the table contains, the executable
            # vocabulary stays exactly {sb-apply}.
            harden_llm_commands({"_": "sb-apply"})
            scene = sb_bridge.scene()
        else:
            scene = self._scene()

        # Jev is handed a bounded host-composed VIEW, never Omega's prompt.
        # Only one narrow field (the last skill result) is taken from the
        # prompt; everything else here is host state.
        view = jev_core.project_view(
            prompt=prompt,
            intent=self.intent,
            scene=scene,
            turn=self.turn,
            max_turns=self.max_turns,
            actions=self.actions,
        )
        if self.kernel_mode:
            # A finished label beats raw parser output (Decisions guidance:
            # "pass computed facts as finished labels rather than raw values").
            view["last_action_result"] = sb_bridge.last_action_label()
        probes = sb_bridge.probes() if self.kernel_mode else None

        # The state is sent as a JSON OBJECT, not a serialized string, so the
        # instructions can reference field paths such as `operator_intent`.
        command, trace = jev_core.decide(
            state=view,
            model=self.model,
            transport=self.transport,
            actions=self.actions,
            criteria=self.criteria,
            probes=probes,
            log=lambda message: logger.warning("[jev] %s", message),
        )

        logger.info("[jev] ---- decision trace, turn %s/%s ----",
                    self.turn, self.max_turns)
        logger.info("[jev]   view chars    : %s", trace["state_chars"])
        logger.info("[jev]   view          : %s", json.dumps(view, sort_keys=True))
        logger.info("[jev]   offered       : %s", trace["offered_actions"])
        logger.info("[jev]   ACTION_ID     : %s", trace["action_id"])
        logger.info("[jev]   confidence    : %s", trace["confidence"])
        logger.info("[jev]   probabilities : %s", trace["probabilities"])
        if trace.get("probes"):
            logger.info("[jev]   probes        : %s (advisory, never actuated)",
                        trace["probes"])
        logger.info("[jev]   compiled      : %r", trace["compiled"])
        if trace["failed_closed"]:
            logger.warning("[jev]   FAILED CLOSED : %s", trace["failed_closed"])

        if self.kernel_mode:
            # Stage the selection for the zero-argument sb-apply skill.
            # Staging is not authorization: the kernel re-validates the key
            # when it runs, and refuses on its own terms.
            if trace["action_id"] is None or not sb_bridge.stage(trace["action_id"]):
                logger.warning("[jev]   NOT STAGED    : nothing will be applied")
                sys.stdout.flush()
                return jev_core.FAIL_CLOSED_OUTPUT
            logger.info("[jev]   staged        : %s -> (sb-apply)",
                        trace["action_id"])
        sys.stdout.flush()

        return command


def loadOmegaPlugin():
    # Harden as early as possible, before any other plugin can run.
    harden_llm_commands()
    providers.registerLLMProvider("Jev", JevProvider())
