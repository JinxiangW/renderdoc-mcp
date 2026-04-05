# Offline Bootstrap Milestone

## Goal

Deliver a minimal offline analysis bootstrap that works without a custom RenderDoc extension.

## Target Capabilities

- discover a local RenderDoc installation
- enumerate `.rdc` files recursively
- open a capture in compact summary mode
- persist active capture status locally for follow-up calls
- validate on a real capture under `C:\Caps`

## Checklist

- [x] define the offline bootstrap milestone
- [x] implement local RenderDoc installation discovery
- [x] implement recursive capture inventory
- [x] implement compact `open_capture`
- [x] implement persisted `get_capture_status`
- [x] add a CLI for manual validation
- [x] validate against at least one real `.rdc` from `C:\Caps`

## Constraints

- compact outputs only
- no full capture parsing in this milestone
- use installed RenderDoc tooling where possible

## Validation Notes

- discovered local installation at `C:\Program Files\RenderDoc`
- validated recursive listing on `C:\Caps`
- validated thumbnail-backed open on `C:\Caps\世界\Endfield-frame106520.rdc`
- validated persisted follow-up status read after open
