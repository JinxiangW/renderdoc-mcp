"""Offline bootstrap adapter built on installed RenderDoc tooling."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import subprocess

from renderdoc_mcp.contracts.common import Envelope, ErrorInfo, MetaInfo
from renderdoc_mcp.integration.installation import discover_installation

from .state import ActiveCaptureState, load_state, save_state


class OfflineBootstrapAdapter:
    """Minimal offline bootstrap features using an installed RenderDoc."""

    def __init__(self) -> None:
        self.installation = discover_installation()

    def get_capture_status(self) -> Envelope:
        state = load_state()
        if state is None:
            return Envelope(
                ok=True,
                data={"loaded": False},
                meta=MetaInfo(cap=None, truncated=False),
            )

        return Envelope(
            ok=True,
            data={
                "loaded": True,
                "cap": state.cap,
                "path": state.path,
                "name": state.name,
                "size": state.size,
                "mtime": state.mtime,
                "thumb": state.thumb_path,
                "api": state.api,
            },
            meta=MetaInfo(cap=state.cap, truncated=False),
        )

    def list_captures(self, root: str, limit: int = 50) -> Envelope:
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            return Envelope(
                ok=False,
                data=None,
                err=ErrorInfo("dir_not_found", f"Directory not found: {root}"),
                meta=MetaInfo(cap=None, truncated=False),
            )

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

        return Envelope(
            ok=True,
            data={"root": str(root_path), "items": items},
            meta=MetaInfo(cap=None, truncated=truncated, count=total),
        )

    def open_capture(self, capture_path: str) -> Envelope:
        path = Path(capture_path)
        if not path.exists() or not path.is_file():
            return Envelope(
                ok=False,
                data=None,
                err=ErrorInfo("capture_not_found", f"Capture file not found: {capture_path}"),
                meta=MetaInfo(cap=None, truncated=False),
            )

        if path.suffix.lower() != ".rdc":
            return Envelope(
                ok=False,
                data=None,
                err=ErrorInfo("invalid_capture_type", f"Expected .rdc file: {capture_path}"),
                meta=MetaInfo(cap=None, truncated=False),
            )

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

        return Envelope(
            ok=True,
            data={
                "cap": state.cap,
                "path": state.path,
                "name": state.name,
                "size": state.size,
                "mtime": state.mtime,
                "thumb": state.thumb_path,
                "api": state.api,
                "verified": thumb_path is not None,
            },
            meta=MetaInfo(cap=state.cap, truncated=False),
        )

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
