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

### RenderDuck free camera

The live tools `get_replay_camera_state`, `configure_replay_camera`, and
`reset_replay_camera` use the updated RenderDuck TextureViewer API. They configure
the visible Free camera panel without mouse/keyboard automation or arbitrary
script execution. The frontend must provide `GetReplayCameraState`,
`ConfigureReplayCamera`, and `ResetReplayCamera`; older frontends return
`unsupported_frontend`. Only a local D3D11 capture is supported.

For RenderDuck's separate extension directory, install with:

```powershell
py -3 scripts/install_ext.py --frontend renderduck --incremental --skip-decompiler
```

Restart the frontend to load extension updates and reconnect the MCP client to
refresh its tool list. Existing RenderDoc installations keep the default
`--frontend renderdoc` path. Use `list_live_windows` and an explicit `window_id`
when both the old and updated windows are open.

`configure_replay_camera` accepts `view` and `projection` as 16 mathematical
row-ordered values for column-vector multiplication. Each `fields` entry supplies
`semantic`, `shader` (ResourceId string), `stage` (VS/HS/DS/GS/PS/CS), `slot`,
`offset`, `first_event`, `last_event`, `row_major`, and `row_vector`.
Offsets are relative to the bound CB range. Matrix storage and multiplication
convention are independent. Inspect `semantics` in the state response for the
frontend's supported meanings, including `RelativeViewProjection` and
`InverseRelativeViewProjection` for shaders using world-position minus camera-position.

Optional `eid` and `output_rid` select the event and displayed texture; `flip_y`
controls only the texture display orientation. `speed`, `forward` (-Z/+Z),
`enabled`, and `show` control the camera and configuration panel. Supply
`expected_capture` to prevent modifying a window that has switched captures.
After configuring/resetting, poll state until `busy` and `pending_update` are
false and check `last_error`. A queued response does not yet prove GPU replay
succeeded. Use `include_fields=true` to read back the full visible configuration.

Regression checks: `python -m unittest tests.test_replay_camera tests.test_runtime
tests.test_capture_ui_thread`. A live owned-fixture check is available through
`scripts/validate_replay_camera.py --window-id ID --dest NEW_DIRECTORY` and uses
the actual FastMCP tool protocol plus image comparison against a directly
rendered camera reference.

#### Camera recipes

`configure_replay_camera_recipe(recipe, run=true, show=true, expected_capture=..., window_id=...)`
lets an agent supply verified CB layout/meaning instead of expanded shader IDs, event ranges
and matrix values. It uses the native **Free camera → Recipe...** entry point and
the bundled Python scanner. `run=false` populates the window without scanning. The same
recipe can be imported and run in the window with MCP stopped.

A version-1 recipe explicitly gives `row_major`, `row_vector`, `forward`, `camera` matrix
locators (`view`, `projection`, optional `inverse_view`: CB `slot` and byte `offset`), and
`layouts` (`slot`, `stages`, semantic/offset `fields`). For a per-object `ModelView`, give
its `model_offset` as an independent ownership check; the native implementation retains
the object transform. Independent projections use `projection_offset` in the same CB.
Profiles and their different import/restore paths are documented in
[RenderDuck game profiles](https://github.com/LesFloraison/RenderDuck/tree/freecamera/docs/freecamera-profiles).

The script searches for a unique camera when `reference_event` is omitted. With multiple
candidates, inspect the reported EIDs and supply one verified main-camera event. That hint
belongs to the current capture; native portable export removes it. Slot/offset meanings
remain agent-authored and must be revised when shader layouts change. Never claim that
matching declared fields proves full game coverage. Put known gaps in `unresolved`.

Poll `get_replay_camera_state` until `scanning` is false, then inspect `last_error`,
`scan_report`, `scan_partial`, and `scan_field_count`. A partial result preserves the active
configuration. After reviewing it, call `apply_replay_camera_recipe(expected_capture=...,
window_id=...)` to explicitly accept it. Poll `busy`/`pending_update` through completion.
Full matches apply automatically. A successful application closes the panel and saves the
recipe plus expanded fields in the native version-3 sidecar; reopening restores them disabled.
The frontend advertises `recipe_supported`; older builds return `unsupported_frontend`.

Version-2 replay recipes add explicit `passes` (`skip` / `colour_bypass`, inclusive action
EIDs, colour texture/subresource/view mappings, analysis `reason`) and require the entire
RDC `capture.size` / `capture.sha256` when referencing events or textures. The native worker
checks the fingerprint. An empty Pass list means no overrides. Camera and Pass rules apply
together and reset together; reopening restores both forms disabled. State advertises
`recipe_versions`, `recipe_passes_supported`, `scan_pass_count`, `active_pass_count` and
`unresolved`. Version-1 camera recipes remain supported. No default game scanner runs when
the recipe is empty. Export full recipes to retain references; camera-layout export drops them.

Capture-specific event hints require a fingerprint even in v1 standalone recipes. Existing
authenticated sidecars supply their fingerprint when restoring an older recipe; portable v1
layouts without concrete event references continue to run unchanged.

Free-camera coordinates: both `configure_replay_camera` and recipe JSON accept `world_up`
(`+X`, `-X`, `+Y`, `-Y`, `+Z`, `-Z`; default `+Y`). `forward` is camera-local `-Z`/`+Z`.
World up controls Q/E, yaw and the no-roll constraint. Horizontal input also accounts for
projection mirroring. State lists `world_up_axes`; unsupported old frontends reject nondefault
world up. No matrix storage/transposition or game-layout conversion is implied.

Install the qrenderdoc bridge extension and bundled Ruri shader decompiler:

```powershell
py -3 scripts\install_ext.py
```

Restart RenderDoc after running the installer. The shader edit/decompile menu will include `Ruri DXBC -> HLSL`, `Ruri DXIL -> HLSL`, and `Ruri SPIR-V -> HLSL`.
