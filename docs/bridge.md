# qrenderdoc Extension Bridge

## Chosen Execution Surface

Milestone 4 uses a `qrenderdoc` Python extension bridge as the execution surface for `find_events`.

Reason:

- installed RenderDoc Python modules are not directly importable from an external interpreter
- event tree and cached capture state are naturally available inside `qrenderdoc`
- the extension model is officially supported by RenderDoc

## Layout

- bridge package: `bridge_extension/renderdoc_mcp_bridge`
- installer: `scripts/install_ext.py`
- IPC transport: local file polling in the temp directory
- live window isolation: each loaded qrenderdoc extension owns `instances/<window_id>/`

The bridge root is `%TEMP%/renderdoc_mcp_bridge`. New extension instances write:

- `instances/<window_id>/requests`
- `instances/<window_id>/responses`
- `instances/<window_id>/heartbeat`
- `instances/<window_id>/info.json`

The MCP client still recognizes the old root-level heartbeat/request/response layout as `legacy`
so an already-running qrenderdoc does not break until it is restarted.

## Implemented Methods

- `ping`
- `get_capture_status`
- `list_live_windows`
- `open_capture`
- `find_latest_capture`
- `load_latest_capture`
- `wait_for_new_capture`
- `find_events`

## Live Window Selection

- call `list_live_windows` to enumerate active qrenderdoc windows
- pass `window_id` to live tools when more than one window is present
- omit `window_id` only when exactly one live bridge is active
- set `RENDERDOC_MCP_WINDOW_ID=<window_id>` when using helper scripts repeatedly

If multiple live bridges are available and a live tool is called without `window_id`, the client
fails fast instead of letting the wrong qrenderdoc window consume the request.

## Manual Validation Path

1. install the extension with the installer script
2. launch `qrenderdoc`
3. open a capture
4. let the auto-loaded extension start
5. call `list_live_windows` if more than one qrenderdoc window is open
6. send bridge requests with `window_id` when targeting a specific live window

Example:

```powershell
uv run python scripts\bridge_req.py list_live_windows
$env:RENDERDOC_MCP_WINDOW_ID = "105880-420776f9"
uv run python scripts\bridge_req.py get_capture_status
uv run python scripts\bridge_req.py list_passes --params '{"limit":3}'
```

Validation on 2026-05-04 used two captures from `C:\Caps`:

- `C:\Caps\剧情\Endfield-frame360653.rdc`
- `C:\Caps\世界\Endfield-frame7146.rdc`

Both windows returned their own capture path when queried by `window_id`; an unqualified live
request failed with the expected "pass window_id" error.

## Current Limitation

End-to-end validation still requires a real `qrenderdoc` session with the extension loaded.
