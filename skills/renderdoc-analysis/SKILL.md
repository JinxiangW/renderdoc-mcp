---
name: renderdoc-analysis
description: Analyze RenderDoc observe-layer evidence from renderdoc-mcp. Use for action reverse engineering, pass classification, resource-flow tracing, shader/material usage, frame reports, and pipeline reconstruction.
---

# RenderDoc Analysis
Use this skill only after collecting facts from `renderdoc-mcp`.
Working boundary:
- MCP is the observe layer.
- This skill is the analysis layer.
- Name packet fields or inspect outputs when you cite evidence.
- Treat script outputs as evidence helpers, not final authority.
- If evidence is insufficient, stop at a broader family.

Task routes:
- `analyze-pass`
- `trace-resource-flow`
- `analyze-material-usage`
- `reverse-action`
- `build-frame-report`
- `reverse-render-pipeline`

Read only the references you need:
- routing: `references/tool-map.md`
- workflow: `references/workflows.md`
- taxonomy: `references/pass-taxonomy.md`, `references/render-pass-taxonomy.md`
- category checks: `references/pass-checklists.md`
- conclusion rules: `references/conclusion-rules.md`
- evidence guardrails: `references/evidence-guardrails.md`
- report format: `references/report-format.md`
- shader motifs: `references/shader-patterns.md`

Script rule:
- Always read `*_summary.json` first.
- Read `*_full.json` only when summary confidence is `low` or `needs_detail` is non-empty.
- Do not dump a whole full JSON into context when a few fields are enough.

Useful scripts:
- `scripts/build_pass_evidence_bundle.py`
- `scripts/scan_pass_visuals.py`
- `scripts/classify_pass_taxonomy.py`
- `scripts/analyze_pass.py`

## analyze-pass

Use for pass role, pass family, RT meaning, or semantic naming.

Decision tree:

1. `get_pass_packet` is the required entry.
2. If the pass is only clear/copy/resolve, conclude and stop.
3. Use `data.rep_draw` first. It already includes `pipe` and `shader`.
4. Only call `get_draw_packet`, `inspect_pipeline_state`, or `inspect_shader` when you need a non-representative event.
5. Cluster the pass before naming it. Let the dominant cluster decide the family.
6. Default to one `inspect_texture_usage` on RT slot 0.
7. Only inspect a second RT when the pass is multi-RT and RT semantics matter. Hard cap: 2 RTs.
8. Export overlay or prev/current RT only when screen contribution is genuinely unclear.
9. For multi-RT or GBuffer-like passes, inspect only the first key downstream consumer that is needed to keep RT semantics honest.
10. Before writing the answer, read `references/report-format.md`.

## trace-resource-flow

Use for producer, first consumer, and downstream chain questions.

Default path:

1. `inspect_texture_usage`
2. `get_pass_packet` only for the producer or first key consumer
3. `get_draw_packet` only if one specific event matters
4. Write the result with `references/report-format.md`

## analyze-material-usage

Use for shader bindings, sampled textures, and likely material role.

Default path:

1. `get_draw_packet`
2. use packet shader data first
3. call `inspect_shader` only if packet shader data is not enough
4. `inspect_texture_usage` only for the few bindings that matter
5. `inspect_mesh` only if geometry context changes the answer
6. Write the result with `references/report-format.md`

## reverse-action

Use for one draw or dispatch when the goal is to explain shader behavior, resource usage, code segments, and output semantics in detail.

Default path:

1. `get_draw_packet` is the required entry.
2. Use draw-packet `context` first for marker path, parent pass, root pass, position, and neighbors. Add `get_pass_packet` only when broader pass role or sibling evidence beyond packet context matters.
3. For draws, `inspect_mesh` is the default, not optional. You need vertex attributes plus vertex/index buffer bindings before explaining the shader. For dispatches, mark geometry as not applicable.
4. For draws, inspect both `vs` and `ps` unless one stage is proven irrelevant. For dispatches, inspect `cs`.
5. Build a binding inventory before drawing conclusions:
   - `inspect_shader.bind`
   - `inspect_shader.bindings`
   - `inspect_shader.cbufs`
   - `inspect_shader.sig`
   - draw-packet `io`
6. Use `get_shader_disasm` to segment the decisive stage by code ranges. At minimum identify:
   - declaration / resource setup
   - input reconstruction or coordinate prep
   - texture sampling and decode blocks
   - lighting or material evaluation blocks
   - output packing / final writes
7. Use disassembly line ranges explicitly. Report findings as ranges such as `lines 1-40`, `41-96`, not just free-form summaries.
8. Treat resource semantics as unproven until tied to actual code use. Resource name, format, dimensions, and downstream use all matter.
9. Use `inspect_texture_usage` for the few inputs or outputs that change the conclusion. Default priority:
   - one main output RT or UAV
   - one disputed input texture
   - one downstream consumer if output channel meaning is uncertain
10. Use `io.in_tex_meta` and `io.out_*_meta` to judge partial coverage. Do not compare `inspect_shader.bind.srv` directly against `io.in_tex` as if they were the same counting basis.
11. Export overlay or before/after RT only when visible contribution itself is disputed; do not let overlay work replace shader analysis.
12. Write the result with `references/report-format.md` and use `references/shader-patterns.md` for motif recognition.

Reverse-action acceptance bar:

- list the key `t#`, `u#`, `cb#`, and `vb/ib` inputs
- explain what each important resource is doing, not just that it is bound
- split the decisive shader into line ranges with a function for each range
- describe `o#` or UAV outputs with channel-level evidence when available
- keep pass-family guesses secondary to shader/resource facts
- do not use `BLENDWEIGHTS/BLENDINDICES` as semantic proof beyond mesh-format context

## build-frame-report

Use for a concise frame summary.

Default path:

1. `get_frame_packet`
2. `get_pass_packet` for only the passes you discuss
3. add targeted `inspect_*` calls only where they change the conclusion
4. Write the result with `references/report-format.md`

## reverse-render-pipeline

Use for high-level frame reconstruction.

Default path:

1. `list_passes`
2. `get_frame_packet`
3. targeted `get_pass_packet` on key passes
4. add `inspect_*` only on disputed stages
5. Write the result with `references/report-format.md`

Final rules:

- Prefer broad families over shaky narrow labels.
- Do not let one representative draw define the whole pass.
- Do not translate `fullscreen`, `local`, `simple mesh`, or `skeletal mesh` directly into semantics.
- For disputed passes, force `top1 / top2 / support / counter-evidence / decision / final name`.
