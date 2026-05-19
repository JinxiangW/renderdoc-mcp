"""UE semantic hint helpers derived from capture-context sidecars."""

from __future__ import annotations

from typing import Any

from renderdoc_mcp.context_metadata import load_capture_context
from renderdoc_mcp.contracts.common import DEFAULT_MODE, Envelope


def load_capture_hints(
    capture_path: str,
    cap: str | None = None,
    sidecar_path: str | None = None,
    packet_kind: str | None = None,
    packet: dict[str, Any] | None = None,
) -> Envelope:
    loaded = load_capture_context(capture_path, cap=cap, sidecar_path=sidecar_path)
    if not loaded.get("ok"):
        return loaded

    data = loaded.get("data") or {}
    ctx = data.get("ctx") or {}
    hints = summarize_capture_hints(ctx, packet_kind=packet_kind, packet=packet)
    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "cap": data.get("cap"),
            "capture": data.get("capture"),
            "sidecar": data.get("sidecar"),
            "hints": hints,
        },
        "err": None,
        "meta": {"cap": cap, "truncated": False},
    }


def summarize_capture_hints(
    ctx: dict[str, Any],
    packet_kind: str | None = None,
    packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hints = {
        "engine": _pick_dict(ctx.get("engine"), ["project", "build", "rhi", "shader_platform", "feature_level"]),
        "scene": _pick_dict(ctx.get("scene"), ["map", "world"]),
        "capture": _pick_dict(ctx.get("capture"), ["reason", "frame_hint", "user_note"]),
        "selection": _pick_dict(ctx.get("selection"), ["actor", "component", "material", "asset"]),
        "rdg": _pick_dict(ctx.get("rdg"), ["focus_pass", "pass_filters"]),
    }
    hints["matches"] = _packet_match_hints(hints, packet_kind=packet_kind, packet=packet)
    return hints


def attach_capture_hints(
    result: dict[str, Any],
    capture_path: str,
    cap: str | None = None,
    sidecar_path: str | None = None,
    packet_kind: str | None = None,
) -> dict[str, Any]:
    if not result.get("ok"):
        return result

    packet = result.get("data")
    if not isinstance(packet, dict):
        return result

    loaded = load_capture_hints(
        capture_path,
        cap=cap,
        sidecar_path=sidecar_path,
        packet_kind=packet_kind,
        packet=packet,
    )
    if not loaded.get("ok"):
        return result

    enriched = dict(result)
    enriched_data = dict(packet)
    enriched_data["ue"] = loaded["data"]["hints"]
    enriched["data"] = enriched_data
    return enriched


def _pick_dict(value: Any, keys: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    picked = {key: value[key] for key in keys if key in value}
    return picked or None


def _packet_match_hints(
    hints: dict[str, Any],
    packet_kind: str | None = None,
    packet: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(packet, dict):
        return None

    matches: dict[str, Any] = {}
    rdg = hints.get("rdg") or {}
    focus_pass = rdg.get("focus_pass")
    packet_pass = _packet_pass_name(packet_kind, packet)
    if focus_pass:
        matches["focus_pass"] = focus_pass
        matches["packet_pass"] = packet_pass
        matches["focus_pass_match"] = bool(packet_pass) and str(focus_pass).lower() in str(packet_pass).lower()

    selection = hints.get("selection") or {}
    if selection:
        matches["selection_present"] = True
        if selection.get("material"):
            matches["selection_material"] = selection.get("material")

    return matches or None


def _packet_pass_name(packet_kind: str | None, packet: dict[str, Any]) -> str | None:
    if packet_kind == "pass":
        pass_info = packet.get("pass")
        if isinstance(pass_info, dict):
            return pass_info.get("pass") or pass_info.get("name")
    if packet_kind == "draw":
        context = packet.get("context")
        if isinstance(context, dict):
            root_pass = context.get("root_pass") or {}
            parent_pass = context.get("parent_pass") or {}
            return root_pass.get("pass") or parent_pass.get("pass") or context.get("marker_path")
    return None
