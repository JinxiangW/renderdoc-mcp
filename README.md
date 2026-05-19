# RenderDoc MCP

RenderDoc MCP workspace for a TA-focused, token-efficient analysis server.

## Goals

- Prioritize material debugging, draw call location, reverse analysis, and model/texture export.
- Support both live `qrenderdoc` workflows and offline `.rdc` analysis.
- Live qrenderdoc mode supports parallel windows; use `list_live_windows` and pass
  `window_id` when more than one bridge window is active.
- Prefer compact structured responses over large raw payloads.
- Use standard graphics terminology without adding a separate TA translation layer.

## Working Rules

- All MCP-related planning, implementation, and docs live under this repository.
- Default response mode is summary-first, detail-on-demand.
- Marker/pass filtering should be supported consistently across analysis tools.
- Two-stage workflows are acceptable and preferred for token-heavy operations.

## Key Docs

- [Feature Tree](./docs/feat-tree.md)
- [Schema Policy](./docs/schema.md)
- [Checklist](./docs/checklist.md)
- [UE Workflow Roadmap](./docs/ue_renderdoc_workflow.md)
- [UE-Side MCP Checklist](./docs/ue_side_mcp_checklist.md)
- [RenderDoc MCP Checklist](./docs/renderdoc_mcp_checklist.md)
- [Capture Context Sidecar](./docs/capture_context.md)

## Local Setup

Install the qrenderdoc bridge extension and bundled Ruri shader decompiler:

```powershell
py -3 scripts\install_ext.py
```

Restart RenderDoc after running the installer. The shader edit/decompile menu will include `Ruri DXBC -> HLSL`, `Ruri DXIL -> HLSL`, and `Ruri SPIR-V -> HLSL`.
