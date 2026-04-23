"""MCP-facing runtime for the implemented offline bootstrap tools."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from renderdoc_mcp.capture_hints import attach_capture_hints, load_capture_hints
from renderdoc_mcp.context_metadata import compare_capture_contexts, load_capture_context
from renderdoc_mcp.integration import LiveBridgeClient

from .app import LIVE_BRIDGE_TOOLS, OFFLINE_BOOTSTRAP_TOOLS
from .offline_bootstrap import OfflineBootstrapTools

ToolHandler = Callable[[dict[str, Any]], Any]


class OfflineToolRegistry:
    """Registry for the implemented offline bootstrap tools."""

    def __init__(self, tools: OfflineBootstrapTools | None = None) -> None:
        self.tools = tools or OfflineBootstrapTools()
        self.handlers: dict[str, ToolHandler] = {
            "get_capture_status": self._get_capture_status,
            "get_capture_context": self._get_capture_context,
            "get_capture_hints": self._get_capture_hints,
            "compare_capture_contexts": self._compare_capture_contexts,
            "compare_pass_lists": self._compare_pass_lists,
            "compare_packet_artifacts": self._compare_packet_artifacts,
            "compare_draw_packets": self._compare_draw_packets,
            "compare_texture_usage_artifacts": self._compare_texture_usage_artifacts,
            "list_captures": self._list_captures,
            "open_capture": self._open_capture,
            "find_latest_capture": self._find_latest_capture,
            "load_latest_capture": self._load_latest_capture,
            "wait_for_new_capture": self._wait_for_new_capture,
        }

    def invoke(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if method not in self.handlers:
            raise KeyError(f"Unknown tool: {method}")
        return self.handlers[method](params or {})

    def _get_capture_status(self, params: dict[str, Any]) -> Any:
        directory = params.get("directory") or params.get("root")
        return self.tools.get_capture_status(str(directory) if directory else None)

    def _get_capture_context(self, params: dict[str, Any]) -> Any:
        path = params.get("path")
        sidecar = params.get("sidecar")
        return self.tools.get_capture_context(str(path) if path else None, str(sidecar) if sidecar else None)

    def _get_capture_hints(self, params: dict[str, Any]) -> Any:
        path = params.get("path")
        sidecar = params.get("sidecar")
        return self.tools.get_capture_hints(str(path) if path else None, str(sidecar) if sidecar else None)

    def _compare_capture_contexts(self, params: dict[str, Any]) -> Any:
        path_a = params.get("path_a")
        path_b = params.get("path_b")
        if not path_a or not path_b:
            raise ValueError("path_a and path_b are required")
        sidecar_a = params.get("sidecar_a")
        sidecar_b = params.get("sidecar_b")
        return self.tools.compare_capture_contexts(
            str(path_a),
            str(path_b),
            str(sidecar_a) if sidecar_a else None,
            str(sidecar_b) if sidecar_b else None,
        )

    def _compare_pass_lists(self, params: dict[str, Any]) -> Any:
        file_a = params.get("file_a")
        file_b = params.get("file_b")
        if not file_a or not file_b:
            raise ValueError("file_a and file_b are required")
        return self.tools.compare_pass_lists(str(file_a), str(file_b))

    def _compare_packet_artifacts(self, params: dict[str, Any]) -> Any:
        file_a = params.get("file_a")
        file_b = params.get("file_b")
        if not file_a or not file_b:
            raise ValueError("file_a and file_b are required")
        return self.tools.compare_packet_artifacts(str(file_a), str(file_b))

    def _compare_draw_packets(self, params: dict[str, Any]) -> Any:
        file_a = params.get("file_a")
        file_b = params.get("file_b")
        if not file_a or not file_b:
            raise ValueError("file_a and file_b are required")
        return self.tools.compare_draw_packets(str(file_a), str(file_b))

    def _compare_texture_usage_artifacts(self, params: dict[str, Any]) -> Any:
        file_a = params.get("file_a")
        file_b = params.get("file_b")
        if not file_a or not file_b:
            raise ValueError("file_a and file_b are required")
        return self.tools.compare_texture_usage_artifacts(str(file_a), str(file_b))

    def _list_captures(self, params: dict[str, Any]) -> Any:
        root = params.get("root")
        if not root:
            raise ValueError("root is required")
        limit = int(params.get("limit", 50))
        return self.tools.list_captures(str(root), limit)

    def _open_capture(self, params: dict[str, Any]) -> Any:
        path = params.get("path")
        if not path:
            raise ValueError("path is required")
        return self.tools.open_capture(str(path))

    def _find_latest_capture(self, params: dict[str, Any]) -> Any:
        directory = params.get("directory") or params.get("root")
        if not directory:
            raise ValueError("directory is required")
        return self.tools.find_latest_capture(str(directory), bool(params.get("recursive", True)))

    def _load_latest_capture(self, params: dict[str, Any]) -> Any:
        directory = params.get("directory") or params.get("root")
        if not directory:
            raise ValueError("directory is required")
        return self.tools.load_latest_capture(str(directory), bool(params.get("recursive", True)))

    def _wait_for_new_capture(self, params: dict[str, Any]) -> Any:
        directory = params.get("directory") or params.get("root")
        if not directory:
            raise ValueError("directory is required")
        return self.tools.wait_for_new_capture(
            str(directory),
            str(params["previous_path"]) if params.get("previous_path") else None,
            float(params.get("timeout", 30.0) or 30.0),
            float(params.get("interval", 0.5) or 0.5),
            bool(params.get("recursive", True)),
        )


class LiveToolRegistry:
    """Registry for live qrenderdoc bridge tools."""

    def __init__(self, client: LiveBridgeClient | None = None) -> None:
        self.client = client or LiveBridgeClient()
        self.handlers: dict[str, ToolHandler] = {
            "get_capture_status": self._get_capture_status,
            "open_capture": self._open_capture,
            "find_latest_capture": self._find_latest_capture,
            "load_latest_capture": self._load_latest_capture,
            "wait_for_new_capture": self._wait_for_new_capture,
            "get_capture_context": self._get_capture_context,
            "get_capture_hints": self._get_capture_hints,
            "compare_capture_contexts": self._compare_capture_contexts,
            "find_events": self._find_events,
            "list_passes": self._list_passes,
            "get_frame_packet": self._get_frame_packet,
            "get_pass_packet": self._get_pass_packet,
            "get_draw_packet": self._get_draw_packet,
            "debug_save_overlay": self._debug_save_overlay,
            "debug_save_texture": self._debug_save_texture,
            "inspect_pipeline_state": self._inspect_pipeline_state,
            "inspect_shader": self._inspect_shader,
            "inspect_cbuffer_values": self._inspect_cbuffer_values,
            "read_buffer": self._read_buffer,
            "get_shader_disasm": self._get_shader_disasm,
            "get_shader_source": self._get_shader_source,
            "get_shader_code": self._get_shader_code,
            "inspect_texture_usage": self._inspect_texture_usage,
            "inspect_mesh": self._inspect_mesh,
        }

    def invoke(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if method not in self.handlers:
            raise KeyError("Unknown live tool: {}".format(method))
        return self.handlers[method](params or {})

    def available(self) -> bool:
        return self.client.available()

    def require(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.available():
            raise RuntimeError("Live qrenderdoc bridge is not available")
        return self.invoke(method, params or {})

    def _get_capture_status(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_capture_status", params)

    def _open_capture(self, params: dict[str, Any]) -> Any:
        return self.client.call("open_capture", params)

    def _find_latest_capture(self, params: dict[str, Any]) -> Any:
        return self.client.call("find_latest_capture", params)

    def _load_latest_capture(self, params: dict[str, Any]) -> Any:
        return self.client.call("load_latest_capture", params)

    def _wait_for_new_capture(self, params: dict[str, Any]) -> Any:
        return self.client.call("wait_for_new_capture", params)

    def _get_capture_context(self, params: dict[str, Any]) -> Any:
        explicit_path = params.get("path")
        sidecar = params.get("sidecar")
        if explicit_path:
            return load_capture_context(str(explicit_path), sidecar_path=str(sidecar) if sidecar else None)

        status = self.client.call("get_capture_status")
        if not status.get("ok"):
            return status
        data = status.get("data") or {}
        if not data.get("loaded"):
            return _error_envelope("capture_not_loaded", "No capture loaded", cap="active")
        return load_capture_context(
            str(data.get("path")),
            cap=str(data.get("cap")) if data.get("cap") is not None else "active",
            sidecar_path=str(sidecar) if sidecar else None,
        )

    def _get_capture_hints(self, params: dict[str, Any]) -> Any:
        explicit_path = params.get("path")
        sidecar = params.get("sidecar")
        if explicit_path:
            return load_capture_hints(str(explicit_path), sidecar_path=str(sidecar) if sidecar else None)

        status = self.client.call("get_capture_status")
        if not status.get("ok"):
            return status
        data = status.get("data") or {}
        if not data.get("loaded"):
            return _error_envelope("capture_not_loaded", "No capture loaded", cap="active")
        return load_capture_hints(
            str(data.get("path")),
            cap=str(data.get("cap")) if data.get("cap") is not None else "active",
            sidecar_path=str(sidecar) if sidecar else None,
        )

    def _compare_capture_contexts(self, params: dict[str, Any]) -> Any:
        path_a = params.get("path_a")
        path_b = params.get("path_b")
        if not path_a or not path_b:
            raise ValueError("path_a and path_b are required")
        sidecar_a = params.get("sidecar_a")
        sidecar_b = params.get("sidecar_b")
        return compare_capture_contexts(
            str(path_a),
            str(path_b),
            str(sidecar_a) if sidecar_a else None,
            str(sidecar_b) if sidecar_b else None,
        )

    def _find_events(self, params: dict[str, Any]) -> Any:
        return self.client.call("find_events", params)

    def _list_passes(self, params: dict[str, Any]) -> Any:
        return self.client.call("list_passes", params)

    def _inspect_pipeline_state(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_pipeline_state", params)

    def _inspect_shader(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_shader", params)

    def _inspect_cbuffer_values(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_cbuffer_values", params)

    def _read_buffer(self, params: dict[str, Any]) -> Any:
        return self.client.call("read_buffer", params)

    def _get_shader_disasm(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_shader_disasm", params)

    def _get_shader_source(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_shader_source", params)

    def _get_shader_code(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_shader_code", params)

    def _inspect_texture_usage(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_texture_usage", params)

    def _inspect_mesh(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_mesh", params)

    def _get_frame_packet(self, params: dict[str, Any]) -> Any:
        include_hints = bool(params.get("include_hints"))
        sidecar = params.get("sidecar")
        call_params = dict(params)
        call_params.pop("include_hints", None)
        call_params.pop("sidecar", None)
        result = self.client.call("get_frame_packet", call_params)
        if not include_hints or not result.get("ok"):
            return result
        status = self.client.call("get_capture_status")
        if not status.get("ok"):
            return result
        data = status.get("data") or {}
        if not data.get("loaded") or not data.get("path"):
            return result
        return attach_capture_hints(
            result,
            str(data.get("path")),
            cap=str(data.get("cap")) if data.get("cap") is not None else "active",
            sidecar_path=str(sidecar) if sidecar else None,
            packet_kind="frame",
        )

    def _get_pass_packet(self, params: dict[str, Any]) -> Any:
        include_hints = bool(params.get("include_hints"))
        sidecar = params.get("sidecar")
        call_params = dict(params)
        call_params.pop("include_hints", None)
        call_params.pop("sidecar", None)
        result = self.client.call("get_pass_packet", call_params)
        if not include_hints or not result.get("ok"):
            return result
        status = self.client.call("get_capture_status")
        if not status.get("ok"):
            return result
        data = status.get("data") or {}
        if not data.get("loaded") or not data.get("path"):
            return result
        return attach_capture_hints(
            result,
            str(data.get("path")),
            cap=str(data.get("cap")) if data.get("cap") is not None else "active",
            sidecar_path=str(sidecar) if sidecar else None,
            packet_kind="pass",
        )

    def _get_draw_packet(self, params: dict[str, Any]) -> Any:
        include_hints = bool(params.get("include_hints"))
        sidecar = params.get("sidecar")
        call_params = dict(params)
        call_params.pop("include_hints", None)
        call_params.pop("sidecar", None)
        result = self.client.call("get_draw_packet", call_params)
        if not include_hints or not result.get("ok"):
            return result
        status = self.client.call("get_capture_status")
        if not status.get("ok"):
            return result
        data = status.get("data") or {}
        if not data.get("loaded") or not data.get("path"):
            return result
        return attach_capture_hints(
            result,
            str(data.get("path")),
            cap=str(data.get("cap")) if data.get("cap") is not None else "active",
            sidecar_path=str(sidecar) if sidecar else None,
            packet_kind="draw",
        )

    def _debug_save_overlay(self, params: dict[str, Any]) -> Any:
        return self.client.call("debug_save_overlay", params)

    def _debug_save_texture(self, params: dict[str, Any]) -> Any:
        return self.client.call("debug_save_texture", params)


def _configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def _tool_descriptions(*spec_groups) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for group in spec_groups:
        for spec in group:
            descriptions[spec.name] = spec.description
    return descriptions


def _error_envelope(code: str, msg: str, cap: str | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "mode": "summary",
        "data": None,
        "err": {
            "code": code,
            "msg": msg,
        },
        "meta": {
            "cap": cap,
            "truncated": False,
        },
    }


def maybe_create_fastmcp() -> Any | None:
    """Create a FastMCP app if the dependency is available."""

    try:
        from fastmcp import FastMCP  # type: ignore
    except ImportError:
        return None

    offline = OfflineToolRegistry()
    live = LiveToolRegistry()
    app = FastMCP(name="RenderDoc MCP")
    descriptions = _tool_descriptions(OFFLINE_BOOTSTRAP_TOOLS, LIVE_BRIDGE_TOOLS)

    # Keep tool wrappers explicit so FastMCP can preserve per-tool signatures and schemas.
    # `live.require()` and `description=` remove most of the duplication without hiding
    # arguments behind dynamic registration.

    @app.tool(description=descriptions["get_capture_status"])
    def get_capture_status(directory: str | None = None) -> Any:
        if live.available():
            return live.invoke("get_capture_status", {"directory": directory})
        return offline.invoke("get_capture_status", {"directory": directory})

    @app.tool(description=descriptions["get_capture_context"])
    def get_capture_context(
        path: str | None = None,
        sidecar: str | None = None,
    ) -> Any:
        if live.available():
            return live.invoke("get_capture_context", {"path": path, "sidecar": sidecar})
        return offline.invoke("get_capture_context", {"path": path, "sidecar": sidecar})

    @app.tool(description=descriptions["get_capture_hints"])
    def get_capture_hints(
        path: str | None = None,
        sidecar: str | None = None,
    ) -> Any:
        if live.available():
            return live.invoke("get_capture_hints", {"path": path, "sidecar": sidecar})
        return offline.invoke("get_capture_hints", {"path": path, "sidecar": sidecar})

    @app.tool(description=descriptions["compare_capture_contexts"])
    def compare_capture_contexts(
        path_a: str,
        path_b: str,
        sidecar_a: str | None = None,
        sidecar_b: str | None = None,
    ) -> Any:
        if live.available():
            return live.invoke(
                "compare_capture_contexts",
                {
                    "path_a": path_a,
                    "path_b": path_b,
                    "sidecar_a": sidecar_a,
                    "sidecar_b": sidecar_b,
                },
            )
        return offline.invoke(
            "compare_capture_contexts",
            {
                "path_a": path_a,
                "path_b": path_b,
                "sidecar_a": sidecar_a,
                "sidecar_b": sidecar_b,
            },
        )

    @app.tool(description=descriptions["compare_pass_lists"])
    def compare_pass_lists(
        file_a: str,
        file_b: str,
    ) -> Any:
        return offline.invoke(
            "compare_pass_lists",
            {
                "file_a": file_a,
                "file_b": file_b,
            },
        )

    @app.tool(description=descriptions["compare_packet_artifacts"])
    def compare_packet_artifacts(
        file_a: str,
        file_b: str,
    ) -> Any:
        return offline.invoke(
            "compare_packet_artifacts",
            {
                "file_a": file_a,
                "file_b": file_b,
            },
        )

    @app.tool(description=descriptions["compare_draw_packets"])
    def compare_draw_packets(
        file_a: str,
        file_b: str,
    ) -> Any:
        return offline.invoke(
            "compare_draw_packets",
            {
                "file_a": file_a,
                "file_b": file_b,
            },
        )

    @app.tool(description=descriptions["compare_texture_usage_artifacts"])
    def compare_texture_usage_artifacts(
        file_a: str,
        file_b: str,
    ) -> Any:
        return offline.invoke(
            "compare_texture_usage_artifacts",
            {
                "file_a": file_a,
                "file_b": file_b,
            },
        )

    @app.tool(description=descriptions["list_captures"])
    def list_captures(root: str, limit: int = 50) -> Any:
        return offline.invoke("list_captures", {"root": root, "limit": limit})

    @app.tool(description=descriptions["open_capture"])
    def open_capture(path: str) -> Any:
        if live.available():
            return live.invoke("open_capture", {"path": path})
        return offline.invoke("open_capture", {"path": path})

    @app.tool(description=descriptions["find_latest_capture"])
    def find_latest_capture(directory: str, recursive: bool = True) -> Any:
        params = {"directory": directory, "recursive": recursive}
        if live.available():
            return live.invoke("find_latest_capture", params)
        return offline.invoke("find_latest_capture", params)

    @app.tool(description=descriptions["load_latest_capture"])
    def load_latest_capture(directory: str, recursive: bool = True) -> Any:
        params = {"directory": directory, "recursive": recursive}
        if live.available():
            return live.invoke("load_latest_capture", params)
        return offline.invoke("load_latest_capture", params)

    @app.tool(description=descriptions["wait_for_new_capture"])
    def wait_for_new_capture(
        directory: str,
        previous_path: str | None = None,
        timeout: float = 30.0,
        interval: float = 0.5,
        recursive: bool = True,
    ) -> Any:
        params = {
            "directory": directory,
            "previous_path": previous_path,
            "timeout": timeout,
            "interval": interval,
            "recursive": recursive,
        }
        if live.available():
            return live.invoke("wait_for_new_capture", params)
        return offline.invoke("wait_for_new_capture", params)

    @app.tool(description=descriptions["find_events"])
    def find_events(
        q: str | None = None,
        marker: str | None = None,
        exclude_markers: list[str] | None = None,
        eid_min: int | None = None,
        eid_max: int | None = None,
        limit: int = 50,
    ) -> Any:
        return live.require(
            "find_events",
            {
                "q": q,
                "marker": marker,
                "exclude_markers": exclude_markers or [],
                "eid_min": eid_min,
                "eid_max": eid_max,
                "limit": limit,
            },
        )

    @app.tool(description=descriptions["list_passes"])
    def list_passes(
        marker: str | None = None,
        limit: int = 50,
    ) -> Any:
        return live.require(
            "list_passes",
            {
                "marker": marker,
                "limit": limit,
            },
        )

    @app.tool(description=descriptions["inspect_pipeline_state"])
    def inspect_pipeline_state(
        eid: int,
    ) -> Any:
        return live.require(
            "inspect_pipeline_state",
            {
                "eid": eid,
            },
        )

    @app.tool(description=descriptions["debug_save_overlay"])
    def debug_save_overlay(
        eid: int,
        overlay: str = "drawcall",
        rid: str | None = None,
        dest: str = "PNG",
    ) -> Any:
        return live.require(
            "debug_save_overlay",
            {
                "eid": eid,
                "overlay": overlay,
                "rid": rid,
                "dest": dest,
            },
        )

    @app.tool(description=descriptions["debug_save_texture"])
    def debug_save_texture(
        rid: str,
        eid: int | None = None,
        dest: str = "PNG",
        format: str | None = None,
        overwrite: bool = False,
    ) -> Any:
        return live.require(
            "debug_save_texture",
            {
                "rid": rid,
                "eid": eid,
                "dest": dest,
                "format": format,
                "overwrite": overwrite,
            },
        )

    @app.tool(description=descriptions["inspect_shader"])
    def inspect_shader(
        eid: int,
        stage: str,
    ) -> Any:
        return live.require(
            "inspect_shader",
            {
                "eid": eid,
                "stage": stage,
            },
        )

    @app.tool(description=descriptions["inspect_cbuffer_values"])
    def inspect_cbuffer_values(
        eid: int,
        stage: str,
        slot: int | None = None,
        raw: bool = False,
    ) -> Any:
        return live.require(
            "inspect_cbuffer_values",
            {
                "eid": eid,
                "stage": stage,
                "slot": slot,
                "raw": raw,
            },
        )

    @app.tool(description=descriptions["read_buffer"])
    def read_buffer(
        rid: str,
        offset: int,
        length: int,
        format: str = "raw",
        stride: int | None = None,
        eid: int | None = None,
    ) -> Any:
        return live.require(
            "read_buffer",
            {
                "rid": rid,
                "offset": offset,
                "length": length,
                "format": format,
                "stride": stride,
                "eid": eid,
            },
        )

    @app.tool(description=descriptions["get_shader_disasm"])
    def get_shader_disasm(
        eid: int,
        stage: str,
        offset: int = 0,
        max_lines: int = 400,
    ) -> Any:
        return live.require(
            "get_shader_disasm",
            {
                "eid": eid,
                "stage": stage,
                "offset": offset,
                "max_lines": max_lines,
            },
        )

    @app.tool(description=descriptions["get_shader_source"])
    def get_shader_source(
        eid: int,
        stage: str,
        file: str | None = None,
        file_index: int = 0,
        offset: int = 0,
        max_lines: int = 400,
    ) -> Any:
        return live.require(
            "get_shader_source",
            {
                "eid": eid,
                "stage": stage,
                "file": file,
                "file_index": file_index,
                "offset": offset,
                "max_lines": max_lines,
            },
        )

    @app.tool(description=descriptions["get_shader_code"])
    def get_shader_code(
        eid: int,
        stage: str,
        file: str | None = None,
        file_index: int = 0,
        offset: int = 0,
        max_lines: int = 400,
    ) -> Any:
        return live.require(
            "get_shader_code",
            {
                "eid": eid,
                "stage": stage,
                "file": file,
                "file_index": file_index,
                "offset": offset,
                "max_lines": max_lines,
            },
        )

    @app.tool(description=descriptions["inspect_texture_usage"])
    def inspect_texture_usage(
        rid: str | None = None,
        name: str | None = None,
        limit: int = 10,
        eid_min: int | None = None,
        eid_max: int | None = None,
    ) -> Any:
        return live.require(
            "inspect_texture_usage",
            {
                "rid": rid,
                "name": name,
                "limit": limit,
                "eid_min": eid_min,
                "eid_max": eid_max,
            },
        )

    @app.tool(description=descriptions["inspect_mesh"])
    def inspect_mesh(
        eid: int,
    ) -> Any:
        return live.require(
            "inspect_mesh",
            {
                "eid": eid,
            },
        )

    @app.tool(description=descriptions["get_frame_packet"])
    def get_frame_packet(
        limit: int = 20,
        include_hints: bool = False,
        sidecar: str | None = None,
        pass_contains: str | None = None,
        draw_contains: str | None = None,
        only_writes_to_resource: str | None = None,
        only_reads_resource: str | None = None,
        exclude_editor_only: bool = False,
    ) -> Any:
        return live.require(
            "get_frame_packet",
            {
                "limit": limit,
                "include_hints": include_hints,
                "sidecar": sidecar,
                "pass_contains": pass_contains,
                "draw_contains": draw_contains,
                "only_writes_to_resource": only_writes_to_resource,
                "only_reads_resource": only_reads_resource,
                "exclude_editor_only": exclude_editor_only,
            },
        )

    @app.tool(description=descriptions["get_pass_packet"])
    def get_pass_packet(
        marker: str | None = None,
        eid: int | None = None,
        limit: int = 8,
        include_hints: bool = False,
        sidecar: str | None = None,
    ) -> Any:
        return live.require(
            "get_pass_packet",
            {
                "marker": marker,
                "eid": eid,
                "limit": limit,
                "include_hints": include_hints,
                "sidecar": sidecar,
            },
        )

    @app.tool(description=descriptions["get_draw_packet"])
    def get_draw_packet(
        eid: int,
        include_hints: bool = False,
        sidecar: str | None = None,
    ) -> Any:
        return live.require(
            "get_draw_packet",
            {"eid": eid, "include_hints": include_hints, "sidecar": sidecar},
        )

    return app


def run_local_json(method: str, params: dict[str, Any]) -> int:
    live = LiveToolRegistry()
    offline = OfflineToolRegistry()
    try:
        if method in live.handlers:
            if live.available():
                result = live.invoke(method, params)
            elif method in offline.handlers:
                result = offline.invoke(method, params)
            else:
                result = _error_envelope(
                    "live_bridge_unavailable",
                    "Live qrenderdoc bridge is not available",
                    cap="active",
                )
        elif method in offline.handlers:
            result = offline.invoke(method, params)
        else:
            result = _error_envelope("unknown_tool", f"Unknown tool: {method}")
    except ValueError as exc:
        result = _error_envelope("bad_request", str(exc))
    except Exception as exc:
        result = _error_envelope("request_failed", str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def main() -> int:
    _configure_stdio()

    parser = argparse.ArgumentParser(description="RenderDoc MCP runtime")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_local = sub.add_parser("run-local-json")
    run_local.add_argument("method")
    run_local.add_argument("--params", default="{}")
    run_local.add_argument("--params-file")

    run_mcp = sub.add_parser("run-mcp")
    run_mcp.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    run_mcp.add_argument("--host", default="127.0.0.1")
    run_mcp.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()

    if args.cmd == "run-local-json":
        if args.params_file:
            with open(args.params_file, "r", encoding="utf-8-sig") as handle:
                params = json.loads(handle.read())
                params = params.get("params", params)
        else:
            params = json.loads(args.params)
        return run_local_json(args.method, params)

    app = maybe_create_fastmcp()
    if app is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "err": {
                        "code": "fastmcp_not_installed",
                        "msg": "fastmcp is not installed; use run-local-json for validation",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    if args.transport == "http":
        app.run("http", host=args.host, port=args.port)
    else:
        app.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
