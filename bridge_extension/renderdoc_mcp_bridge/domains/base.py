"""Shared base helpers for live bridge services."""

import sys


class BridgeService:
    def __init__(self, ctx):
        self.ctx = ctx

    @staticmethod
    def _no_capture():
        return {
            "ok": False,
            "mode": "summary",
            "data": None,
            "err": {"code": "capture_not_loaded", "msg": "No capture loaded"},
            "meta": {"cap": None, "truncated": False},
        }

    @staticmethod
    def _warn_swallow(context, exc):
        print("[renderdoc-mcp-bridge] warn {}: {}".format(context, exc), file=sys.stderr)
