"""Offline bootstrap adapter built on installed RenderDoc tooling."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import subprocess

from renderdoc_mcp.contracts.common import DEFAULT_MODE, Envelope
from renderdoc_mcp.integration.installation import discover_installation

from .state import ActiveCaptureState, load_state, save_state


class OfflineBootstrapAdapter:
    """Minimal offline bootstrap features using an installed RenderDoc."""

    def __init__(self) -> None:
        self.installation = discover_installation()

    def get_capture_status(self) -> Envelope:
        state = load_state()
        if state is None:
            return {
                "ok": True,
                "mode": DEFAULT_MODE,
                "data": {"loaded": False},
                "err": None,
                "meta": {"cap": None, "truncated": False},
            }

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
            },
            "err": None,
            "meta": {"cap": state.cap, "truncated": False},
        }

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
        out_dir = Path(".state") / "thumbs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{self._cap_id(capture_path)}.jpg"

        cmd = [
            str(self.installation.renderdoccmd),
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

    @staticmethod
    def _cap_id(path: Path) -> str:
        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()
        return f"cap_{digest[:12]}"
