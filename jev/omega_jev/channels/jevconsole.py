"""
Offline console channel for the Jev experiment.

Replaces IRC / Telegram / Slack / Mattermost / WebSocket entirely. It makes no
network connection of any kind and holds no token.

  receive() -- returns a single fixed human intent on the first turn, then "".
               The intent is supplied by the operator at container start via
               the jevIntent config parameter. Nothing else can inject input.
  send()    -- writes to stdout, so the whole conversation is visible in
               `docker logs`. It cannot reach any external service.
"""

from __future__ import annotations

import sys

import channels
from config import config_get_by_key
from src.logger import get_logger

logger = get_logger(__name__)

DEFAULT_INTENT = "Please confirm which version of Omega you are running."


class JevConsoleChannel(channels.CommChannel):

    def __init__(self):
        super().__init__()
        self._intent = ""
        self._delivered = False

    def start(self) -> None:
        self._intent = str(config_get_by_key("jevIntent", DEFAULT_INTENT))
        self._delivered = False
        logger.info("[jevconsole] offline channel started; no network, no tokens")
        logger.info("[jevconsole] operator intent: %s", self._intent)

    def stop(self) -> None:
        self._delivered = True

    def receive(self) -> str:
        """Deliver the operator's intent exactly once."""
        if self._delivered:
            return ""
        self._delivered = True
        logger.info("[jevconsole] delivering operator intent to the loop")
        return self._intent

    def send(self, message: str) -> None:
        print("[jevconsole] AGENT SAYS: " + str(message), flush=True)
        sys.stdout.flush()


def loadOmegaPlugin():
    channels.registerCommChannel("jevconsole", JevConsoleChannel())
