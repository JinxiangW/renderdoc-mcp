# Report Format

Write concise reports that separate facts from interpretation.

## Pass report

```text
Pass: <name> (eid=<eid>)

dominant cluster:
- <cluster>

mixed-in items:
- <secondary item>

Candidates:
- top1: <family / label>
- top2: <family / label or none>

Support for top1:
- <fact>

Support for top2:
- <fact>

Counter-evidence:
- <fact>

Decision:
<why top1 beats top2>

Final Name:
<family / label or broad family>

Uncertainties:
- <gap>
```

## Resource-flow report

```text
Resource: <rid> <name>
Producer: <producer>
First consumer: <consumer>

Flow:
- <edge>

Notes:
- <gap or limit>
```

## Frame report

```text
Frame Overview
- API: <api>
- Path: <path>
- Pass count: <count>

Key Passes
- <pass>: <why it matters>

Resource Flow Notes
- <note>

Next Checks
- <check>
```

## Action reverse report

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
- <topology / index count / instance count / attribute pattern>
- <vertex buffers and index buffer summary, or not applicable>

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
- <first visible consumers of the main outputs>

Conclusion:
- <what this action is doing>
- <why that conclusion fits the evidence>

Limits:
- <missing stage, partial binding map, IO truncation, API limitation, or uncertainty>
```

## Acceptance

- cite the pass name and stats when available
- cite at least one packet or inspect field
- keep evidence factual
- keep interpretation separate
- do not end with only geometric labels such as `fullscreen`, `local`, or `mixed`
- if RT or channel semantics are not backed by downstream use, keep them provisional
- for action reverse reports, include context, resources, and shader behavior
- for dispatch events, mark geometry or fixed-function sections as not applicable instead of forcing graphics wording
- when the draw-packet IO list is partial, say so explicitly instead of implying a complete binding map
- do not translate full disassembly line by line; summarize only the motifs that matter to the conclusion
- action reverse reports must explain the important resources, not just list them
- action reverse reports must use explicit code line ranges for the decisive stage
- do not use `BLENDWEIGHTS/BLENDINDICES` as semantic proof beyond mesh-format context
