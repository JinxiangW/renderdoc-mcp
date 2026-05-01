"""File-based client for the qrenderdoc live bridge."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from typing import Any


HEARTBEAT_STALE_SECONDS = 2.0


class LiveBridgeError(RuntimeError):
    """Raised when the live qrenderdoc bridge cannot be reached."""


class LiveBridgeClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.ipc_dir = Path(tempfile.gettempdir()) / "renderdoc_mcp_bridge"
        self.requests_dir = self.ipc_dir / "requests"
        self.responses_dir = self.ipc_dir / "responses"
        self.heartbeat_file = self.ipc_dir / "heartbeat"

    def available(self) -> bool:
        if not self.ipc_dir.exists() or not self.heartbeat_file.exists():
            return False
        try:
            ts = float(self.heartbeat_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return False
        return (time.time() - ts) < HEARTBEAT_STALE_SECONDS

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.available():
            raise LiveBridgeError("Live qrenderdoc bridge is not available")

        request_id = str(uuid.uuid4())
        request_file = self._request_file(request_id)
        response_file = self._response_file(request_id)

        payload = {
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        self._write_json_atomic(request_file, payload)

        start = time.time()
        while time.time() - start < self.timeout:
            if response_file.exists():
                raw = json.loads(response_file.read_text(encoding="utf-8"))
                self._safe_remove(response_file)
                if "error" in raw:
                    err = raw["error"]
                    raise LiveBridgeError("{}: {}".format(err.get("code"), err.get("message")))
                return raw.get("result")
            time.sleep(0.1)

        raise LiveBridgeError("Timed out waiting for live bridge response")

    def _request_file(self, request_id: str) -> Path:
        return self.requests_dir / f"{request_id}.json"

    def _response_file(self, request_id: str) -> Path:
        return self.responses_dir / f"{request_id}.json"

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, path)

    @staticmethod
    def _safe_remove(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
