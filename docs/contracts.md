# Shared Contracts

## Common Response Envelope

Every tool response should fit this top-level shape:

```json
{
  "ok": true,
  "mode": "summary",
  "data": {},
  "err": null,
  "meta": {
    "cap": "active",
    "truncated": false
  }
}
```

Error shape:

```json
{
  "ok": false,
  "mode": "summary",
  "data": null,
  "err": {
    "code": "capture_not_loaded",
    "msg": "No capture loaded"
  },
  "meta": {
    "cap": null,
    "truncated": false
  }
}
```

## Required Top-Level Fields

- `ok`: success flag
- `mode`: `summary` or `full`
- `data`: payload or `null`
- `err`: error object or `null`
- `meta`: compact metadata

## Meta Fields

- `cap`: capture identifier or `null`
- `truncated`: whether payload was shortened
- `count`: optional total count for list responses
- `next`: optional pagination token or offset

## Shared Request Conventions

### Common Optional Fields

- `mode`: `summary` or `full`
- `limit`: list limit
- `offset`: pagination offset
- `marker`: include-only marker or pass filter
- `exclude_markers`: excluded marker substrings
- `eid_min`: minimum event ID
- `eid_max`: maximum event ID

### Shared Entity Fields

- `cap`: capture selector
- `eid`: event ID
- `rid`: resource ID
- `sid`: shader ID
- `path`: file path
- `stage`: graphics stage

## Compact Naming Policy

- use short stable keys in machine-facing payloads
- use standard graphics terminology
- avoid nested RenderDoc object mirrors

## Shared Summary Shapes

### Action Ref

```json
{
  "eid": 4211,
  "name": "BasePass",
  "type": "Draw",
  "marker": "Opaque"
}
```

### Shader Ref

```json
{
  "sid": "s205",
  "stage": "ps",
  "name": "BasePassPS",
  "entry": "main"
}
```

### Resource Ref

```json
{
  "rid": "r918",
  "name": "GBufferA",
  "type": "Texture2D",
  "fmt": "R8G8B8A8_UNORM",
  "dims": [1920, 1080, 1]
}
```

### Binding Count Block

```json
{
  "srv": 12,
  "uav": 1,
  "cbv": 8,
  "smp": 6,
  "rt": 4,
  "ds": 1
}
```
