# Schema Policy

## Core Policy

All MCP request and response payloads must be compact by default.

- Default mode is `summary`
- Large payloads require explicit opt-in
- Repeated static metadata should be referenced by ID, not re-sent
- Responses should be shaped for AI consumption, not UI mirroring
- Response envelopes are plain JSON dicts, not required to be dataclass objects at runtime

## Identifier Policy

Use stable short identifiers wherever possible:

- `cap`: capture identifier
- `eid`: event ID
- `rid`: resource ID
- `sid`: shader ID
- `mid`: marker or pass identifier when applicable

Do not return full nested RenderDoc objects.

## Response Modes

Every heavy tool should support:

- `summary`: default compact response
- `full`: expanded response

Optional heavy fetches should use explicit booleans such as:

- `include_bindings`
- `include_consts`
- `include_disasm`
- `include_preview`

## Compact Naming

Preferred compact field names:

- `api`
- `name`
- `type`
- `count`
- `items`
- `path`
- `size`
- `fmt`
- `dims`
- `stage`
- `slot`
- `src`
- `dst`

Avoid deep nesting unless it removes meaningful duplication.

## Heavy Data Rules

Never return these by default:

- full draw tree
- full pipeline object graph
- full shader disassembly
- full mesh vertex streams
- raw texture bytes
- large buffer blobs

Instead return:

- counts
- ranges
- sampled previews
- handles or file paths
- compact summaries

## Pagination And Limits

Default list limits:

- `items`: max 50
- string fields: truncate long bodies
- repeated arrays: summarize with `count` and `top`

Heavy text fields should support:

- `offset`
- `limit`
- `truncated`

## Example Shapes

### Capture Summary

```json
{
  "cap": "active",
  "api": "D3D12",
  "path": "C:/captures/foo.rdc",
  "frame": {
    "draws": 1823,
    "dispatch": 43,
    "tex": 912,
    "buf": 377
  }
}
```

### Event Search Result

```json
{
  "count": 3,
  "items": [
    {"eid": 4211, "name": "BasePass", "type": "Draw", "marker": "Opaque"},
    {"eid": 4227, "name": "BasePass", "type": "Draw", "marker": "Opaque"}
  ],
  "truncated": false
}
```

### Pipeline Summary

```json
{
  "eid": 4211,
  "api": "D3D12",
  "pass": "BasePass",
  "sh": {
    "vs": {"sid": "s101", "name": "BasePassVS", "entry": "main"},
    "ps": {"sid": "s205", "name": "BasePassPS", "entry": "main"}
  },
  "res": {
    "srv": 12,
    "uav": 1,
    "cbv": 8,
    "rt": 4,
    "ds": 1
  }
}
```

### Fixed-Function State Note

When fixed-function state appears inside draw packets, treat it as API-limited:

- current `blend` / `depth` / `rast` extraction is sourced from D3D11 pipeline state
- responses should carry the source API and a flag when the current capture API is outside that supported path
- callers must not assume those fixed-function fields are equally populated on Vulkan or D3D12 captures

### Draw Packet Context Note

When using `get_draw_packet` for reverse engineering:

- `context.parent_pass` is the nearest enclosing marker in the action path
- `context.root_pass` is the outermost enclosing marker in the same action path
- `context.position` and `context.neighbors` are computed within the nearest enclosing marker scope

### Draw Packet IO Note

When using `get_draw_packet.io`:

- `in_tex` is a deduplicated resource list across bound stages, not a direct copy of one stage's reflection bindings
- compare packet completeness using `in_tex_meta`, `out_rt_meta`, `out_uav_meta`, and `out_next_meta`
- do not compare `inspect_shader.bind.srv` directly against `len(io.in_tex)` as if they were the same counting basis
- downstream `out_next` is capped and should be treated as an early-consumer sample, not an exhaustive usage list

### Shader Inspection Note

When using `inspect_shader` for action reverse engineering:

- `bindings` is the stage-local binding table and is a better source for `t#`, `u#`, `cb#`, and `s#` than pass-level summaries
- `cbufs` is a compact preview of constant-buffer contents and may truncate long buffers
- `sig.inputs` and `sig.outputs` help map stage interfaces and output registers before deeper disassembly work

### Disassembly Window Note

When using `get_shader_disasm`:

- use `line_start`, `line_end`, and `lines` when you need to cite code ranges
- the returned window is paged; one call is not guaranteed to contain every decisive range

### Mesh Inspection Note

When using `inspect_mesh` for action reverse engineering:

- `attrs` is the input-layout view
- `vbs` and `ib` summarize bound vertex and index buffers
- treat these as binding facts, not as a substitute for full mesh export

## Terminology Policy

- Use standard graphics terms
- Do not add simplified TA-only aliases by default
- Keep names close to D3D / RenderDoc vocabulary

## Transport Policy

- Prefer JSON-safe scalar data
- Export large artifacts to files and return `path`
- Base64 only for explicitly requested small slices or previews
