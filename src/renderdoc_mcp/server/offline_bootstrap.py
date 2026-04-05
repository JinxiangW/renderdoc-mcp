"""Server-facing offline bootstrap tool wrappers."""

from __future__ import annotations

from renderdoc_mcp.contracts.common import Envelope
from renderdoc_mcp.offline import OfflineBootstrapAdapter


class OfflineBootstrapTools:
    """Thin wrapper exposing offline bootstrap operations as tool-like methods."""

    def __init__(self, adapter: OfflineBootstrapAdapter | None = None) -> None:
        self.adapter = adapter or OfflineBootstrapAdapter()

    def get_capture_status(self) -> Envelope:
        return self.adapter.get_capture_status()

    def list_captures(self, root: str, limit: int = 50) -> Envelope:
        return self.adapter.list_captures(root, limit)

    def open_capture(self, path: str) -> Envelope:
        return self.adapter.open_capture(path)
