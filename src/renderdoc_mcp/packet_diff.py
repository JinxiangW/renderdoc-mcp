"""Helpers for comparing compact packet artifacts."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from renderdoc_mcp.contracts.common import DEFAULT_MODE, Envelope


def compare_packet_artifacts(file_a: str | Path, file_b: str | Path) -> Envelope:
    left = _load_json_artifact(file_a)
    if not left.get("ok"):
        return left

    right = _load_json_artifact(file_b)
    if not right.get("ok"):
        return right

    left_payload = left["data"]["payload"]
    right_payload = right["data"]["payload"]
    changes = _collect_json_changes(left_payload, right_payload, ())

    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "a": {"path": str(file_a)},
            "b": {"path": str(file_b)},
            "summary": {
                "changed": len(changes),
            },
            "changes": changes,
        },
        "err": None,
        "meta": {"cap": None, "truncated": False, "count": len(changes)},
    }


def compare_draw_packets(file_a: str | Path, file_b: str | Path) -> Envelope:
    left = _load_json_artifact(file_a)
    if not left.get("ok"):
        return left

    right = _load_json_artifact(file_b)
    if not right.get("ok"):
        return right

    left_payload = _extract_packet_payload(left["data"]["payload"])
    right_payload = _extract_packet_payload(right["data"]["payload"])
    if left_payload is None or right_payload is None:
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {
                "code": "artifact_invalid",
                "msg": "Artifact does not contain a recognizable compact packet payload",
            },
            "meta": {"cap": None, "truncated": False},
        }

    changes = _collect_json_changes(left_payload, right_payload, ())

    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "a": {
                "path": str(file_a),
                "packet": _draw_packet_overview(left_payload),
            },
            "b": {
                "path": str(file_b),
                "packet": _draw_packet_overview(right_payload),
            },
            "summary": {
                "changed": len(changes),
                "shader_changed": _shader_ref(left_payload) != _shader_ref(right_payload),
                "io_changed": _io_summary(left_payload) != _io_summary(right_payload),
                "counts_changed": left_payload.get("counts") != right_payload.get("counts"),
            },
            "changes": changes,
        },
        "err": None,
        "meta": {"cap": None, "truncated": False, "count": len(changes)},
    }


def compare_texture_usage_artifacts(file_a: str | Path, file_b: str | Path) -> Envelope:
    left = _load_json_artifact(file_a)
    if not left.get("ok"):
        return left

    right = _load_json_artifact(file_b)
    if not right.get("ok"):
        return right

    left_payload = _extract_packet_payload(left["data"]["payload"])
    right_payload = _extract_packet_payload(right["data"]["payload"])
    if left_payload is None or right_payload is None:
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {
                "code": "artifact_invalid",
                "msg": "Artifact does not contain a recognizable compact packet payload",
            },
            "meta": {"cap": None, "truncated": False},
        }

    changes = _collect_json_changes(left_payload, right_payload, ())

    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "a": {
                "path": str(file_a),
                "packet": _texture_usage_overview(left_payload),
            },
            "b": {
                "path": str(file_b),
                "packet": _texture_usage_overview(right_payload),
            },
            "summary": {
                "changed": len(changes),
                "uses_changed": left_payload.get("uses") != right_payload.get("uses"),
                "producer_changed": left_payload.get("producer") != right_payload.get("producer"),
                "first_read_changed": left_payload.get("first_read") != right_payload.get("first_read"),
                "last_write_changed": left_payload.get("last_write") != right_payload.get("last_write"),
            },
            "changes": changes,
        },
        "err": None,
        "meta": {"cap": None, "truncated": False, "count": len(changes)},
    }


def compare_pass_lists(file_a: str | Path, file_b: str | Path) -> Envelope:
    left = _load_pass_list_artifact(file_a)
    if not left.get("ok"):
        return left

    right = _load_pass_list_artifact(file_b)
    if not right.get("ok"):
        return right

    left_items = left["data"]["items"]
    right_items = right["data"]["items"]
    left_index = _index_pass_items(left_items)
    right_index = _index_pass_items(right_items)

    added = []
    removed = []
    changed = []
    unchanged = 0

    keys = sorted(set(left_index.keys()) | set(right_index.keys()))
    for key in keys:
        left_item = left_index.get(key)
        right_item = right_index.get(key)
        pass_name, occurrence = key
        if left_item is None:
            added.append({"pass": pass_name, "occurrence": occurrence, "b": right_item})
            continue
        if right_item is None:
            removed.append({"pass": pass_name, "occurrence": occurrence, "a": left_item})
            continue

        item_changes = _compare_dicts(left_item, right_item)
        if item_changes:
            changed.append(
                {
                    "pass": pass_name,
                    "occurrence": occurrence,
                    "changes": item_changes,
                    "a": left_item,
                    "b": right_item,
                }
            )
        else:
            unchanged += 1

    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "a": {
                "path": str(file_a),
                "count": len(left_items),
            },
            "b": {
                "path": str(file_b),
                "count": len(right_items),
            },
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "unchanged": unchanged,
            },
            "added": added,
            "removed": removed,
            "changed": changed,
        },
        "err": None,
        "meta": {"cap": None, "truncated": False, "count": len(added) + len(removed) + len(changed)},
    }


def _load_pass_list_artifact(path: str | Path) -> Envelope:
    loaded = _load_json_artifact(path)
    if not loaded.get("ok"):
        return loaded

    payload = loaded["data"]["payload"]
    file_path = loaded["data"]["path"]
    items = _extract_pass_items(payload)
    if items is None:
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {
                "code": "artifact_invalid",
                "msg": "Artifact does not contain a recognizable pass list or frame packet payload",
            },
            "meta": {"cap": None, "truncated": False},
        }

    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "path": str(file_path),
            "items": items,
        },
        "err": None,
        "meta": {"cap": None, "truncated": False, "count": len(items)},
    }


def _load_json_artifact(path: str | Path) -> Envelope:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {"code": "artifact_not_found", "msg": f"Artifact file not found: {file_path}"},
            "meta": {"cap": None, "truncated": False},
        }

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "mode": DEFAULT_MODE,
            "data": None,
            "err": {"code": "artifact_invalid", "msg": str(exc)},
            "meta": {"cap": None, "truncated": False},
        }

    return {
        "ok": True,
        "mode": DEFAULT_MODE,
        "data": {
            "path": str(file_path),
            "payload": payload,
        },
        "err": None,
        "meta": {"cap": None, "truncated": False},
    }


def _extract_pass_items(payload: Any) -> list[dict[str, Any]] | None:
    if not isinstance(payload, dict):
        return None

    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return None

    raw_items = None
    if isinstance(data.get("items"), list):
        raw_items = data.get("items")
    elif isinstance(data.get("passes"), list):
        raw_items = data.get("passes")

    if raw_items is None:
        return None

    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        pass_name = item.get("pass") or item.get("name")
        if not pass_name:
            continue
        items.append(
            {
                "eid": item.get("eid"),
                "pass": str(pass_name),
                "stats": item.get("stats"),
            }
        )
    return items


def _extract_packet_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return None
    recognized_keys = {
        "eid",
        "shader",
        "pipe",
        "io",
        "rid",
        "uses",
        "items",
        "producer",
        "last_write",
        "first_read",
    }
    if not any(key in data for key in recognized_keys):
        return None
    return data


def _index_pass_items(items: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    counts: dict[str, int] = {}
    indexed: dict[tuple[str, int], dict[str, Any]] = {}
    for item in items:
        pass_name = str(item.get("pass") or "")
        counts[pass_name] = counts.get(pass_name, 0) + 1
        occurrence = counts[pass_name]
        indexed[(pass_name, occurrence)] = item
    return indexed


def _compare_dicts(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    keys = sorted(set(left.keys()) | set(right.keys()), key=lambda value: str(value))
    for key in keys:
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value == right_value:
            continue
        if isinstance(left_value, dict) and isinstance(right_value, dict):
            for child in _compare_dicts(left_value, right_value):
                child_path = "{}.{}".format(key, child["path"]) if child.get("path") else str(key)
                changes.append(
                    {
                        "path": child_path,
                        "a": child.get("a"),
                        "b": child.get("b"),
                    }
                )
            continue
        changes.append({"path": str(key), "a": left_value, "b": right_value})
    return changes


def _collect_json_changes(left: Any, right: Any, prefix: tuple[str, ...]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left.keys()) | set(right.keys()), key=lambda value: str(value))
        for key in keys:
            key_text = str(key)
            next_prefix = prefix + (key_text,)
            if key not in left:
                changes.append({"path": ".".join(next_prefix), "type": "added", "b": right[key]})
            elif key not in right:
                changes.append({"path": ".".join(next_prefix), "type": "removed", "a": left[key]})
            else:
                changes.extend(_collect_json_changes(left[key], right[key], next_prefix))
        return changes

    if isinstance(left, list) and isinstance(right, list):
        if left != right:
            changes.append({"path": ".".join(prefix), "type": "changed", "a": left, "b": right})
        return changes

    if left != right:
        changes.append({"path": ".".join(prefix), "type": "changed", "a": left, "b": right})

    return changes


def _shader_ref(packet: dict[str, Any]) -> dict[str, Any] | None:
    shader = packet.get("shader")
    if not isinstance(shader, dict):
        return None
    shader_info = shader.get("shader", shader)
    if not isinstance(shader_info, dict):
        return None
    return {
        "name": shader_info.get("name"),
        "entry": shader_info.get("entry"),
        "stage": shader.get("stage"),
    }


def _io_summary(packet: dict[str, Any]) -> dict[str, Any]:
    io = packet.get("io")
    if not isinstance(io, dict):
        return {}
    return {
        "in_tex": len(io.get("in_tex", []) or []),
        "out_rt": len(io.get("out_rt", []) or []),
        "out_uav": len(io.get("out_uav", []) or []),
        "out_next": len(io.get("out_next", []) or []),
        "out_ds": io.get("out_ds") is not None,
    }


def _draw_packet_overview(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "eid": packet.get("eid"),
        "name": packet.get("name"),
        "type": packet.get("type"),
        "counts": packet.get("counts"),
        "shader": _shader_ref(packet),
        "io": _io_summary(packet),
    }


def _texture_usage_overview(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "rid": packet.get("rid"),
        "name": packet.get("name"),
        "uses": packet.get("uses"),
        "producer": packet.get("producer"),
        "last_write": packet.get("last_write"),
        "first_read": packet.get("first_read"),
        "first_ps_read": packet.get("first_ps_read"),
        "item_count": len(packet.get("items", []) or []),
    }
