# Heuristics

Use these as lightweight guides, not hard truth.

## Pass Type Hints

### Likely compute processing

Typical signals:

- pass stats show non-zero dispatch count
- representative event type is `Dispatch`
- pipeline state includes only `cs`
- outputs are UAV-heavy or intermediate textures

Confidence should drop if:

- there is mixed draw and dispatch activity
- pass naming is generic

### Likely depth-only or depth-prepass

Typical signals:

- pass name includes `depth` or `depth-only`
- many draws and zero dispatches
- pipeline state shows depth target bound
- color target count is zero or minimal

Confidence should drop if:

- pass has meaningful color outputs
- the pass name is misleading or auto-generated

### Likely colour, gbuffer, or main graphics pass

Typical signals:

- draw count dominates
- multiple render targets are bound
- representative pixel shader is present
- outputs have downstream consumers in later lighting or composite passes

Confidence should drop if:

- there are very few draws
- the outputs do not appear to feed later stages

For GBuffer-like passes:

- do not assign each RT's semantic role from the producer pass alone
- prefer downstream consumer usage plus current and downstream shader reads
- treat per-channel meaning as a hypothesis until later passes support it

## Resource Flow Hints

- Treat the last visible write before a read chain as the strongest producer candidate.
- Treat the first visible read as the strongest handoff point.
- Prefer concrete usage types like `ColorTarget`, `PS_Resource`, or `RWResource` over pass names alone.

## Suggested Next Checks

- If a pass looks compute-heavy, inspect `inspect_texture_usage` for its outputs before making claims about purpose.
- If a pass looks graphics-heavy with multiple render targets, inspect downstream reads of those outputs before calling it gbuffer or lighting.
- If a resource chain is noisy, focus on producer, first read, and the first non-compute read.

## Reporting Rules

- Always label heuristic conclusions as inferred when they depend on naming or common engine patterns.
- Prefer `high`, `medium`, and `low` confidence.
- When evidence conflicts, report the conflict instead of picking a clean narrative.
