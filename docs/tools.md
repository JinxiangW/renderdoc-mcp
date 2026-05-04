# V1 Tool Specs

All tools below default to `mode=summary`.

## Live Window Targeting

Live qrenderdoc tools accept an optional `window_id`.

- Use `list_live_windows` when multiple qrenderdoc windows may be open.
- Pass the returned `window_id` to every live call that should target that capture.
- Omit `window_id` only when exactly one live bridge is active.
- Helper scripts also read `RENDERDOC_MCP_WINDOW_ID`.

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
{
  "window_id": "105880-420776f9"
}
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

## 2a. `list_live_windows`

Purpose:

- enumerate live qrenderdoc bridge windows
- provide `window_id` values for explicit target selection
- avoid sending live requests to the wrong capture when several windows are open

Input:

```json
{}
```

Summary output:

```json
{
  "count": 2,
  "windows": [
    {
      "window_id": "105880-420776f9",
      "pid": 105880,
      "loaded": true,
      "capture_path": "C:/Caps/world/Endfield-frame7146.rdc",
      "api": "GraphicsAPI.D3D11"
    }
  ]
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
- CBV bindings include `byteOffset`, `byteSize`, `elementByteSize`, and buffer size when RenderDoc exposes descriptor ranges
- `cbufs.variables` is a preview, not necessarily the full variable list
- `sig.inputs` and `sig.outputs` are useful for action reverse work and output-write analysis

## 8. `inspect_cbuffer_values`

Purpose:

- read actual constant-buffer values for one stage at one event
- expose the bound buffer RID plus byte range, so large ring-buffer bindings are distinguishable
- fall back to raw rows when reflection names are missing or variable decoding fails

Input:

```json
{
  "eid": 4211,
  "stage": "ps",
  "slot": 5,
  "raw": false
}
```

Summary output:

```json
{
  "eid": 4211,
  "stage": "ps",
  "shader": {"name": "BasePassPS", "entry": "main", "sid": "ResourceId::205"},
  "cbufs": [
    {
      "slot": 5,
      "block_index": 3,
      "name": "Material",
      "bound": {
        "rid": "ResourceId::1194160",
        "byteOffset": 98304,
        "byteSize": 208,
        "bufferSize": 4194304
      },
      "variables": [
        {
          "name": "_CharacterParams0",
          "offset": 0,
          "type": {"type": "Float", "rows": 1, "cols": 4},
          "value": [1.0, 0.5, 0.0, 1.0]
        }
      ]
    }
  ]
}
```

Notes:

- `slot` filters by fixed cbuffer binding number when reflection provides it; it also accepts the reflection block index as a fallback
- when `raw=true`, the output also includes raw 16-byte rows decoded as `float4`, `int4`, and `uint4`

## 9. `read_buffer`

Purpose:

- read a byte range from a live buffer resource
- decode constant buffers, raw buffers, and structured buffers without relying on shader reflection

Input:

```json
{
  "rid": "ResourceId::1194160",
  "offset": 98304,
  "length": 208,
  "format": "float4",
  "stride": null,
  "eid": 4211
}
```

Supported `format` values:

- `raw`: 16-byte rows with hex plus `float4/int4/uint4` interpretations
- `float4`, `uint4`, `int4`
- `matrix`, `float4x4`, or `floatMxN` for 1-4 rows/columns
- `structured`, with `stride`, or `structured:48`

## 10. `get_shader_disasm`

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

## 11. `inspect_mesh`

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

## 12. `get_frame_packet`

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

## 13. `get_pass_packet`

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

## 14. `get_draw_packet`

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

## 15. `debug_save_overlay`

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

## 16. `debug_save_texture`

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
