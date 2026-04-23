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
    ToolSpec(
        "inspect_cbuffer_values",
        True,
        "Return constant-buffer bindings, ranges, and decoded variable values.",
    ),
    ToolSpec(
        "read_buffer",
        True,
        "Read and decode bytes from a live buffer resource.",
    ),
    ToolSpec("get_shader_disasm", True, "Return shader disassembly text with pagination support."),
    ToolSpec("get_shader_source", True, "Return shader source/debug text when source symbols are available."),
    ToolSpec("get_shader_code", True, "Return shader source when available, otherwise fall back to disassembly."),
    ToolSpec("inspect_mesh", True, "Return compact mesh inspection data."),
)


OFFLINE_BOOTSTRAP_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("get_capture_status", True, "Return current capture status."),
    ToolSpec("get_capture_context", True, "Return UE-side context metadata attached to the active or selected capture."),
    ToolSpec("get_capture_hints", True, "Return compact UE semantic hints derived from capture context metadata."),
    ToolSpec("compare_capture_contexts", True, "Compare UE-side context metadata between two captures."),
    ToolSpec("compare_pass_lists", True, "Compare two saved pass-list or frame-packet artifacts."),
    ToolSpec("compare_packet_artifacts", True, "Compare two saved compact JSON packet artifacts."),
    ToolSpec("compare_draw_packets", True, "Compare two saved draw-packet artifacts with draw-focused summaries."),
    ToolSpec("compare_texture_usage_artifacts", True, "Compare two saved texture-usage artifacts with resource-flow summaries."),
    ToolSpec("list_captures", True, "List capture files recursively under a root directory."),
    ToolSpec("open_capture", True, "Open a capture and return only high-level facts."),
    ToolSpec("find_latest_capture", True, "Find the newest .rdc capture under a directory."),
    ToolSpec("load_latest_capture", True, "Open the newest .rdc capture under a directory."),
    ToolSpec("wait_for_new_capture", True, "Wait for a newer .rdc capture, then open it."),
)


LIVE_BRIDGE_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("get_capture_status", True, "Return current capture status from the live bridge."),
    ToolSpec("open_capture", True, "Load a capture by path into the live qrenderdoc session."),
    ToolSpec("find_latest_capture", True, "Find the newest .rdc capture under a directory."),
    ToolSpec("load_latest_capture", True, "Load the newest .rdc capture into the live qrenderdoc session."),
    ToolSpec("wait_for_new_capture", True, "Wait for a newer .rdc capture and load it into qrenderdoc."),
    ToolSpec(
        "get_capture_context",
        True,
        "Return UE-side context metadata attached to the active live capture.",
    ),
    ToolSpec(
        "get_capture_hints",
        True,
        "Return compact UE semantic hints derived from the active live capture context metadata.",
    ),
    ToolSpec(
        "compare_capture_contexts",
        True,
        "Compare UE-side context metadata between two captures.",
    ),
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
        "inspect_cbuffer_values",
        True,
        "Return cbuffer binding ranges and actual variable values for one stage/event.",
    ),
    ToolSpec(
        "read_buffer",
        True,
        "Read a live buffer range and decode it as raw, float4, uint4, int4, matrix, or structured rows.",
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
        "get_shader_source",
        True,
        "Return shader source text from the live capture when debug/source information is available.",
    ),
    ToolSpec(
        "get_shader_code",
        True,
        "Return shader source text when available, otherwise return disassembly from the live capture.",
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
    ToolSpec(
        "debug_save_texture",
        True,
        "Save one live texture resource to an export file for before/after validation.",
    ),
)
