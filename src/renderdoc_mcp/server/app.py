"""Tool registry scaffold for the RenderDoc MCP server."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    summary_first: bool
    description: str


V1_SUMMARY_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("open_capture", True, "Open a capture and return only high-level facts."),
    ToolSpec("get_capture_status", True, "Return current capture status."),
    ToolSpec("find_events", True, "Find candidate events using compact filters."),
    ToolSpec("list_passes", True, "List pass markers with compact counts."),
    ToolSpec(
        "inspect_pipeline_state",
        True,
        "Return a compact pipeline snapshot for an event.",
    ),
    ToolSpec(
        "inspect_texture_usage",
        True,
        "Return compact read/write usage for a texture.",
    ),
    ToolSpec("inspect_shader", True, "Return compact shader bindings and constants info."),
    ToolSpec("get_shader_disasm", True, "Return shader disassembly text with pagination support."),
    ToolSpec("inspect_mesh", True, "Return compact mesh inspection data."),
)


OFFLINE_BOOTSTRAP_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("get_capture_status", True, "Return current capture status."),
    ToolSpec("list_captures", True, "List capture files recursively under a root directory."),
    ToolSpec("open_capture", True, "Open a capture and return only high-level facts."),
)


LIVE_BRIDGE_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("get_capture_status", True, "Return current capture status from the live bridge."),
    ToolSpec("find_events", True, "Find compact event matches in the live capture."),
    ToolSpec("list_passes", True, "List pass markers in the live capture."),
    ToolSpec(
        "inspect_pipeline_state",
        True,
        "Return a compact pipeline snapshot for one event from the live capture.",
    ),
    ToolSpec(
        "inspect_shader",
        True,
        "Return a compact shader summary for one stage at one event from the live capture.",
    ),
    ToolSpec(
        "inspect_texture_usage",
        True,
        "Return a compact texture usage summary from the live capture.",
    ),
    ToolSpec(
        "get_shader_disasm",
        True,
        "Return shader disassembly text from the live capture with pagination support.",
    ),
    ToolSpec(
        "inspect_mesh",
        True,
        "Return a compact mesh summary for one event from the live capture.",
    ),
    ToolSpec(
        "get_frame_packet",
        True,
        "Return a compact frame-level packet for the live capture.",
    ),
    ToolSpec(
        "get_pass_packet",
        True,
        "Return a compact pass-level packet for the live capture.",
    ),
    ToolSpec(
        "get_draw_packet",
        True,
        "Return a compact draw-level packet for the live capture.",
    ),
    ToolSpec(
        "debug_save_overlay",
        True,
        "Save a debug overlay texture such as Highlight Drawcall for one live event.",
    ),
)
