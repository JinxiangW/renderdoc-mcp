"""Offline bootstrap adapter built on installed RenderDoc tooling."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import subprocess
import time

from renderdoc_mcp.capture_hints import load_capture_hints
from renderdoc_mcp.contracts.common import DEFAULT_MODE, Envelope
from renderdoc_mcp.context_metadata import compare_capture_contexts, load_capture_context
from renderdoc_mcp.integration.installation import RenderDocInstallation, discover_installation
from renderdoc_mcp.packet_diff import (
    compare_draw_packets,
    compare_packet_artifacts,
    compare_pass_lists,
    compare_texture_usage_artifacts,
)

from .state import ActiveCaptureState, load_state, save_state


class OfflineBootstrapAdapter:
    """Minimal offline bootstrap features using an installed RenderDoc."""

    def __init__(self) -> None:
        self._installation: RenderDocInstallation | None = None
        self._installation_checked = False

    def get_capture_status(self, directory: str | None = None) -> Envelope:
        state = load_state()
        if state is None:
            latest = self._latest_capture(Path(directory), recursive=True) if directory else None
            return {
                "ok": True,
                "mode": DEFAULT_MODE,
                "data": {
                    "loaded": False,
                    "latest": latest,
                    "latest_capture_path": latest.get("path") if latest else None,
                    "stale": bool(latest),
                    "is_latest": False if latest else None,
                },
                "err": None,
                "meta": {"cap": None, "truncated": False},
            }

        status_dir = Path(directory) if directory else Path(state.path).parent
        latest = self._latest_capture(status_dir, recursive=True) if status_dir else None
        is_latest = self._same_path(state.path, latest["path"]) if latest else None
        try:
            active_mtime = Path(state.path).stat().st_mtime
        except OSError:
            active_mtime = None
        stale = bool(latest and not is_latest and (active_mtime is None or latest["mtime_ts"] > active_mtime))

        return {
            "ok": True,
            "mode": DEFAULT_MODE,
            "data": {
                "loaded": True,
                "cap": state.cap,
                "path": state.path,
                "name": state.name,
                "size": state.size,
                "mtime": state.mtime,
                "thumb": state.thumb_path,
                "api": state.api,
                "directory": str(status_dir),
                "latest": latest,
                "latest_capture_path": latest.get("path") if latest else None,
                "latest_capture_mtime": latest.get("mtime") if latest else None,
                "is_latest": is_latest,
                "stale": stale,
            },
            "err": None,
            "meta": {"cap": state.cap, "truncated": False},
        }

    def get_capture_context(self, capture_path: str | None = None, sidecar: str | None = None) -> Envelope:
        state = load_state()
        if capture_path is None:
            if state is None:
                return {
                    "ok": False,
                    "mode": DEFAULT_MODE,
                    "data": None,
                    "err": {"code": "capture_not_loaded", "msg": "No capture loaded"},
                    "meta": {"cap": None, "truncated": False},
                }
            capture_path = state.path
            cap = state.cap
        else:
            cap = state.cap if state is not None and state.path == capture_path else None
        return load_capture_context(capture_path, cap=cap, sidecar_path=sidecar)

    def get_capture_hints(self, capture_path: str | None = None, sidecar: str | None = None) -> Envelope:
        state = load_state()
        if capture_path is None:
            if state is None:
                return {
                    "ok": False,
                    "mode": DEFAULT_MODE,
                    "data": None,
                    "err": {"code": "capture_not_loaded", "msg": "No capture loaded"},
                    "meta": {"cap": None, "truncated": False},
                }
            capture_path = state.path
            cap = state.cap
        else:
            cap = state.cap if state is not None and state.path == capture_path else None
        return load_capture_hints(capture_path, cap=cap, sidecar_path=sidecar)

    def compare_capture_contexts(
        self,
        path_a: str,
        path_b: str,
        sidecar_a: str | None = None,
        sidecar_b: str | None = None,
    ) -> Envelope:
        return compare_capture_contexts(path_a, path_b, sidecar_a, sidecar_b)

    def compare_pass_lists(self, file_a: str, file_b: str) -> Envelope:
        return compare_pass_lists(file_a, file_b)

    def compare_packet_artifacts(self, file_a: str, file_b: str) -> Envelope:
        return compare_packet_artifacts(file_a, file_b)

    def compare_draw_packets(self, file_a: str, file_b: str) -> Envelope:
        return compare_draw_packets(file_a, file_b)

    def compare_texture_usage_artifacts(self, file_a: str, file_b: str) -> Envelope:
        return compare_texture_usage_artifacts(file_a, file_b)

    def list_captures(self, root: str, limit: int = 50) -> Envelope:
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            return {
                "ok": False,
                "mode": DEFAULT_MODE,
                "data": None,
                "err": {"code": "dir_not_found", "msg": f"Directory not found: {root}"},
                "meta": {"cap": None, "truncated": False},
            }

        items: list[dict[str, object]] = []
        for path in root_path.rglob("*.rdc"):
            stat = path.stat()
            items.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        items.sort(key=lambda item: (str(item["mtime"]), str(item["name"])), reverse=True)

        total = len(items)
        truncated = total > limit
        items = items[:limit]

        return {
            "ok": True,
            "mode": DEFAULT_MODE,
            "data": {"root": str(root_path), "items": items},
            "err": None,
            "meta": {"cap": None, "truncated": truncated, "count": total},
        }

    def find_latest_capture(self, directory: str, recursive: bool = True) -> Envelope:
        root = Path(directory)
        if not root.exists() or not root.is_dir():
            return {
                "ok": False,
                "mode": DEFAULT_MODE,
                "data": None,
                "err": {"code": "dir_not_found", "msg": f"Directory not found: {directory}"},
                "meta": {"cap": None, "truncated": False},
            }

        latest = self._latest_capture(root, recursive)
        if latest is None:
            return {
                "ok": False,
                "mode": DEFAULT_MODE,
                "data": None,
                "err": {"code": "capture_not_found", "msg": f"No .rdc capture found under: {directory}"},
                "meta": {"cap": None, "truncated": False},
            }

        return {
            "ok": True,
            "mode": DEFAULT_MODE,
            "data": {"directory": str(root), "latest": latest},
            "err": None,
            "meta": {"cap": None, "truncated": False},
        }

    def load_latest_capture(self, directory: str, recursive: bool = True) -> Envelope:
        latest = self.find_latest_capture(directory, recursive)
        if not latest["ok"]:
            return latest
        result = self.open_capture(str(latest["data"]["latest"]["path"]))
        if result.get("ok") and result.get("data") is not None:
            result["data"]["selected_latest"] = latest["data"]["latest"]
        return result

    def wait_for_new_capture(
        self,
        directory: str,
        previous_path: str | None = None,
        timeout: float = 30.0,
        interval: float = 0.5,
        recursive: bool = True,
    ) -> Envelope:
        root = Path(directory)
        if previous_path is None:
            state = load_state()
            previous_path = state.path if state else None
        previous_mtime = Path(previous_path).stat().st_mtime if previous_path and Path(previous_path).exists() else None
        deadline = time.time() + timeout
        while time.time() < deadline:
            latest = self._latest_capture(root, recursive)
            if latest is not None:
                is_different = previous_path is None or not self._same_path(str(latest["path"]), previous_path)
                is_newer = previous_mtime is None or float(latest["mtime_ts"]) > previous_mtime
                if is_different and is_newer:
                    result = self.open_capture(str(latest["path"]))
                    if result.get("ok") and result.get("data") is not None:
                        result["data"]["previous_path"] = previous_path
                        result["data"]["selected_latest"] = latest
                    return result
            time.sleep(interval)

        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {"code": "timeout", "msg": "Timed out waiting for a newer capture"},
            "meta": {"cap": None, "truncated": False},
        }

    def open_capture(self, capture_path: str) -> Envelope:
        path = Path(capture_path)
        if not path.exists() or not path.is_file():
            return {
                "ok": False,
                "mode": DEFAULT_MODE,
                "data": None,
                "err": {"code": "capture_not_found", "msg": f"Capture file not found: {capture_path}"},
                "meta": {"cap": None, "truncated": False},
            }

        if path.suffix.lower() != ".rdc":
            return {
                "ok": False,
                "mode": DEFAULT_MODE,
                "data": None,
                "err": {"code": "invalid_capture_type", "msg": f"Expected .rdc file: {capture_path}"},
                "meta": {"cap": None, "truncated": False},
            }

        stat = path.stat()
        thumb_path = self._extract_thumbnail(path)

        cap_id = self._cap_id(path)
        state = ActiveCaptureState(
            cap=cap_id,
            path=str(path),
            name=path.name,
            size=stat.st_size,
            mtime=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            thumb_path=str(thumb_path) if thumb_path else None,
            api=None,
        )
        save_state(state)

        return {
            "ok": True,
            "mode": DEFAULT_MODE,
            "data": {
                "cap": state.cap,
                "path": state.path,
                "name": state.name,
                "size": state.size,
                "mtime": state.mtime,
                "thumb": state.thumb_path,
                "api": state.api,
                "verified": thumb_path is not None,
            },
            "err": None,
            "meta": {"cap": state.cap, "truncated": False},
        }

    def _extract_thumbnail(self, capture_path: Path) -> Path | None:
        installation = self._get_installation()
        if installation is None:
            return None

        out_dir = Path(".state") / "thumbs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{self._cap_id(capture_path)}.jpg"

        cmd = [
            str(installation.renderdoccmd),
            "thumb",
            "--out",
            str(out_path),
            str(capture_path),
        ]

        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )

        if completed.returncode == 0 and out_path.exists():
            return out_path

        return None

    def _get_installation(self) -> RenderDocInstallation | None:
        if not self._installation_checked:
            try:
                self._installation = discover_installation()
            except FileNotFoundError:
                self._installation = None
            self._installation_checked = True
        return self._installation

    @staticmethod
    def _cap_id(path: Path) -> str:
        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()
        return f"cap_{digest[:12]}"

    @staticmethod
    def _latest_capture(root: Path, recursive: bool = True) -> dict[str, object] | None:
        if not root.exists() or not root.is_dir():
            return None
        paths = root.rglob("*.rdc") if recursive else root.glob("*.rdc")
        latest: dict[str, object] | None = None
        for path in paths:
            if not path.is_file():
                continue
            stat = path.stat()
            item = {
                "path": str(path),
                "name": path.name,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "mtime_ts": stat.st_mtime,
            }
            if latest is None or (float(item["mtime_ts"]), str(item["name"])) > (
                float(latest["mtime_ts"]),
                str(latest["name"]),
            ):
                latest = item
        return latest

    @staticmethod
    def _same_path(left: str, right: str) -> bool:
        try:
            return Path(left).resolve() == Path(right).resolve()
        except OSError:
            return str(Path(left).absolute()).lower() == str(Path(right).absolute()).lower()
