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

## Implemented Methods

- `ping`
- `get_capture_status`
- `open_capture`
- `find_latest_capture`
- `load_latest_capture`
- `wait_for_new_capture`
- `find_events`

## Manual Validation Path

1. install the extension with the installer script
2. launch `qrenderdoc`
3. open a capture
4. let the auto-loaded extension start
5. send bridge requests through the temp IPC directory

## Current Limitation

End-to-end validation still requires a real `qrenderdoc` session with the extension loaded.
