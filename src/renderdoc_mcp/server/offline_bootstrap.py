"""Server-facing offline bootstrap tool wrappers."""

from __future__ import annotations

from renderdoc_mcp.contracts.common import Envelope
from renderdoc_mcp.offline import OfflineBootstrapAdapter


class OfflineBootstrapTools:
    """Thin wrapper exposing offline bootstrap operations as tool-like methods."""

    def __init__(self, adapter: OfflineBootstrapAdapter | None = None) -> None:
        self.adapter = adapter or OfflineBootstrapAdapter()

    def get_capture_status(self, directory: str | None = None) -> Envelope:
        return self.adapter.get_capture_status(directory)

    def get_capture_context(self, path: str | None = None, sidecar: str | None = None) -> Envelope:
        return self.adapter.get_capture_context(path, sidecar)

    def get_capture_hints(self, path: str | None = None, sidecar: str | None = None) -> Envelope:
        return self.adapter.get_capture_hints(path, sidecar)

    def compare_capture_contexts(
        self,
        path_a: str,
        path_b: str,
        sidecar_a: str | None = None,
        sidecar_b: str | None = None,
    ) -> Envelope:
        return self.adapter.compare_capture_contexts(path_a, path_b, sidecar_a, sidecar_b)

    def compare_pass_lists(self, file_a: str, file_b: str) -> Envelope:
        return self.adapter.compare_pass_lists(file_a, file_b)

    def compare_packet_artifacts(self, file_a: str, file_b: str) -> Envelope:
        return self.adapter.compare_packet_artifacts(file_a, file_b)

    def compare_draw_packets(self, file_a: str, file_b: str) -> Envelope:
        return self.adapter.compare_draw_packets(file_a, file_b)

    def compare_texture_usage_artifacts(self, file_a: str, file_b: str) -> Envelope:
        return self.adapter.compare_texture_usage_artifacts(file_a, file_b)

    def list_captures(self, root: str, limit: int = 50) -> Envelope:
        return self.adapter.list_captures(root, limit)

    def open_capture(self, path: str) -> Envelope:
        return self.adapter.open_capture(path)

    def find_latest_capture(self, directory: str, recursive: bool = True) -> Envelope:
        return self.adapter.find_latest_capture(directory, recursive)

    def load_latest_capture(self, directory: str, recursive: bool = True) -> Envelope:
        return self.adapter.load_latest_capture(directory, recursive)

    def wait_for_new_capture(
        self,
        directory: str,
        previous_path: str | None = None,
        timeout: float = 30.0,
        interval: float = 0.5,
        recursive: bool = True,
    ) -> Envelope:
        return self.adapter.wait_for_new_capture(directory, previous_path, timeout, interval, recursive)
