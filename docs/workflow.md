# Workflow

## Principle

This repository keeps MCP focused on observation only.

- `observe/*`: gather evidence packets
- analysis and report generation move to a separate skill

## Why

The MCP layer should stay stable, compact, and easy to compose:

- expose RenderDoc facts
- avoid embedded analysis heuristics
- avoid report-generation workflows in the transport layer

## Observe Layer

Observe tools gather packet-shaped data without producing judgments.

Current target packet types:

- `frame_packet`
- `pass_packet`
- `draw_packet`

## Out Of Scope For MCP

The following belong in the analysis skill instead of this repository's MCP surface:

- pass classification
- frame-level summaries
- evidence-to-judgment pipelines
- report and bundle generation
