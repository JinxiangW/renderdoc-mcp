# V1 Tool Specs

All tools below default to `mode=summary`.

## 1. `open_capture`

Purpose:

- open a capture for offline inspection
- return only high-level capture facts

Input:

```json
{
  "path": "C:/captures/frame_001.rdc",
  "mode": "summary"
}
```

Summary output:

```json
{
  "cap": "active",
  "api": null,
  "path": "C:/captures/frame_001.rdc",
  "name": "frame_001.rdc",
  "size": 12345678,
  "verified": true
}
```

## 2. `get_capture_status`

Purpose:

- tell the caller whether a capture is active
- provide active API and path

Input:

```json
{}
```

Summary output:

```json
{
  "loaded": true,
  "cap": "active",
  "api": "D3D11",
  "path": "C:/captures/foo.rdc"
}
```

## 3. `find_events`

Purpose:

- unified event search entry point
- support event ID range, marker, shader, texture, resource, and text queries

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

Summary output:

```json
{
  "count": 3,
  "items": [
    {"eid": 4211, "name": "BasePass", "type": "Draw", "marker": "Opaque"},
    {"eid": 4227, "name": "BasePass", "type": "Draw", "marker": "Opaque"}
  ]
}
```

## 4. `list_passes`

Purpose:

- enumerate pass markers
- return only pass boundaries and compact counts

Input:

```json
{
  "marker": "BasePass",
  "limit": 50
}
```

Summary output:

```json
{
  "count": 1,
  "items": [
    {
      "eid": 4211,
      "pass": "BasePass",
      "stats": {"draw": 97, "dispatch": 0, "clear": 1}
    }
  ]
}
```

## 5. `inspect_pipeline_state`

Purpose:

- compact per-event pipeline snapshot
- avoid full binding dumps by default
- keep the payload API-agnostic at the top level

Input:

```json
{
  "eid": 4211
}
```

Summary output:

```json
{
  "eid": 4211,
  "api": "D3D12",
  "pass": "BasePass",
  "ia": {"topo": "TriangleList"},
  "sh": {
    "vs": {"sid": "s101", "name": "BasePassVS", "entry": "main"},
    "ps": {"sid": "s205", "name": "BasePassPS", "entry": "main"}
  },
  "res": {"srv": 12, "uav": 1, "cbv": 8, "smp": 6, "rt": 4, "ds": 1}
}
```

Notes:

- fixed-function `blend` / `depth` / `rast` details are not part of `inspect_pipeline_state`
- those details may appear in draw packets and are currently sourced from D3D11-specific state extraction

## 6. `inspect_texture_usage`

Purpose:

- answer where a texture is read or written
- avoid full per-event duplication

Input:

```json
{
  "rid": "r918",
  "limit": 20
}
```

Summary output:

```json
{
  "rid": "r918",
  "name": "GBufferA",
  "type": "Texture2D",
  "fmt": "R8G8B8A8_UNORM",
  "uses": {
    "read": 7,
    "write": 1
  },
  "items": [
    {"eid": 4211, "type": "write", "slot": "rt0", "name": "BasePass"},
    {"eid": 5112, "type": "read", "slot": "srv3", "name": "LightingPass"}
  ]
}
```

## 7. `inspect_shader`

Purpose:

- compact shader summary with bindings and constants summarized
- disassembly deferred to another tool

Input:

```json
{
  "eid": 4211,
  "stage": "ps"
}
```

Summary output:

```json
{
  "eid": 4211,
  "stage": "ps",
  "shader": {"sid": "s205", "name": "BasePassPS", "entry": "main"},
  "bind": {"srv": 10, "uav": 0, "cbv": 6, "smp": 5},
  "cbufs": [
    {"slot": 0, "name": "View", "vars": 24},
    {"slot": 1, "name": "Material", "vars": 13}
  ]
}
```

## 8. `get_shader_disasm`

Purpose:

- return shader disassembly text for one stage at one event
- support pagination for long DXBC output

Input:

```json
{
  "eid": 4211,
  "stage": "ps",
  "offset": 0,
  "max_lines": 120
}
```

Summary output:

```json
{
  "eid": 4211,
  "stage": "ps",
  "shader": {"name": "BasePassPS", "entry": "main"},
  "target": "DXBC",
  "line_count": 834,
  "offset": 0,
  "returned": 120,
  "truncated": true,
  "text": "..."
}
```

## 9. `inspect_mesh`

Purpose:

- give quick geometry inspection without dumping full vertex streams
- target rapid TA checks and deeper debug entry

Input:

```json
{
  "eid": 4211
}
```

Summary output:

```json
{
  "eid": 4211,
  "topo": "TriangleList",
  "verts": 24816,
  "idx": 37224,
  "inst": 1,
  "aabb": {
    "min": [-112.4, -18.8, -96.2],
    "max": [109.7, 201.4, 88.5]
  },
  "attrs": [
    {"name": "POSITION", "fmt": "float3"},
    {"name": "NORMAL", "fmt": "snorm4"},
    {"name": "TEXCOORD0", "fmt": "float2"}
  ]
}
```

## Notes

- marker/pass filters should be wired through any list-producing tool
- all heavy payloads belong to separate deep tools, not the summary tools above
- pass classification and report generation are intentionally outside MCP
