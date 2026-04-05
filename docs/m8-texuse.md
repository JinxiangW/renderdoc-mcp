# Milestone 8: Texture Usage Summary

## Goal

Implement a compact live tool:

- `inspect_texture_usage`

This tool should summarize where a texture is read or written in the frame.

## Checklist

- [x] define milestone 8 scope
- [x] implement `inspect_texture_usage` in the qrenderdoc extension bridge
- [x] route the tool through the MCP runtime
- [x] validate the tool on a real live capture

## Compact Contract

Input:

```json
{
  "rid": "ResourceId::12345",
  "limit": 10
}
```

Output:

```json
{
  "ok": true,
  "mode": "summary",
  "data": {
    "rid": "ResourceId::12345",
    "name": "SomeTexture",
    "uses": {
      "read": 7,
      "write": 1
    },
    "items": [
      {"eid": 21113, "type": "write", "usage": "ColorTarget", "name": "Colour Pass #1"},
      {"eid": 21200, "type": "read", "usage": "PS_Resource", "name": "Lighting"}
    ]
  },
  "err": null,
  "meta": {
    "cap": "active",
    "truncated": false
  }
}
```

## Constraint

- compact usage summary only
- no raw texture data

## Validation Notes

- validated on `C:\Caps\世界\Endfield-frame106520.rdc`
- verified live bridge response for `inspect_texture_usage`
- current validation used the built-in fallback selector and returned:
  - `rid: ResourceId::63`
  - `name: 2D Texture 63`
  - `read: 11`
  - `write: 0`
