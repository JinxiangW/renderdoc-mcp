# UE-Side MCP Checklist

## Goal

UE-side MCP should provide engine context and control surfaces that RenderDoc alone cannot infer reliably.

This is the handoff checklist for agents working on the UE side.

## Coordination Contract

UE-side MCP does not need to call `renderdoc-mcp` directly.

The expected coordination model is:

- UE-side MCP produces `.rdc` captures
- UE-side MCP writes a JSON sidecar next to each capture
- `renderdoc-mcp` reads that sidecar through `get_capture_context`
- diff workflows compare sidecars first, then compare RenderDoc packet artifacts

The sidecar contract reference lives in [capture_context.md](D:/renderdoc-mcp/docs/capture_context.md).

## Minimum Sidecar Fields

These are the fields `renderdoc-mcp` most needs UE-side MCP to provide consistently.

- [x] `engine.project`
- [x] `engine.build`
- [x] `engine.rhi`
- [x] `engine.shader_platform`
- [x] `engine.feature_level`
- [x] `scene.map`
- [x] `scene.world`
- [x] `camera.name`
- [x] `camera.loc`
- [x] `camera.rot`
- [x] `view.size`
- [x] `view.screen_pct`
- [x] `cvars`

## Strongly Recommended Sidecar Fields

- [x] `capture.reason`
- [x] `capture.frame_hint`
- [x] `capture.user_note`
- [x] `selection.actor`
- [x] `selection.component`
- [x] `selection.material`
- [x] `selection.asset`
- [x] `rdg.focus_pass`
- [x] `rdg.pass_filters`
- [x] `scalability`

## Sidecar Rules

- [x] write one JSON object per capture
- [x] keep it next to the `.rdc` file
- [x] prefer `<capture>.rdc.context.json`
- [x] keep field names stable across captures
- [x] store values as facts, not interpretations
- [x] keep arrays compact and deterministic
- [x] keep `cvars` limited to values that matter for render reproduction

## Capture Control

- [ ] trigger RenderDoc capture from PIE, standalone, and packaged workflows
  Note: `editor`, `PIE`, and `standalone` are verified. `packaged` code path exists but real packaged validation is still blocked by a project/engine cook failure unrelated to MCP logic.
- [x] support capture-next-frame and capture-after-N-frames
- [x] support named capture requests for scripted debugging flows
- [x] expose capture success/failure and saved capture path

## Capture Context

- [x] return current map / level / world name
- [x] return active camera transform and projection basics
- [x] return active viewport size and screen percentage
- [x] return current RHI, shader platform, feature level, and build config
- [x] return key render CVars used for debugging and reproduction
- [x] persist a context snapshot next to each capture

## UE Semantic Mapping

- [x] map selected actor/component to likely draw or pass markers
- [x] map material / material instance names to shader or pass context
- [x] map RDG pass names or debug labels into stable queryable output
  Note: label normalization is implemented and exposed. Automatic RDG pass harvesting from UE debug tooling is not yet implemented.
- [x] expose object selection context for mesh/debug-selection workflows

## RenderDoc Handoff

These items directly improve `renderdoc-mcp` usefulness without requiring tighter integration.

- [x] save the sidecar path alongside each capture result
- [x] keep capture filenames stable and human-readable when possible
- [x] include the exact viewport/camera used for the capture
- [x] include render-affecting CVars that changed from project defaults
- [x] include current selection when the capture was taken for a specific object issue
- [x] include any RDG or marker hints already available in UE debug tooling
- [x] include a short capture reason for later diff/report workflows

## Debug Workflow Helpers

- [x] provide a one-shot "capture current selection" action
- [x] provide a one-shot "capture current viewport issue" action
- [x] expose useful toggles for debug viewmodes or diagnostic CVars
- [x] support recording reproduction notes with a capture

## Diff / Regression

- [x] capture the same scene under two configurations and store both context blobs
- [x] expose structured diff inputs: CVars, material switches, scalability, RHI
- [x] emit comparison metadata for downstream RenderDoc-side analysis

## Current Validation Notes

- [x] `editor` capture flow verified against live `RenderingMCP` editor
- [x] `PIE` capture flow verified against live `RenderingMCP` editor
- [x] `standalone` capture flow verified through `renderdoccmd` + `UnrealEditor.exe -game`
- [ ] `packaged` capture flow is not yet verified because current project/engine cook fails before a packaged executable is produced

## Contract Notes

- UE-side MCP should not re-implement RenderDoc inspection.
- UE-side MCP should provide context, control, and semantic mapping.
- RenderDoc-side MCP should remain the source of truth for frame evidence.
