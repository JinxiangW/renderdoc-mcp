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

## Acceptance

- cite the pass name and stats when available
- cite at least one packet or inspect field
- keep evidence factual
- keep interpretation separate
- do not end with only geometric labels such as `fullscreen`, `local`, or `mixed`
- if RT or channel semantics are not backed by downstream use, keep them provisional
