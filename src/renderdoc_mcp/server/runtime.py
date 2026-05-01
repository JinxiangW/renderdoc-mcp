"""MCP-facing runtime for the implemented offline bootstrap tools."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from renderdoc_mcp.integration import LiveBridgeClient

from .app import LIVE_BRIDGE_TOOLS, OFFLINE_BOOTSTRAP_TOOLS
from .offline_bootstrap import OfflineBootstrapTools

ToolHandler = Callable[[dict[str, Any]], Any]


def _error_envelope(code: str, msg: str) -> dict[str, Any]:
    return {
        "ok": False,
        "mode": "summary",
        "data": None,
        "err": {"code": code, "msg": msg},
        "meta": {"cap": None, "truncated": False},
    }


class OfflineToolRegistry:
    """Registry for the implemented offline bootstrap tools."""

    def __init__(self, tools: OfflineBootstrapTools | None = None) -> None:
        self.tools = tools or OfflineBootstrapTools()
        self.handlers: dict[str, ToolHandler] = {
            "get_capture_status": self._get_capture_status,
            "list_captures": self._list_captures,
            "open_capture": self._open_capture,
        }

    def invoke(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if method not in self.handlers:
            raise KeyError(f"Unknown tool: {method}")
        return self.handlers[method](params or {})

    def _get_capture_status(self, _: dict[str, Any]) -> Any:
        return self.tools.get_capture_status()

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


class LiveToolRegistry:
    """Registry for live qrenderdoc bridge tools."""

    def __init__(self, client: LiveBridgeClient | None = None) -> None:
        self.client = client or LiveBridgeClient()
        self.handlers: dict[str, ToolHandler] = {
            "get_capture_status": self._get_capture_status,
            "find_events": self._find_events,
            "list_passes": self._list_passes,
            "get_frame_packet": self._get_frame_packet,
            "get_pass_packet": self._get_pass_packet,
            "get_draw_packet": self._get_draw_packet,
            "debug_save_overlay": self._debug_save_overlay,
            "debug_save_texture": self._debug_save_texture,
            "inspect_pipeline_state": self._inspect_pipeline_state,
            "inspect_shader": self._inspect_shader,
            "get_shader_disasm": self._get_shader_disasm,
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

    def _get_capture_status(self, _: dict[str, Any]) -> Any:
        return self.client.call("get_capture_status")

    def _find_events(self, params: dict[str, Any]) -> Any:
        return self.client.call("find_events", params)

    def _list_passes(self, params: dict[str, Any]) -> Any:
        return self.client.call("list_passes", params)

    def _inspect_pipeline_state(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_pipeline_state", params)

    def _inspect_shader(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_shader", params)

    def _get_shader_disasm(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_shader_disasm", params)

    def _inspect_texture_usage(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_texture_usage", params)

    def _inspect_mesh(self, params: dict[str, Any]) -> Any:
        return self.client.call("inspect_mesh", params)

    def _get_frame_packet(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_frame_packet", params)

    def _get_pass_packet(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_pass_packet", params)

    def _get_draw_packet(self, params: dict[str, Any]) -> Any:
        return self.client.call("get_draw_packet", params)

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
    def get_capture_status() -> Any:
        if live.available():
            return live.invoke("get_capture_status")
        return offline.invoke("get_capture_status")

    @app.tool(description=descriptions["list_captures"])
    def list_captures(root: str, limit: int = 50) -> Any:
        return offline.invoke("list_captures", {"root": root, "limit": limit})

    @app.tool(description=descriptions["open_capture"])
    def open_capture(path: str) -> Any:
        return offline.invoke("open_capture", {"path": path})

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
    ) -> Any:
        return live.require(
            "debug_save_texture",
            {
                "rid": rid,
                "eid": eid,
                "dest": dest,
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

    @app.tool(description=descriptions["inspect_texture_usage"])
    def inspect_texture_usage(
        rid: str | None = None,
        name: str | None = None,
        limit: int = 10,
    ) -> Any:
        return live.require(
            "inspect_texture_usage",
            {
                "rid": rid,
                "name": name,
                "limit": limit,
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
    def get_frame_packet(limit: int = 20) -> Any:
        return live.require("get_frame_packet", {"limit": limit})

    @app.tool(description=descriptions["get_pass_packet"])
    def get_pass_packet(
        marker: str | None = None,
        eid: int | None = None,
        limit: int = 8,
    ) -> Any:
        return live.require("get_pass_packet", {"marker": marker, "eid": eid, "limit": limit})

    @app.tool(description=descriptions["get_draw_packet"])
    def get_draw_packet(eid: int) -> Any:
        return live.require("get_draw_packet", {"eid": eid})

    return app


def run_local_json(method: str, params: dict[str, Any]) -> int:
    live = LiveToolRegistry()
    offline = OfflineToolRegistry()
    try:
        if method in live.handlers:
            if live.available():
                result = live.invoke(method, params)
            else:
                result = _error_envelope(
                    "live_bridge_unavailable",
                    "Live qrenderdoc bridge is not available",
                )
        elif method in offline.handlers:
            result = offline.invoke(method, params)
        else:
            result = _error_envelope("method_not_found", f"Unknown tool: {method}")
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
            params = json.loads(open(args.params_file, "r", encoding="utf-8-sig").read())
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
