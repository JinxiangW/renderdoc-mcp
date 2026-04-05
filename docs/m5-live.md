# Milestone 5: Live Bridge Integration

## Goal

Connect the MCP runtime to the live `qrenderdoc` bridge and expose the first pass-level tool:

- `find_events`
- `list_passes`

## Checklist

- [x] define milestone 5 scope
- [x] implement a reusable live bridge client in the MCP package
- [x] route live-capable tools through the bridge from the MCP runtime
- [x] implement compact `list_passes` in the qrenderdoc extension
- [x] validate both `find_events` and `list_passes` on a real capture

## Constraints

- keep compact envelope shape
- preserve offline bootstrap tools
- do not add heavyweight pipeline dumps in this milestone

## Validation Notes

- live bridge client implemented in `src/renderdoc_mcp/integration/bridge_client.py`
- MCP runtime now routes `get_capture_status`, `find_events`, and `list_passes` through the live bridge when available
- validated direct bridge requests with:
- `scripts/bridge_req.py find_events --params-file fixtures\requests\find.json`
- `scripts/bridge_req.py list_passes --params-file fixtures\requests\list_passes.json`
- validated live capture on:
  - `C:\Caps\世界\Endfield-frame106520.rdc`
- observed real pass summaries such as:
  - `Compute Pass #1`
  - `Depth-only Pass #1`
  - `Colour Pass #1 (1 Targets + Depth)`
