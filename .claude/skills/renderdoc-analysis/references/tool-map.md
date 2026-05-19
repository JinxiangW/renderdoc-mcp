# Tool Map

Use this file to choose the minimum observe-tool set for each analysis task.

## Live Target Setup

When a task uses live qrenderdoc data:

- call `list_live_windows` first if more than one qrenderdoc window may be open
- pick the `window_id` whose `capture_path` matches the target capture
- pass that `window_id` to every live MCP tool call
- for bundled scripts, set `RENDERDOC_MCP_WINDOW_ID=<window_id>`

## `analyze-pass`

Start with:

- `list_passes`
- `get_pass_packet`

Add when needed:

- `get_draw_packet` for a representative event
- `inspect_pipeline_state`
- `inspect_shader`
- `inspect_texture_usage` for important outputs

Good stopping point:

- you can name the pass
- you can cite its dominant event type
- you can cite its output pattern or shader stage pattern

## `trace-resource-flow`

Start with:

- `inspect_texture_usage`

Add when needed:

- `get_pass_packet` for producer or consumer context
- `get_draw_packet` when a single event matters more than the pass summary

Good stopping point:

- you can identify producer and first consumer
- you can distinguish downstream major consumers from incidental reads

## `analyze-material-usage`

Start with:

- `get_draw_packet`

Add when needed:

- `inspect_shader` for another stage or fuller binding detail
- `inspect_texture_usage`
- `inspect_mesh`

Good stopping point:

- you can name the dominant stage and entry point
- you can cite the important binding counts or key sampled resources

## `reverse-action`

Start with:

- `get_draw_packet`
- `inspect_mesh` for draw events
- `inspect_shader` for `vs + ps` on draw events, or `cs` on dispatch events

Add when needed:

- `get_pass_packet` for broader pass role or sibling evidence beyond draw-packet context
- Ruri HLSL export for the inspected action shader stages into the action working directory
- `get_shader_disasm` for motif recognition in the decisive stage
- `inspect_texture_usage` for the few outputs or disputed inputs that matter downstream

Good stopping point:

- exported or explicitly failed HLSL artifacts are recorded for the inspected shader stages
- you can list the important `t#`, `u#`, `cb#`, and `vb/ib` inputs
- you can annotate what important input resources do in code
- you can explain the main shader code ranges and what each range does
- you can describe `o#` or UAV outputs with evidence tied to code or downstream consumers
- you can separate hard evidence from inferred material or effect role

## `build-frame-report`

Start with:

- `get_frame_packet`

Add when needed:

- `get_pass_packet` for important passes
- `inspect_pipeline_state`
- `inspect_shader`
- `inspect_texture_usage`

Good stopping point:

- you can identify the frame backbone
- you can justify why each discussed pass matters

## `reverse-render-pipeline`

Start with:

- `list_passes`
- `get_frame_packet`

Add when needed:

- `get_pass_packet`
- `inspect_pipeline_state`
- `inspect_shader`

Good stopping point:

- you can propose a likely stage ordering
- you can cite at least one factual signal for each major stage label
