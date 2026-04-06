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
  "sig": {
    "inputs": [{"name": "TEXCOORD0", "reg": 1, "comp_count": 2}],
    "outputs": [{"name": "SV_Target", "reg": 0, "comp_count": 4}]
  },
  "cbufs": [
    {
      "slot": 0,
      "name": "View",
      "vars": 24,
      "size": 1536,
      "variables": [{"name": "ViewProj", "offset": 0, "size": 64}]
    },
    {
      "slot": 1,
      "name": "Material",
      "vars": 13,
      "size": 256,
      "variables": [{"name": "BaseColor", "offset": 0, "size": 16}]
    }
  ]
}
```

Notes:

- `bindings` carries the stage binding table with actual bound resources when available
- `cbufs.variables` is a preview, not necessarily the full variable list
- `sig.inputs` and `sig.outputs` are useful for action reverse work and output-write analysis

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
  "line_start": 1,
  "line_end": 120,
  "returned": 120,
  "truncated": true,
  "lines": [
    {"line": 1, "text": "ps_5_0"},
    {"line": 2, "text": "dcl_globalFlags refactoringAllowed"}
  ],
  "text": "..."
}
```

Notes:

- use `lines` plus `line_start/line_end` when you need code-range references in a reverse-action report
- `text` remains available for quick scanning or copy/paste into notes

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
  "idx": 37224,
  "inst": 1,
  "attrs": [
    {"name": "POSITION", "fmt": "float3", "vb_slot": 0, "offset": 0},
    {"name": "NORMAL", "fmt": "snorm4", "vb_slot": 0, "offset": 12},
    {"name": "TEXCOORD0", "fmt": "float2", "vb_slot": 1, "offset": 0}
  ],
  "vbs": [
    {
      "slot": 0,
      "rid": "ResourceId::700",
      "name": "MeshVB0",
      "meta": {"kind": "buf", "size": 921600},
      "stride": 32,
      "offset": 0
    }
  ],
  "ib": {
    "rid": "ResourceId::701",
    "name": "MeshIB",
    "meta": {"kind": "buf", "size": 148896},
    "offset": 0,
    "byte_stride": 4
  },
  "postvs": {"verts": 24816}
}
```

Notes:

- `attrs` is the input layout view
- `vbs` and `ib` are the bound vertex/index buffers for action reverse work
- mesh summaries are still compact; this is not a full vertex-stream dump

## 10. `get_frame_packet`

Purpose:

- return a compact frame-level packet for the active live capture
- provide a pass inventory for frame reports and pipeline reconstruction

Input:

```json
{
  "limit": 20
}
```

Summary output:

```json
{
  "api": "D3D11",
  "path": "C:/captures/foo.rdc",
  "passes": [
    {
      "eid": 4211,
      "pass": "BasePass",
      "stats": {"draw": 97, "dispatch": 0, "clear": 1}
    }
  ]
}
```

## 11. `get_pass_packet`

Purpose:

- return a compact pass-level packet for one marker/pass
- include pass outputs and one representative draw or dispatch packet

Input:

```json
{
  "marker": "BasePass",
  "eid": 4211,
  "limit": 8
}
```

Summary output:

```json
{
  "pass": {
    "eid": 4211,
    "pass": "BasePass",
    "stats": {"draw": 97, "dispatch": 0, "clear": 1}
  },
  "io": {
    "out_rt": [
      {
        "rid": "ResourceId::918",
        "name": "GBufferA",
        "slot": 0,
        "meta": {"type": "Texture2D", "dims": "1920x1080", "fmt": "R8G8B8A8_UNORM"}
      }
    ],
    "out_ds": null
  },
  "rep": [
    {"eid": 4217, "name": "DrawIndexedInstanced", "type": "Draw"}
  ],
  "rep_draw": {}
}
```

## 12. `get_draw_packet`

Purpose:

- return a compact draw or dispatch packet for one event
- include action context, packet-level shader summary, fixed-function state, and staged IO facts for reverse engineering

Input:

```json
{
  "eid": 4217
}
```

Summary output:

```json
{
  "eid": 4217,
  "name": "ID3D11DeviceContext::DrawIndexedInstanced()",
  "type": "Draw",
  "context": {
    "marker_path": "BasePass / Opaque",
    "parent_pass": {"eid": 4211, "pass": "Opaque", "stats": {"draw": 97}},
    "root_pass": {"eid": 4200, "pass": "BasePass", "stats": {"draw": 97}},
    "position": {
      "index": 18,
      "count": 97,
      "draw_dispatch_index": 18,
      "draw_dispatch_count": 97
    },
    "neighbors": {
      "prev": {"eid": 4216, "name": "DrawIndexedInstanced", "type": "Draw"},
      "next": {"eid": 4218, "name": "DrawIndexedInstanced", "type": "Draw"}
    }
  },
  "counts": {"idx": 37224, "inst": 1},
  "shader": {"stage": "ps"},
  "io": {
    "in_tex": [
      {
        "rid": "ResourceId::702",
        "name": "SceneDepth",
        "meta": {"type": "Texture2D", "dims": "1920x1080", "fmt": "R32_FLOAT"},
        "stages": ["PS"],
        "slots": [{"stage": "PS", "slot": 3}]
      }
    ],
    "in_tex_meta": {
      "total_bindings": 6,
      "unique_resources": 4,
      "reported_resources": 4,
      "truncated": false,
      "cap": 8,
      "stage_bindings": {"PS": 6}
    },
    "out_rt": [],
    "out_uav": [],
    "out_next": [
      {
        "src": "ResourceId::918",
        "eid": 5112,
        "usage": "PS_Resource",
        "name": "LightingPass",
        "type": "Draw",
        "pass": "LightingPass"
      }
    ]
  },
  "state": {
    "api": "GraphicsAPI.D3D11",
    "source_api": "D3D11",
    "limited_to_source_api": false
  }
}
```

Notes:

- `io.in_tex` is a deduplicated resource list across stages, not a direct mirror of shader reflection counts
- use `io.in_tex_meta` and `io.out_*_meta` to judge truncation or partial coverage
- `context.parent_pass` is the nearest enclosing marker; `context.root_pass` is the outermost enclosing marker in the action path

## 13. `debug_save_overlay`

Purpose:

- export a debug overlay texture for one event
- support highlight, wireframe, depth, and overdraw style checks

Input:

```json
{
  "eid": 4217,
  "overlay": "drawcall",
  "rid": "ResourceId::918",
  "dest": "PNG"
}
```

## 14. `debug_save_texture`

Purpose:

- export one texture resource from the active capture
- support before/after validation when reverse-engineering action outputs

Input:

```json
{
  "rid": "ResourceId::918",
  "eid": 4217,
  "dest": "PNG"
}
```

## Notes

- marker/pass filters should be wired through any list-producing tool
- all heavy payloads belong to separate deep tools, not the summary tools above
- pass classification and report generation are intentionally outside MCP
