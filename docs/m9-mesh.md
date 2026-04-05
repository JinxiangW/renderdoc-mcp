# Milestone 9: Mesh Summary

## Goal

Implement a compact live tool:

- `inspect_mesh`

This tool should provide an event-scoped geometry summary for a draw-like event.

## Checklist

- [ ] define milestone 9 scope
- [ ] implement `inspect_mesh` in the qrenderdoc extension bridge
- [ ] route the tool through the MCP runtime
- [ ] validate the tool on a real live capture

## Compact Contract

Input:

```json
{
  "eid": 31
}
```

Output:

```json
{
  "ok": true,
  "mode": "summary",
  "data": {
    "eid": 31,
    "topo": "TriangleList",
    "idx": 1234,
    "inst": 1,
    "attrs": [
      {"name": "POSITION", "fmt": "Float3"},
      {"name": "TEXCOORD0", "fmt": "Float2"}
    ],
    "postvs": {
      "verts": 1234
    }
  },
  "err": null,
  "meta": {
    "cap": "active",
    "truncated": false
  }
}
```

## Constraint

- compact summary only
- no CSV export
- no FBX export
- no full vertex dump
