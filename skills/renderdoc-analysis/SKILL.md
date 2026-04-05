---
name: renderdoc-analysis
description: Analyze RenderDoc evidence gathered from observe-only MCP tools. Use when Codex needs to explain what a pass likely does, trace resource flow across passes, summarize material or shader usage, reverse-engineer a frame's rendering pipeline, or generate concise evidence-backed reports from `list_passes`, `get_*_packet`, and `inspect_*` results.
---

# RenderDoc Analysis

Use this skill only after collecting facts from `renderdoc-mcp`.

Keep the boundary strict:

- Treat MCP as the observe layer.
- Treat this skill as the analysis layer.
- Never require removed MCP analysis endpoints.
- Base every judgment on packet fields or inspect outputs that can be named explicitly.
- Treat scripts as evidence producers, not final arbiters.
- The final semantic conclusion and report assembly must be reviewed and authored by the agent.

## Quick Route

Map the user request to one of these analysis tasks:

- `analyze-pass`
- `trace-resource-flow`
- `analyze-material-usage`
- `build-frame-report`
- `reverse-render-pipeline`

Default tool order:

1. Narrow the scope with `find_events` or `list_passes`.
2. Pull evidence with `get_frame_packet`, `get_pass_packet`, or `get_draw_packet`.
3. Enrich with `inspect_pipeline_state`, `inspect_shader`, `inspect_texture_usage`, and `inspect_mesh` only where they materially help.
4. When screen contribution matters, export a `Highlight Drawcall` overlay to see whether the action is local or full-screen.
5. Then compare the current RT against the previous action's RT to see what this action actually changed on screen.
6. Produce a judgment only after citing the evidence packet fields that support it.
7. For any pass type, summarize:
   - likely role
   - major inputs
   - major outputs and downstream consumers
   - shader behavior
   - visible screen contribution when available
   - uncertainties

Read these references as needed:

- For task-to-tool routing: `references/tool-map.md`
- For workflows: `references/workflows.md`
- For lightweight classification rules: `references/heuristics.md`
- For semantic pass categories: `references/pass-taxonomy.md`
- For output formats and acceptance bars: `references/report-shapes.md`

Use these scripts when they help:

- `scripts/analyze_pass.py`
- `scripts/build_pass_report.py`
- `scripts/build_frame_report.py`
- `scripts/build_resource_flow_report.py`
- `scripts/classify_pass_taxonomy.py`
- `scripts/scan_pass_visuals.py`
- `scripts/scan_frame_passes.py`

Script boundary:

- Scripts may export images, gather packets, compute overlay coverage, build diffs, and propose taxonomy candidates.
- Scripts may emit intermediate labels such as `translucent_signage_local` or taxonomy candidates such as `overlay_projection / decal_pass`.
- Scripts should not be treated as the final semantic authority when evidence conflicts or when multiple candidates are plausible.
- The agent must review the script outputs, decide which evidence matters, resolve conflicts, and write the final conclusion in human-readable form.

## Task Routing

### `analyze-pass`

Use when the user asks:

- what a pass is doing
- whether a pass looks like depth, colour, compute, gbuffer, lighting, or post
- why a pass exists
- what each GBuffer render target or channel likely means

Default call chain:

1. `list_passes`
2. `get_pass_packet`
3. `get_draw_packet` for a representative event if the packet does not already contain enough context
4. `inspect_pipeline_state`
5. `inspect_shader`
6. `inspect_texture_usage` for the most important outputs
7. for GBuffer-like passes, inspect the first major downstream consumer passes and read the current plus downstream shaders before assigning RT/channel semantics
8. when available, pass downstream consumer shader evidence into `scripts/analyze_pass.py` with `--consumer-shader-evidence`
9. when available, pass overlay and before/after RT comparison notes into `scripts/analyze_pass.py` with `--visual-validation`

Minimum evidence:

- `list_passes` or `get_pass_packet`
- one representative draw or dispatch when available
- `inspect_pipeline_state`
- `inspect_shader` for the dominant stage

Acceptance standard:

- State the judgment, confidence, and concrete evidence.
- Separate evidence from inference.
- Name follow-up checks when the evidence is incomplete.
- If the pass looks like GBuffer, treat per-RT or per-channel meaning as provisional until downstream usage supports it.
- Regardless of pass type, summarize what the pass reads, what it writes, and what the shader appears to be doing.
- If overlay or before/after RT images are available, summarize what the action visibly drew or changed on screen.
- Do not stop at geometric labels such as `mixed`, `local overlay`, `fullscreen init`, or `projected` if they do not answer what the pass is actually drawing.
- If the pass-level evidence does not support a concrete semantic label like `logo translucent`, `opaque character`, `shadow map`, `decal`, or `lighting composite`, descend to action or action-cluster analysis instead of emitting a vague pass conclusion.

