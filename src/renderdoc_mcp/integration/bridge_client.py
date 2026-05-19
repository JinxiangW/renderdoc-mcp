"""File-based client for the qrenderdoc live bridge."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class LiveBridgeInstance:
    bridge_id: str
    ipc_dir: Path
    requests_dir: Path
    responses_dir: Path
    heartbeat_file: Path
    info_file: Path
    heartbeat_age: float
    info: dict[str, Any]


class LiveBridgeClient:
    def __init__(self, timeout: float = 20.0, bridge_id: str | None = None) -> None:
        self.timeout = timeout
        self.bridge_id = (
            bridge_id
            or os.environ.get("RENDERDOC_MCP_WINDOW_ID")
            or os.environ.get("RENDERDOC_MCP_BRIDGE_ID")
        )
        self.ipc_dir = Path(tempfile.gettempdir()) / "renderdoc_mcp_bridge"
        self.requests_dir = self.ipc_dir / "requests"
        self.responses_dir = self.ipc_dir / "responses"
        self.heartbeat_file = self.ipc_dir / "heartbeat"

    @property
    def instances_dir(self) -> Path:
        return self.ipc_dir / "instances"

    def available(self, bridge_id: str | None = None) -> bool:
        try:
            if bridge_id or self.bridge_id:
                self._select_instance(bridge_id)
                return True
            return bool(self.list_instances())
        except LiveBridgeError:
            return False

    def list_instances(self) -> list[LiveBridgeInstance]:
        instances: list[LiveBridgeInstance] = []

        legacy = self._instance_from_paths(
            bridge_id="legacy",
            ipc_dir=self.ipc_dir,
            requests_dir=self.requests_dir,
            responses_dir=self.responses_dir,
            heartbeat_file=self.heartbeat_file,
            info_file=self.ipc_dir / "info.json",
        )
        if legacy is not None:
            instances.append(legacy)

        try:
            children = list(self.instances_dir.iterdir())
        except OSError:
            children = []

        for child in children:
            if not child.is_dir():
                continue
            instance = self._instance_from_paths(
                bridge_id=child.name,
                ipc_dir=child,
                requests_dir=child / "requests",
                responses_dir=child / "responses",
                heartbeat_file=child / "heartbeat",
                info_file=child / "info.json",
            )
            if instance is not None:
                instances.append(instance)

        instances.sort(key=lambda item: float(item.info.get("updated_at") or 0.0), reverse=True)
        return instances

    def list_windows(self) -> dict[str, Any]:
        windows = [self._window_summary(instance) for instance in self.list_instances()]
        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "count": len(windows),
                "windows": windows,
            },
            "err": None,
            "meta": {"cap": None, "truncated": False},
        }

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        bridge_id: str | None = None,
        window_id: str | None = None,
    ) -> Any:
        instance = self._select_instance(window_id or bridge_id)

        request_id = str(uuid.uuid4())
        request_file = self._request_file(request_id, instance)
        response_file = self._response_file(request_id, instance)

        payload = {
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        self._safe_remove(response_file)
        self._write_json_atomic(request_file, payload)

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

    def _select_instance(self, bridge_id: str | None = None) -> LiveBridgeInstance:
        requested = bridge_id or self.bridge_id
        instances = self.list_instances()

        if requested:
            for instance in instances:
                aliases = {
                    instance.bridge_id,
                    str(instance.info.get("bridge_id") or ""),
                    str(instance.info.get("window_id") or ""),
                }
                if requested in aliases:
                    return instance
            raise LiveBridgeError("Live qrenderdoc bridge not found: {}".format(requested))

        if len(instances) == 1:
            return instances[0]
        if not instances:
            raise LiveBridgeError("Live qrenderdoc bridge is not available")

        ids = ", ".join(instance.bridge_id for instance in instances)
        raise LiveBridgeError(
            "Multiple live qrenderdoc bridges are available; pass window_id. Active window_ids: {}".format(ids)
        )

    def _instance_from_paths(
        self,
        bridge_id: str,
        ipc_dir: Path,
        requests_dir: Path,
        responses_dir: Path,
        heartbeat_file: Path,
        info_file: Path,
    ) -> LiveBridgeInstance | None:
        try:
            ts = float(heartbeat_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

        heartbeat_age = time.time() - ts
        if heartbeat_age >= HEARTBEAT_STALE_SECONDS:
            return None

        info: dict[str, Any] = {}
        try:
            raw_info = json.loads(info_file.read_text(encoding="utf-8"))
            if isinstance(raw_info, dict):
                info = raw_info
        except (OSError, ValueError, json.JSONDecodeError):
            pass

        instance_id = str(info.get("window_id") or info.get("bridge_id") or bridge_id)
        return LiveBridgeInstance(
            bridge_id=instance_id,
            ipc_dir=ipc_dir,
            requests_dir=requests_dir,
            responses_dir=responses_dir,
            heartbeat_file=heartbeat_file,
            info_file=info_file,
            heartbeat_age=heartbeat_age,
            info=info,
        )

    @staticmethod
    def _window_summary(instance: LiveBridgeInstance) -> dict[str, Any]:
        info = instance.info
        summary: dict[str, Any] = {
            "window_id": instance.bridge_id,
            "bridge_id": instance.bridge_id,
            "pid": info.get("pid"),
            "loaded": bool(info.get("loaded", False)),
            "capture_path": info.get("capture_path"),
            "api": info.get("api"),
            "started_at": info.get("started_at"),
            "updated_at": info.get("updated_at"),
            "heartbeat_age_seconds": round(instance.heartbeat_age, 3),
        }
        if info.get("status_error"):
            summary["status_error"] = info.get("status_error")
        return summary

    def _request_file(self, request_id: str, instance: LiveBridgeInstance | None = None) -> Path:
        requests_dir = instance.requests_dir if instance is not None else self.requests_dir
        return requests_dir / f"{request_id}.json"

    def _response_file(self, request_id: str, instance: LiveBridgeInstance | None = None) -> Path:
        responses_dir = instance.responses_dir if instance is not None else self.responses_dir
        return responses_dir / f"{request_id}.json"

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
