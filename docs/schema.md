# Schema Policy

## Core Policy

All MCP request and response payloads must be compact by default.

- Default mode is `summary`
- Large payloads require explicit opt-in
- Repeated static metadata should be referenced by ID, not re-sent
- Responses should be shaped for AI consumption, not UI mirroring

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

## Terminology Policy

- Use standard graphics terms
- Do not add simplified TA-only aliases by default
- Keep names close to D3D / RenderDoc vocabulary

## Transport Policy

- Prefer JSON-safe scalar data
- Export large artifacts to files and return `path`
- Base64 only for explicitly requested small slices or previews
