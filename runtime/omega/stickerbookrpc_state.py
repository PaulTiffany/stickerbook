"""Canonical, process-local RPC state shared by all channel executions.

Imported normally from Omega's channels search path. No persistence or IPC.
"""
import threading


class RpcState:
    def __init__(self):
        self.lock = threading.RLock()
        self.gate = threading.Lock()
        self.current = None
        self.staged = None
        self.serial = 0
        self.provider_ready = False
        self.provider_metadata = {}
        self.role = ""
        self.server = None
        self.thread = None
        self.memory = None


state = RpcState()