Recommended script:

- `scripts/analyze_pass.py` for structured analysis output
- `scripts/build_pass_report.py` for markdown output built from the same analysis logic
- use `--consumer-shader-evidence` when you have downstream consumer shader summaries or disassembly
- use `--visual-validation` when you have concrete before/after RT comparison notes

### `trace-resource-flow`

Use when the user asks:

- where a texture came from
- which pass first writes a resource
- where an output gets consumed next

Default call chain:

1. `inspect_texture_usage`
2. `get_pass_packet` for the producer or key consumer passes
3. `get_draw_packet` for representative producer or consumer events only if needed

Minimum evidence:

- `inspect_texture_usage`
- `get_pass_packet` for producing or consuming passes when needed
- `get_draw_packet` for representative producer or consumer events when needed

Acceptance standard:

- Identify producer, first consumer, and important downstream consumers when available.
- Distinguish reads from writes.
- Call out uncertainty if the chain is partial.

### `analyze-material-usage`

Use when the user asks:

- which resources a material or draw uses
- what a shader samples
- which bindings are likely important

Default call chain:

1. `get_draw_packet`
2. `inspect_shader`
3. `inspect_texture_usage` for the most important sampled or output textures
4. `inspect_mesh` only if geometry context matters

Minimum evidence:

- `get_draw_packet`
- `inspect_shader`
- `inspect_texture_usage` for the most important outputs or sampled textures

Acceptance standard:

- List the bound shader stage and major resource bindings.
- Explain which textures or buffers appear central versus incidental.
- Avoid pretending to know semantics that are not supported by packet evidence.

### `build-frame-report`

Use when the user wants:

- a concise frame summary
- a readable review of the main render pipeline
- a compact report for another engineer or TA

Default call chain:

1. `get_frame_packet`
2. `get_pass_packet` for important passes
3. targeted `inspect_*` calls for only the passes discussed in the report

Minimum evidence:

- `get_frame_packet`
- `get_pass_packet` for important passes
- targeted `inspect_*` calls for only the passes discussed in the report

Acceptance standard:

- Organize by frame overview, key passes, and next checks.
- Keep the report concise and evidence-backed.
- Avoid dumping every pass unless the user explicitly asks for exhaustive output.

### `reverse-render-pipeline`

Use when the user wants:

- a high-level reconstruction of the frame
- a likely ordering of depth, colour, compute, lighting, and post stages
- a reverse-engineering summary from RenderDoc evidence

Default call chain:

1. `list_passes`
2. `get_frame_packet`
3. targeted `get_pass_packet` and `inspect_*` on candidate key passes

Minimum evidence:

- `list_passes`
- `get_frame_packet`
- targeted `get_pass_packet` and `inspect_*` on candidate key passes

Acceptance standard:

- Identify the likely pipeline stages in order.
- Mark uncertain stage labels as hypotheses.
- Cite the pass names, event counts, and resource patterns that led to the reconstruction.

## Invocation Examples

- "Use `list_passes` and `get_pass_packet` first. If the pass looks graphics-heavy, add `inspect_pipeline_state` and `inspect_shader`."
- "For a resource-flow question, start from `inspect_texture_usage` and only pull packets for the producer and first major consumer."
- "For a frame report, keep the report shorter than the union of the packets you inspected."

## Working Rules

- Prefer packet-first analysis over ad hoc guessing.
- Quote packet field names when helpful for traceability.
- Keep judgments compact and readable.
- Use standard graphics terminology.
- If the evidence is insufficient, say that directly instead of overfitting.
- If a report would spend many tokens on raw data, summarize and point to the specific packet fields that matter.
- Treat pass naming as a hint, not a proof.
- Coverage shape is only a routing hint, not a valid final conclusion.
- A pass report is only useful if it answers what category of content the pass is drawing or producing. If not, escalate to action-level analysis.
- Taxonomy and scan scripts provide candidates and supporting evidence; they do not replace agent judgment.
- Final reports should be assembled after the agent has reviewed the supporting evidence files and accepted or rejected the candidate labels.
