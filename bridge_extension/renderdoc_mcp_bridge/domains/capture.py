"""Capture-scoped live bridge services."""

from .base import BridgeService


class CaptureStatusService(BridgeService):
    def run(self, _params):
        if not self.ctx.IsCaptureLoaded():
            return {
                "ok": True,
                "mode": "summary",
                "data": {"loaded": False},
                "err": None,
                "meta": {"cap": "active", "truncated": False},
            }

        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "loaded": True,
                "cap": "active",
                "path": self.ctx.GetCaptureFilename(),
                "api": str(self.ctx.APIProps().pipelineType),
            },
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }
