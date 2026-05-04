# Evidence Guardrails

Use evidence in this priority order:

1. render state
2. resource dependency
3. screen contribution
4. geometry type
5. pass name

Lower-priority evidence does not override higher-priority evidence.

## Forbidden jumps

- `fullscreen draw` -> `postprocess`
- `simple mesh` -> `vfx`
- `skeletal mesh` -> `opaque character`
- `local coverage` -> `decal`
- `character region changed` -> `character base pass`
- `edge glow` -> `outline`
- `local glow` -> `particle vfx`
- `depth write off` -> `vfx`
- `scene color input` -> `translucency`

## Safe replacement

- always list `top1` and `top2`
- give support for each
- add counter-evidence
- explain why `top1` beats `top2`

## Common tie-break reminders

- `skeletal mesh` plus `blend on + depth write off` points toward `translucency` or `vfx`, not `opaque_character`
- a fullscreen draw inside a pass does not make the whole pass `postprocess` when fullscreen is not dominant
- pass names are hints only and never settle the answer by themselves
