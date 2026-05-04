# Conclusion Rules

Use these rules before naming a pass.

## Required order

1. Cluster the pass structurally.
2. Rank clusters by dominance with:
   - count
   - screen contribution
   - resource-flow importance
3. Let only the dominant cluster decide the pass family.
4. Treat other clusters as mixed-in items.
5. Only then pick `top1`, `top2`, and a final name.

## Label gates

- `opaque`: mostly blend off, mostly depth write on, looks like first solid surface draw.
- `translucency`: mostly blend on, mostly depth write off, reads scene/intermediate data or behaves like an overlay layer.
- `vfx`: blend on, effect-like visuals, effect-like inputs such as noise, mask, ramp, volume, or flipbook.
- `decal_or_projection`: local coverage, no depth write, projected/decal/sign/panel evidence.
- `lighting_or_composite`: fullscreen or large screen-space, reads GBuffer/depth/intermediate, not dominated by mesh draws.
- `postprocess`: fullscreen dominant cluster, screen-space intermediate input, not dominated by mesh draws.
- `ui`: small screen-space draw, simple geometry, icon/text/panel style evidence.

If the gate is not met, stop at the broader family.

## Stop rules

- If broad family is stable but label is not, stop at the broad family.
- If `top1` and `top2` stay close, keep the broader family and state uncertainty.
- If dominant cluster family is still unclear, keep drilling into the dominant cluster instead of naming the whole pass.
- Do not narrow when you only have structure, only image change, or only one representative draw.

## Required report decision shape

Use:

- `dominant cluster`
- `mixed-in items`
- `top1`
- `top2`
- `support for top1`
- `support for top2`
- `counter-evidence`
- `decision`
- `final name`
- `uncertainties`
