# RenderDoc MCP Checklist

## Goal

Keep `renderdoc-mcp` focused on frame evidence, packet inspection, resource tracing, and shader inspection.

## Done

- [x] compact frame / pass / draw packet tools
- [x] live bridge integration for qrenderdoc
- [x] shader disassembly inspection
- [x] shader debug/source availability summary in `inspect_shader`
- [x] `get_shader_source` for source-first shader reads when symbols are available
- [x] `inspect_texture_usage(name=...)` lookup by actual resource name
- [x] lazy offline installation discovery so MCP startup does not require RenderDoc tooling up front
- [x] structured `run-local-json` errors when live-only tools are unavailable
- [x] standalone CLI exit code fix for envelope dictionaries
- [x] request-ID-scoped bridge IPC with legacy protocol fallback
- [x] stable capture-context ingestion path from UE-side metadata blobs
- [x] first-pass capture-context diff tool
- [x] first-pass pass-list/frame-packet diff tool
- [x] general compact packet artifact diff tool
- [x] source-first unified shader code helper
- [x] specialized draw-packet diff helper
- [x] specialized texture-usage diff helper
- [x] UE semantic hints helper and packet-side hint attachment

## Next

- [ ] add specialized pass/resource-flow diff helpers that consume live MCP outputs directly

## Boundaries

- UE-side owns engine context, object semantics, and capture triggering
- `renderdoc-mcp` owns RenderDoc evidence collection and packet shaping
