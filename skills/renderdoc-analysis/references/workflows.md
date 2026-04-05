# Workflows

## Pass Analysis

Use this sequence:

1. Call `list_passes` to find the target pass by marker or by rough position in the frame.
2. Call `get_pass_packet` for the selected pass.
3. Read pass stats, representative events, and pass outputs from the packet.
4. Call `inspect_pipeline_state` for the representative draw or dispatch.
5. Call `inspect_shader` for the dominant stage.
6. If outputs matter, call `inspect_texture_usage` on the main render targets or UAVs.
7. If the pass output is visually important, export a `Highlight Drawcall` overlay for the action.
8. If needed, also export the current RT and the previous action's RT for image comparison.
9. Use the overlay first to answer "is this a local draw or a full-screen pass".
10. Use before/after RT comparison to answer "what pixels or objects actually changed".
11. Treat visual comparison as validation of screen-space contribution, not as a replacement for shader or packet evidence.
12. If the pass looks like a GBuffer or multi-RT graphics pass, inspect the first major consumer of each important RT.
13. Read the current shader and the downstream consumer shader before assigning likely RT or channel semantics.
14. If you have downstream consumer shader evidence files, pass them into `scripts/analyze_pass.py` with `--consumer-shader-evidence`.
15. If you have visual comparison notes, pass them into `scripts/analyze_pass.py` with `--visual-validation`.
16. Optionally run `scripts/analyze_pass.py` on the collected packet files.
17. Produce:
   - role
   - inputs
   - outputs
   - shader summary
   - visual validation
   - interpretation
   - uncertainties
   - next checks

Minimum acceptance:

- cite the pass name and event counts
- cite at least one packet or inspect field
- separate facts from interpretation
- if image comparison is used, state exactly which region or object changed on screen
- treat per-RT or per-channel roles as provisional unless downstream usage supports them
- do not finalize the pass report with only coverage-shape language such as `fullscreen`, `local`, or `mixed`
- if the pass still cannot be named semantically, split it into action clusters and analyze those clusters directly

## Resource Flow Analysis

Use this sequence:

1. Call `inspect_texture_usage` for the resource.
2. Identify producer, first read, and important downstream consumers.
3. If a producer or consumer pass needs more context, call `get_pass_packet`.
4. If a specific event matters, call `get_draw_packet`.
5. Produce a chain in this order:
   - producer
   - immediate use
   - major downstream use

Minimum acceptance:

- distinguish read and write edges
- call out missing producer or missing consumer data
- avoid claiming a full chain when only a partial chain is visible

## Material Or Shader Usage Analysis

Use this sequence:

1. Start from `get_draw_packet`.
2. Inspect the bound stage with `inspect_shader`.
3. Use packet IO plus shader bindings to identify major inputs and outputs.
4. Call `inspect_texture_usage` only for the most relevant textures.
5. Summarize:
   - dominant shader stage
   - major bindings
   - likely material role

Minimum acceptance:

- cite stage, entry point, and binding counts
- mention only bindings that matter to the question
- mark semantics as inferred when the names are weak

## Frame Report

Use this sequence:

1. Call `get_frame_packet`.
2. Select the passes worth discussing.
3. For each important pass, call `get_pass_packet`.
4. Add `inspect_pipeline_state` and `inspect_shader` only for the key representative events.
5. Assemble a report with:
   - frame overview
   - key passes
   - resource-flow notes
   - next checks

Minimum acceptance:

- keep the report shorter than the underlying packet dump
- mention why a pass is important
- keep all conclusions traceable to observe data
