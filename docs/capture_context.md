# Capture Context Sidecar

## Goal

Allow UE-side tooling to attach engine context to a RenderDoc capture without pushing engine-specific logic into `renderdoc-mcp`.

`renderdoc-mcp` reads a JSON sidecar next to a capture and exposes it through `get_capture_context`.
It can also compare two sidecars through `compare_capture_contexts`.
Compact UE semantic hints can be read through `get_capture_hints`.

## Preferred Filenames

Given a capture path such as:

```text
C:/Caps/frame_0103.rdc
```

Preferred sidecar names are checked in this order:

1. `frame_0103.rdc.context.json`
2. `frame_0103.context.json`
3. `frame_0103.rdc.meta.json`
4. `frame_0103.meta.json`

An explicit `sidecar` path may also be supplied to the tool.

## Expected Shape

The sidecar should be one compact JSON object.

Suggested top-level blocks:

```json
{
  "engine": {
    "project": "ExampleGame",
    "build": "Editor",
    "rhi": "D3D12",
    "shader_platform": "PCD3D_SM6",
    "feature_level": "SM6"
  },
  "scene": {
    "map": "L_Test",
    "world": "PersistentLevel"
  },
  "camera": {
    "name": "DebugCamera",
    "loc": [0.0, 100.0, 200.0],
    "rot": [0.0, 90.0, 0.0]
  },
  "view": {
    "size": [2560, 1440],
    "screen_pct": 100
  },
  "cvars": {
    "r.Nanite": 1,
    "r.Lumen": 0
  }
}
```

Suggested hint-oriented optional blocks:

```json
{
  "capture": {
    "reason": "Investigate BasePass material mismatch",
    "frame_hint": 103,
    "user_note": "Selection was the hero mesh"
  },
  "selection": {
    "actor": "BP_Hero",
    "component": "BodyMesh",
    "material": "MI_HeroBody",
    "asset": "/Game/Characters/Hero"
  },
  "rdg": {
    "focus_pass": "BasePass",
    "pass_filters": ["BasePass", "Lighting"]
  }
}
```

## Notes

- `renderdoc-mcp` does not require a fixed UE schema yet.
- The sidecar must be a JSON object, not an array or raw string.
- UE-side MCP should keep this object compact and reproducible.
- `compare_capture_contexts` compares JSON values by path and reports added, removed, and changed fields.
