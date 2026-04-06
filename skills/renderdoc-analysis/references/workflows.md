# Workflows

## Summary First

- Read `*_summary.json` first.
- Read `*_full.json` only when summary confidence is `low` or `needs_detail` is non-empty.
- If you need full output, read only the relevant fields or sections instead of the whole file.

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

## Frame Report

1. Start with `get_frame_packet`.
2. Pull `get_pass_packet` only for passes discussed in the report.
3. Add targeted `inspect_*` calls only where they change the conclusion.
4. Keep the report shorter than the packet material it summarizes.
