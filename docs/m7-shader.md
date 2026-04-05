# Milestone 7: Shader Summary

## Goal

Implement a compact live tool:

- `inspect_shader`

This tool should summarize one shader stage at one event without returning disassembly.

## Checklist

- [x] define milestone 7 scope
- [x] implement `inspect_shader` in the qrenderdoc extension bridge
- [x] route the tool through the MCP runtime
- [x] validate the tool on a real live capture

## Compact Contract

Input:

```json
{
  "eid": 21113,
  "stage": "ps"
}
```

Output:

```json
{
  "ok": true,
  "mode": "summary",
  "data": {
    "eid": 21113,
    "stage": "ps",
    "shader": {
      "name": "main",
      "entry": "main"
    },
    "bind": {
      "srv": 3,
      "uav": 0,
      "cbv": 4,
      "smp": 1
    },
    "cbufs": [
      {"name": "PerView", "vars": 18}
    ]
  },
  "err": null,
  "meta": {
    "cap": "active",
    "truncated": false
  }
}
```

## Validation Notes

- validated on `C:\Caps\世界\Endfield-frame106520.rdc`
- verified `inspect_shader` for `eid=21113`, `stage=ps`
- compact output includes:
  - shader name and entry
  - `srv/uav/cbv/smp` binding counts
  - constant buffer names and variable counts
