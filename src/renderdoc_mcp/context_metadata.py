"""Capture-context sidecar loading helpers."""

from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime
from typing import Any

from renderdoc_mcp.contracts.common import DEFAULT_MODE, Envelope


def load_capture_context(
    capture_path: str | Path,
    cap: str | None = None,
    sidecar_path: str | Path | None = None,
) -> Envelope:
    path = Path(capture_path)
    if not path.exists() or not path.is_file():
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {"code": "capture_not_found", "msg": f"Capture file not found: {path}"},
            "meta": {"cap": cap, "truncated": False},
        }

    candidates = _candidate_sidecars(path, sidecar_path)
    selected = next((candidate for candidate in candidates if candidate.exists() and candidate.is_file()), None)
    if selected is None:
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {
                "code": "capture_context_not_found",
                "msg": "No capture context sidecar was found for the selected capture",
            },
            "meta": {"cap": cap, "truncated": False},
        }

    try:
        ctx = json.loads(selected.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {"code": "capture_context_invalid", "msg": str(exc)},
            "meta": {"cap": cap, "truncated": False},
        }

    if not isinstance(ctx, dict):
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {"code": "capture_context_invalid", "msg": "Capture context sidecar must contain a JSON object"},
            "meta": {"cap": cap, "truncated": False},
        }

    keys = sorted(str(key) for key in ctx.keys())
    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "cap": cap,
            "capture": {
                "path": str(path),
                "name": path.name,
            },
            "sidecar": {
                "path": str(selected),
                "keys": keys,
            },
            "ctx": ctx,
        },
        "err": None,
        "meta": {"cap": cap, "truncated": False},
    }


def compare_capture_contexts(
    path_a: str | Path,
    path_b: str | Path,
    sidecar_a: str | Path | None = None,
    sidecar_b: str | Path | None = None,
) -> Envelope:
    left = load_capture_context(path_a, sidecar_path=sidecar_a)
    if not left.get("ok"):
        return left

    right = load_capture_context(path_b, sidecar_path=sidecar_b)
    if not right.get("ok"):
        return right

    left_data = left.get("data") or {}
    right_data = right.get("data") or {}
    left_ctx = left_data.get("ctx") or {}
    right_ctx = right_data.get("ctx") or {}

    changes = []
    _collect_context_changes(left_ctx, right_ctx, (), changes)

    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "a": {
                "capture": left_data.get("capture"),
                "sidecar": left_data.get("sidecar"),
                "meta": _capture_file_meta(path_a),
            },
            "b": {
                "capture": right_data.get("capture"),
                "sidecar": right_data.get("sidecar"),
                "meta": _capture_file_meta(path_b),
            },
            "summary": {
                "changed": len(changes),
                "top_keys_a": left_data.get("sidecar", {}).get("keys", []),
                "top_keys_b": right_data.get("sidecar", {}).get("keys", []),
            },
            "changes": changes,
        },
        "err": None,
        "meta": {"cap": None, "truncated": False, "count": len(changes)},
    }


def _capture_file_meta(capture_path: str | Path) -> dict[str, Any]:
    path = Path(capture_path)
    stat = path.stat()
    return {
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def _collect_context_changes(left: Any, right: Any, prefix: tuple[str, ...], out: list[dict[str, Any]]) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left.keys()) | set(right.keys()), key=lambda value: str(value))
        for key in keys:
            key_text = str(key)
            next_prefix = prefix + (key_text,)
            if key not in left:
                out.append({"path": ".".join(next_prefix), "type": "added", "b": right[key]})
            elif key not in right:
                out.append({"path": ".".join(next_prefix), "type": "removed", "a": left[key]})
            else:
                _collect_context_changes(left[key], right[key], next_prefix, out)
        return

    if isinstance(left, list) and isinstance(right, list):
        if left != right:
            out.append({"path": ".".join(prefix), "type": "changed", "a": left, "b": right})
        return

    if left != right:
        out.append({"path": ".".join(prefix), "type": "changed", "a": left, "b": right})


def _candidate_sidecars(capture_path: Path, sidecar_path: str | Path | None = None) -> list[Path]:
    if sidecar_path is not None:
        return [Path(sidecar_path)]

    return [
        capture_path.with_suffix(capture_path.suffix + ".context.json"),
        capture_path.with_suffix(".context.json"),
        capture_path.with_suffix(capture_path.suffix + ".meta.json"),
        capture_path.with_suffix(".meta.json"),
        capture_path.parent / (capture_path.name + ".context.json"),
        capture_path.parent / (capture_path.stem + ".context.json"),
    ]
