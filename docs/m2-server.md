# MCP Server Bootstrap Milestone

## Goal

Expose the validated offline bootstrap through an MCP-facing server entrypoint with three tools:

- `get_capture_status`
- `list_captures`
- `open_capture`

## Checklist

- [x] define the MCP server bootstrap milestone
- [x] create a tool registry for the three implemented tools
- [x] add a server runtime with MCP-facing entrypoints
- [x] keep local validation independent of optional third-party MCP packages
- [x] add request fixtures for the three implemented tools
- [x] validate the entrypoint with real captures from `C:\Caps`

## Constraints

- only the three implemented offline tools are exposed in this milestone
- response shapes must match the compact envelope policy
- no live `qrenderdoc` bridge work in this milestone

## Validation Notes

- `run-local-json list_captures --params-file fixtures\requests\list_caps.json` passed
- `run-local-json open_capture --params-file fixtures\requests\open_capture.json` passed
- `run-local-json get_capture_status` passed after real capture open
- `run-mcp --transport stdio` starts correctly for MCP clients and exits when stdin is closed
- `run-mcp --transport http` stays alive when run in the foreground for manual serving
