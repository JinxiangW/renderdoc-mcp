# Feature Tree

## Product Direction

This MCP is aimed at technical artists and graphics debugging workflows, with the first version optimized for:

- material debugging
- draw call location
- reverse analysis of pass/resource flow
- quick mesh inspection
- texture and model export when explicitly requested

Primary APIs:

- D3D11
- D3D12

Supported working modes:

- live analysis against an open `qrenderdoc` session
- offline analysis against `.rdc` files

## Design Principles

- Summary first, raw data second
- Pass/marker filters available everywhere practical
- Event, resource, shader, marker, draw name, and path can all be valid entry points
- Reverse lookup is a first-class feature
- Favor stable identifiers over repeated full objects

## V1 Tool Families

### 1. Session And Capture

- `open_capture`
- `get_capture_status`
- `list_captures`
- `get_frame_packet`

Purpose:

- open or attach to analysis context
- return API, filename, high-level counts, active capture state

### 2. Event Discovery

- `find_events`
- `find_draws_by_shader`
- `find_draws_by_texture`
- `find_draws_by_resource`
- `find_events_by_marker`

Purpose:

- find candidate events from the user’s mental model
- narrow down the frame before deep inspection

### 3. Pass And Pipeline Inspection

- `list_passes`
- `get_pass_packet`
- `get_draw_packet`
- `inspect_pipeline_state`

Purpose:

- answer “this pass uses what resources”
- answer “where did this output come from”
- answer “what is bound here without dumping the whole pipeline”

### 4. Shader Inspection

- `inspect_shader`
- `inspect_shader_bindings`
- `inspect_shader_constants`
- `get_shader_disasm`

Purpose:

- summarize stage, entry point, bindings, constant buffers
- only fetch disassembly on demand

### 5. Mesh And Geometry Inspection

- `inspect_mesh`
- `inspect_mesh_attributes`
- `inspect_mesh_stage_data`
- `export_mesh_csv`
- `export_mesh_fbx`

Purpose:

- quick checks: counts, topology, AABB, attributes
- deeper checks: VS input/output, post-VS, buffer layout reasoning

### 6. Texture And Buffer Inspection

- `inspect_texture_summary`
- `inspect_texture_usage`
- `sample_texture_pixels`
- `export_texture`
- `get_buffer_slice`

Purpose:

- summarize dimensions, format, usage sites
- support explicit export or sampled reads without default raw dumps

## Recommended V1 MCP Tools

These should be the default observe-only tools exposed first:

- `open_capture`
- `find_events`
- `list_passes`
- `get_pass_packet`
- `inspect_pipeline_state`
- `inspect_texture_usage`
- `inspect_shader`
- `inspect_mesh`

## Analysis Boundary

The following should live outside MCP in a separate skill:

- pass classification
- resource-flow interpretation
- material-usage analysis
- frame summaries and report generation

## Deferred / V2

- pixel-history-oriented tools
- full variable tracing inside shader debug
- automated semantic guessing for export pipelines
- performance-first tooling beyond simple action timings
- richer visual thumbnail generation
