# UE RenderDoc Workflow Roadmap

## Goal

Build a practical UE + RenderDoc workflow for render-state inspection, resource tracing, and shader debugging.

The workflow should answer the questions a graphics programmer actually asks:

- which pass/draw produced this result
- which resources were bound, written, or consumed
- which shader permutation ran
- whether source-level shader debug information is available
- what changed between two captures

## MVP

- [ ] trigger and collect captures from UE workflows
- [ ] record capture context: map, camera, RHI, resolution, key CVars
- [ ] keep three primary entry points: pass, draw/dispatch, resource
- [ ] support compact frame/pass/draw inspection packets
- [ ] support resource producer / first consumer / last write checks
- [ ] support export of overlays and textures for quick evidence capture
- [ ] write a short frame or pass evidence bundle from MCP outputs

## V2

- [ ] map UE-facing concepts to RenderDoc markers where possible
- [x] expose shader debug/source information when captures contain symbols
- [ ] prefer source-level shader inspection when available, with disassembly fallback
- [ ] add capture-to-capture diff for pass, draw, and resource changes
- [ ] add stronger resource-flow traversal and jump links between packets

## V3

- [ ] add automatic pass family classification
- [ ] add frame-level pipeline reconstruction
- [ ] add pixel-issue backtracking workflow
- [ ] add regression-oriented validation across multiple captures
- [ ] add report generation for common TA / graphics debugging tasks

## Current Start

The first implementation step in this roadmap is shader debug/source visibility:

- [x] expose whether a shader has debug/source information
- [x] add a dedicated source-reading tool for live captures
- [ ] wire source-first shader reading into downstream analysis workflows
