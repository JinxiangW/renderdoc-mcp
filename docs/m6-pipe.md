# Milestone 6: Event Pipeline Summary

## Goal

Implement and validate a compact live tool:

- `inspect_pipeline_state`

This tool should provide a concise per-event pipeline snapshot suitable for TA debugging.

## Checklist

- [x] define milestone 6 scope
- [x] define compact request and response contract
- [x] implement `inspect_pipeline_state` in the qrenderdoc extension bridge
- [x] route the tool through the MCP runtime
- [x] validate the tool on a real live capture

## Compact Contract

Input:

```json
{
  "eid": 21113
}
```

Output:

```json
{
  "ok": true,
  "mode": "summary",
  "data": {
    "eid": 21113,
    "api": "GraphicsAPI.D3D11",
    "ia": {"topo": "TriangleList"},
    "sh": {
      "vs": {"name": "SomeVS", "entry": "main"},
      "ps": {"name": "SomePS", "entry": "main"}
    },
    "res": {
      "srv": 8,
      "uav": 0,
      "cbv": 6,
      "smp": 4,
      "rt": 1,
      "ds": 1
    }
  },
  "err": null,
  "meta": {
    "cap": "active",
    "truncated": false
  }
}
```

## Constraints

- summary only
- no large shader disassembly
- no full binding dumps

## Validation Notes

- validated on `C:\Caps\世界\Endfield-frame106520.rdc`
- verified live bridge response through `inspect_pipeline_state`
- current summary correctly limits shader stages for a graphics event to `vs` and `ps`

## Remaining Quality Gaps

- `ia.topo` is still empty on the current capture and needs API-specific fallback work
- `rt` and `ds` counts may still under-report on some captures and should be refined later
- fixed-function blend / depth / rasterizer extraction is handled elsewhere and is currently D3D11-limited
