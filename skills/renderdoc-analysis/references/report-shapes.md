# Report Shapes

## Pass Analysis Shape

Structured JSON form:

```json
{
  "pass": {
    "eid": 21115,
    "name": "Colour Pass #2",
    "stats": {"draw": 645, "dispatch": 0, "clear": 1}
  },
  "role": {
    "judgment": "graphics_colour_or_gbuffer_pass",
    "confidence": "high",
    "alternatives": []
  },
  "inputs": [],
  "outputs": [],
  "shader_summary": {},
  "visual_validation": {},
  "evidence": ["..."],
  "interpretation": ["..."],
  "next_checks": ["..."],
  "uncertainties": ["..."],
  "context": {}
}
```

Visual-validation extension:

```json
{
  "method": "prev_curr_rt_compare",
  "resources": {
    "previous": "C:/.../prev.png",
    "current": "C:/.../curr.png"
  },
  "observations": [
    "Only the center character body changed.",
    "Environment lighting remained stable."
  ],
  "screen_contribution": "This action draws the character coat/body material.",
  "confidence": "high"
}
```

Use this structure:

```text
Pass: <name> (eid=<eid>)
Judgment: <judgment>
Confidence: <high|medium|low>

Evidence:
- <fact 1>
- <fact 2>

Inputs:
- <input 1>

Outputs:
- <output 1>

Shader Summary:
- <shader fact 1>

Visual Validation:
- <visual fact 1>

Interpretation:
- <interpretation 1>

Next checks:
- <next action 1>

Uncertainties:
- <open issue 1>
```

Acceptance:

- include at least two evidence bullets when possible
- keep evidence factual
- keep interpretation separate from evidence
- if visual validation is present, keep it tied to concrete before/after image differences
- include uncertainties when GBuffer role inference is still provisional or when inputs/outputs are incomplete
- reject reports whose top-line conclusion is only a geometric routing label without semantic content

## Semantic Pass Report Shape

Use this structure:

```text
Pass: <name> (eid=<eid>)
top1: <family / label>
top2: <family / label or none>
Confidence: <high|medium|low>
Stats: draw=<draw> dispatch=<dispatch> clear=<clear>

Support for top1:
- <evidence 1>
- <evidence 2>

Support for top2:
- <evidence 1>

Counter-evidence:
- <counter evidence 1>
- <counter evidence 2>

Action Clusters:
- <cluster 1>
- <cluster 2>

Decision:
<why top1 beats top2>

Final Name:
<one-line semantic label>

Uncertainties:
- <uncertainty 1>
```

Acceptance:

- top-line candidates must be semantic, not geometric
- evidence must cite either action clusters, shader behavior, fixed-function state, or visual change
- include at least one counter-evidence bullet when the pass is ambiguous
- use scan output as input evidence, not as the final conclusion itself

## Resource Flow Shape

Use this structure:

```text
Resource: <rid> <name>
Producer: <producer or unknown>
First consumer: <consumer or unknown>

Flow:
- <edge 1>
- <edge 2>

Notes:
- <uncertainty or limitation>
```

Acceptance:

- distinguish producer from consumer
- note if the chain is partial

## Frame Report Shape

Use this structure:

```text
Frame Overview
- API: <api>
- Path: <path>
- Pass count: <count>

Key Passes
- <pass 1>: <why it matters>
- <pass 2>: <why it matters>

Resource Flow Notes
- <resource note 1>

Next Checks
- <next check 1>
```

Acceptance:

- keep the overview compact
- discuss only the passes relevant to the user question
- avoid raw packet dumps

## Material Usage Shape

Use this structure:

```text
Event: <eid> <name>
Stage focus: <stage>

Key bindings:
- <binding 1>
- <binding 2>

Likely material role:
- <inference 1>

Limits:
- <missing data or ambiguity>
```

Acceptance:

- cite stage and binding evidence
- separate binding facts from semantic guesses

## Action Reverse Shape

Use this structure:

```text
Action: <eid> <name> (<Draw|Dispatch>)
Marker Path: <marker path or unknown>
Parent Pass: <nearest marker pass name or unknown>
Root Pass: <outermost pass name or unknown>
Position: <index within pass or unknown>

Neighbors:
- prev: <eid or none>
- next: <eid or none>

Geometry:
- <topology / counts / attribute pattern>
- <vertex/index buffer bindings, or not applicable>

Fixed-function State:
- <blend / depth / rasterizer facts, or not applicable / API-limited>

Resource Inventory:
- VS: <t#/cb#/vb inputs and roles>
- PS: <t#/cb#/s# inputs and roles>
- CS: <t#/u#/cb# inputs and roles, or not applicable>

Constant Buffers:
- <cb slot name size variables and likely usage>

Shader Segments:
- <lines A-B: what this range does>
- <lines C-D: what this range does>

Outputs:
- <o#/rt/uav target and likely channel meaning>

Shader Behavior:
- <stage and entry>
- <how resources are actually used in code>

Screen Contribution:
- <overlay or before/after observation, if collected>

Downstream:
- <first visible consumers>

Conclusion:
- <what this action is doing>
- <why that conclusion fits>

Limits:
- <missing data, IO truncation, or ambiguity>
```

Acceptance:

- include pass context, resource IO, and shader behavior
- for dispatch events, mark geometry or fixed-function sections as not applicable instead of forcing graphics language
- keep binding coverage provisional when packet IO is partial
- summarize motifs rather than translating the whole disassembly
- use explicit disassembly line ranges for the decisive stage
- explain the important resources, not just that they are bound

## Reverse Pipeline Shape

Use this structure:

```text
Likely Frame Structure
- <stage 1>
- <stage 2>

Key evidence:
- <pass or packet fact 1>
- <pass or packet fact 2>

Uncertain areas:
- <open question 1>
```

Acceptance:

- keep ordering explicit
- mark hypotheses as inferred
