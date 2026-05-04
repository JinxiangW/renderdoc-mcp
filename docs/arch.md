# Architecture

## Chosen V1 Architecture

V1 will use a three-layer design:

1. MCP server
2. RenderDoc bridge
3. RenderDoc integration host

## Why This Architecture

It matches the intended workflow:

- live `qrenderdoc` analysis
- offline `.rdc` analysis
- compact AI-facing responses
- ability to swap transport or host mode without changing tool contracts

## Layers

### 1. MCP Server

Responsibility:

- expose AI-facing tools
- validate arguments
- apply compact response policy
- choose `summary` vs `full` behavior

Non-goals:

- direct RenderDoc object handling
- tool-specific replay logic

### 2. RenderDoc Bridge

Responsibility:

- transport requests to the integration host
- normalize errors
- manage timeouts and request IDs
- discover live qrenderdoc bridge instances and route requests by `window_id`

V1 bridge requirements:

- local-only
- request/response model
- explicit timeout handling
- no shared request queue across qrenderdoc windows

Transport decision for V1:

- abstract bridge interface in code
- leave transport pluggable
- do not lock the contracts to file IPC

This keeps the current community-style extension approach possible, while allowing later migration to
named pipes or sockets.

### 3. RenderDoc Integration Host

Supported host modes:

- `ui_extension`: running inside `qrenderdoc`
- `offline_host`: replay-only process opening `.rdc` directly

V1 priority:

- design contracts that work for both
- allow first implementation to start with `ui_extension`

## Operational Modes

### Live Mode

- active capture already open in `qrenderdoc`
- best for pass inspection, live debugging, current pipeline state
- each qrenderdoc window is a separate live bridge target
- use `list_live_windows` and pass `window_id` when more than one target is active

### Offline Mode

- open `.rdc` by path
- best for reverse analysis and batch-friendly workflows

## Response Policy

- summary-first by default
- detail only on explicit request
- prefer IDs, counts, and compact summaries over raw blobs

## Entry Points

All major tools should eventually support one or more of:

- event ID
- marker/pass name
- shader name
- texture/resource name
- resource ID
- capture path

## V1 Tool Set

The V1 observe-only tool set is:

- `open_capture`
- `get_capture_status`
- `list_captures`
- `list_live_windows`
- `find_events`
- `list_passes`
- `get_frame_packet`
- `get_pass_packet`
- `get_draw_packet`
- `inspect_pipeline_state`
- `inspect_texture_usage`
- `inspect_shader`
- `inspect_mesh`

## Deferred Items

These are intentionally out of scope for this milestone:

- pixel history
- full shader debug traces
- heavy binary transport
- embedded analysis heuristics in MCP
- report generation inside MCP
