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
        self.request_file = self.ipc_dir / "request.json"
        self.response_file = self.ipc_dir / "response.json"
        self.lock_file = self.ipc_dir / "lock"
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
        payload = {
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        if self._modern_ipc_available():
            return self._call_modern(request_id, payload)
        return self._call_legacy(payload)

    def _modern_ipc_available(self) -> bool:
        return self.requests_dir.exists() and self.responses_dir.exists()

    def _call_modern(self, request_id: str, payload: dict[str, Any]) -> Any:
        request_file = self.requests_dir / f"{request_id}.json"
        response_file = self.responses_dir / f"{request_id}.json"

        self._safe_remove(response_file)
        self._atomic_write_json(request_file, payload)

        start = time.time()
        while time.time() - start < self.timeout:
            if response_file.exists():
                raw = self._read_json_retry(response_file)
                self._safe_remove(response_file)
                if "error" in raw:
                    err = raw["error"]
                    raise LiveBridgeError("{}: {}".format(err.get("code"), err.get("message")))
                return raw.get("result")
            time.sleep(0.1)

        self._safe_remove(request_file)
        raise LiveBridgeError("Timed out waiting for live bridge response")

    def _call_legacy(self, payload: dict[str, Any]) -> Any:
        self._safe_remove(self.response_file)

        self._acquire_write_slot()
        try:
            self._atomic_write_json(self.request_file, payload)
        finally:
            self._safe_remove(self.lock_file)

        start = time.time()
        while time.time() - start < self.timeout:
            if self.response_file.exists():
                raw = self._read_json_retry(self.response_file)
                self._safe_remove(self.response_file)
                if raw.get("id") not in (None, payload["id"]):
                    time.sleep(0.05)
                    continue
                if "error" in raw:
                    err = raw["error"]
                    raise LiveBridgeError("{}: {}".format(err.get("code"), err.get("message")))
                return raw.get("result")
            time.sleep(0.1)

        raise LiveBridgeError("Timed out waiting for live bridge response")

    @staticmethod
    def _safe_remove(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)

    @staticmethod
    def _read_json_retry(path: Path) -> Any:
        last_error: json.JSONDecodeError | None = None
        for _ in range(5):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                last_error = exc
                time.sleep(0.05)
        if last_error is not None:
            raise last_error
        return json.loads(path.read_text(encoding="utf-8"))
