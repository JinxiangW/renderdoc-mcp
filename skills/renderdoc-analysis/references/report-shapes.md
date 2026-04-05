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

Consumer-evidence extension:

```json
{
  "rid": "ResourceId::36801",
  "consumer": {
    "eid": 9642,
    "pass": "Compute Pass #2",
    "stage": "cs"
  },
  "shader": {},
  "shader_disasm": {}
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
最终结论: <semantic label>
置信度: <high|medium|low>
统计: draw=<draw> dispatch=<dispatch> clear=<clear>

总结:
<1-2 句中文总结>

关键依据:
- <evidence 1>
- <evidence 2>

Action Cluster:
- <cluster 1>
- <cluster 2>

证据文件:
- <file path 1>
- <file path 2>

不确定性:
- <uncertainty 1>
```

Acceptance:

- top-line conclusion must be semantic, not geometric
- evidence must cite either action clusters, shader behavior, or visual change
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
