"""File-based client for the qrenderdoc live bridge."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import uuid
from typing import Any


class LiveBridgeError(RuntimeError):
    """Raised when the live qrenderdoc bridge cannot be reached."""


class LiveBridgeClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.ipc_dir = Path(tempfile.gettempdir()) / "renderdoc_mcp_bridge"
        self.request_file = self.ipc_dir / "request.json"
        self.response_file = self.ipc_dir / "response.json"
        self.lock_file = self.ipc_dir / "lock"

    def available(self) -> bool:
        return self.ipc_dir.exists()

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.available():
            raise LiveBridgeError("Live qrenderdoc bridge is not available")

        self._safe_remove(self.response_file)

        payload = {
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }

        self._acquire_write_slot()
        self.request_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self._safe_remove(self.lock_file)

        start = time.time()
        while time.time() - start < self.timeout:
            if self.response_file.exists():
                raw = json.loads(self.response_file.read_text(encoding="utf-8"))
                self._safe_remove(self.response_file)
                if "error" in raw:
                    err = raw["error"]
                    raise LiveBridgeError("{}: {}".format(err.get("code"), err.get("message")))
                return raw.get("result")
            time.sleep(0.1)

        raise LiveBridgeError("Timed out waiting for live bridge response")

    def _acquire_write_slot(self) -> None:
        start = time.time()
        while time.time() - start < self.timeout:
            if not self.lock_file.exists():
                try:
                    self.lock_file.write_text("lock", encoding="utf-8")
                    return
                except OSError:
                    time.sleep(0.05)
                    continue
            time.sleep(0.05)

        raise LiveBridgeError("Timed out waiting to acquire bridge write slot")

    @staticmethod
    def _safe_remove(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
