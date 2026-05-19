# Workflows

## Summary First

- Read `*_summary.json` first.
- Read `*_full.json` only when summary confidence is `low` or `needs_detail` is non-empty.
- If you need full output, read only the relevant fields or sections instead of the whole file.

## Live Window Selection

1. Use `list_live_windows` when more than one qrenderdoc window may be active.
2. Match the intended capture by `capture_path`.
3. Pass `window_id` on all live MCP calls for that task.
4. For bundled scripts, set `RENDERDOC_MCP_WINDOW_ID` before running the script.
5. Treat a multiple-window error as a target-selection problem, not as evidence failure.

## Pass Analysis

1. Start with `get_pass_packet`.
2. Use `data.rep_draw` first; it already carries pipeline and shader summary.
3. Cluster the pass before naming it.
4. If the dominant cluster is still unclear, inspect 1-2 more representative events with `get_draw_packet`.
5. Call `inspect_pipeline_state` or `inspect_shader` only for non-representative events that matter.
6. Default to one `inspect_texture_usage` on RT slot 0.
7. Add a second RT only when the pass is multi-RT and RT semantics matter. Stop at 2 RTs.
8. Use overlay or prev/current RT comparison only when screen contribution is disputed.
9. For multi-RT or GBuffer-like passes, inspect only the first key downstream consumer needed for RT semantics.
10. Write the answer with `report-format.md`.

## Resource Flow

1. Start with `inspect_texture_usage`.
2. Add `get_pass_packet` only for the producer or first key consumer.
3. Add `get_draw_packet` only when one event matters more than the pass packet.
4. Write the answer with `report-format.md`.

## Material Or Shader Usage

1. Start with `get_draw_packet`.
2. Use packet shader data first.
3. Call `inspect_shader` only when packet shader data is insufficient.
4. Limit `inspect_texture_usage` to the few bindings that matter.
5. Add `inspect_mesh` only when geometry context changes the answer.
6. Write the answer with `report-format.md`.

## Action Reverse Engineering

1. Start with `get_draw_packet`.
2. Use draw-packet `context` first for marker path, parent pass, root pass, ordering, and neighbors. Add `get_pass_packet` only when broader pass role or sibling evidence beyond packet context matters.
3. If the event is a draw, `inspect_mesh` is the default because vertex attributes plus `vb/ib` bindings are part of the reverse-engineering evidence. If the event is a dispatch, mark geometry as not applicable.
4. For draws, inspect both `vs` and `ps` unless one stage is clearly irrelevant. For dispatches, inspect `cs`.
5. Treat fixed-function state as API-limited when `state.limited_to_source_api` is true.
6. Create or reuse the action working directory before shader code reading. Use the user-provided directory when present; otherwise use the current report/bundle directory or `.state/action_reverse/<capture-or-session>/eid_<eid>/`.
7. Decompile the inspected shader stages with Ruri to HLSL and export them into that working directory. For draws, export `vs` and `ps` unless a stage is proven irrelevant; for dispatches, export `cs`. If decompilation fails, record the failure and continue from RenderDoc disassembly.
8. Build a binding inventory from `inspect_shader.bind`, `inspect_shader.bindings`, `inspect_shader.cbufs`, `inspect_shader.sig`, draw-packet `io`, and mesh `vb/ib` data before writing semantics.
9. Annotate the exported HLSL, or an adjacent notes file, by large functional blocks: declarations, input reconstruction, texture decode, material/lighting/composite or compute evaluation, and output packing/writes.
10. Annotate important input resources with slot, RID/name, format/dimensions when available, actual code role, and semantic status (`consumer-only`, `producer-confirmed`, or `ambiguous`).
11. Add `get_shader_disasm` for the decisive stage and use it to cross-check HLSL and cite code ranges.
12. Use explicit HLSL block names and disassembly line ranges in the report, not just motif names.
13. Use `inspect_texture_usage` for only the few outputs or disputed inputs that materially change the conclusion. Default priority is one main output plus one disputed input and one downstream consumer if needed.
14. Use `io.in_tex_meta`, `io.out_rt_meta`, `io.out_uav_meta`, and `io.out_next_meta` to judge truncation or partial downstream coverage. Do not treat `inspect_shader.bind.srv` and `io.in_tex` as directly comparable counts.
15. Use overlay or before/after RT validation only when visible contribution is disputed; shader code and output writes remain primary evidence.
16. Write the answer with `report-format.md` and consult `shader-patterns.md` for motif recognition.

## Frame Report

1. Start with `get_frame_packet`.
2. Pull `get_pass_packet` only for passes discussed in the report.
3. Add targeted `inspect_*` calls only where they change the conclusion.
4. Keep the report shorter than the packet material it summarizes.
