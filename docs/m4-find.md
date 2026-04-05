# Milestone 4: Event Discovery

## Goal

Add the first real analysis tool beyond capture bootstrap:

- `find_events`

This tool should support compact event discovery by:

- text query
- marker/pass filter
- event ID range

## Current Technical Boundary

The installed RenderDoc directory is not directly importable from an external Python interpreter:

- `import renderdoc` is unavailable
- `import qrenderdoc` is unavailable

This means offline event discovery cannot currently be implemented by simply importing RenderDoc's
Python API from the installed package.

## Chosen Execution Surface

Milestone 4 uses:

1. `qrenderdoc` Python extension bridge

## Checklist

- [x] freeze milestone 4 scope around `find_events`
- [x] choose the execution surface for event discovery
- [x] define compact `find_events` request and response rules
- [x] implement a first working `find_events` path
- [x] validate `find_events` against a real capture

## Proposed Compact Contract

Input:

```json
{
  "q": "BasePass",
  "marker": "Opaque",
  "eid_min": 4000,
  "eid_max": 5000,
  "limit": 25
}
```

Output:

```json
{
  "ok": true,
  "mode": "summary",
  "data": {
    "count": 2,
    "items": [
      {"eid": 4211, "name": "BasePass", "type": "Draw", "marker": "Opaque"},
      {"eid": 4227, "name": "BasePass", "type": "Draw", "marker": "Opaque"}
    ]
  },
  "err": null,
  "meta": {
    "cap": "active",
    "truncated": false,
    "count": 2
  }
}
```

## Validation Notes

- installed extension to `%APPDATA%\qrenderdoc\extensions\renderdoc_mcp_bridge`
- enabled auto-load through `%APPDATA%\qrenderdoc\UI.config`
- launched `qrenderdoc` v1.43 with `C:\Caps\世界\Endfield-frame106520.rdc`
- verified bridge `ping`
- verified bridge `get_capture_status`
- verified `find_events` returns compact event summaries on the live capture
