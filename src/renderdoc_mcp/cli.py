"""Manual CLI for offline bootstrap validation."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
import sys

from renderdoc_mcp.offline import OfflineBootstrapAdapter


def _print(obj: object) -> None:
    def encode(value: object) -> object:
        if is_dataclass(value):
            return asdict(value)
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    print(json.dumps(obj, ensure_ascii=False, indent=2, default=encode))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="RenderDoc MCP offline bootstrap CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    list_parser = sub.add_parser("list-captures")
    list_parser.add_argument("root")
    list_parser.add_argument("--limit", type=int, default=50)

    open_parser = sub.add_parser("open-capture")
    open_parser.add_argument("path")

    context_parser = sub.add_parser("get-capture-context")
    context_parser.add_argument("--path")
    context_parser.add_argument("--sidecar")

    hints_parser = sub.add_parser("get-capture-hints")
    hints_parser.add_argument("--path")
    hints_parser.add_argument("--sidecar")

    compare_context_parser = sub.add_parser("compare-capture-contexts")
    compare_context_parser.add_argument("path_a")
    compare_context_parser.add_argument("path_b")
    compare_context_parser.add_argument("--sidecar-a")
    compare_context_parser.add_argument("--sidecar-b")

    compare_pass_parser = sub.add_parser("compare-pass-lists")
    compare_pass_parser.add_argument("file_a")
    compare_pass_parser.add_argument("file_b")

    compare_packet_parser = sub.add_parser("compare-packet-artifacts")
    compare_packet_parser.add_argument("file_a")
    compare_packet_parser.add_argument("file_b")

    compare_draw_parser = sub.add_parser("compare-draw-packets")
    compare_draw_parser.add_argument("file_a")
    compare_draw_parser.add_argument("file_b")

    compare_texuse_parser = sub.add_parser("compare-texture-usage-artifacts")
    compare_texuse_parser.add_argument("file_a")
    compare_texuse_parser.add_argument("file_b")

    sub.add_parser("get-capture-status")

    args = parser.parse_args()
    adapter = OfflineBootstrapAdapter()

    if args.cmd == "list-captures":
        res = adapter.list_captures(args.root, args.limit)
    elif args.cmd == "open-capture":
        res = adapter.open_capture(args.path)
    elif args.cmd == "get-capture-context":
        res = adapter.get_capture_context(args.path, args.sidecar)
    elif args.cmd == "get-capture-hints":
        res = adapter.get_capture_hints(args.path, args.sidecar)
    elif args.cmd == "compare-capture-contexts":
        res = adapter.compare_capture_contexts(args.path_a, args.path_b, args.sidecar_a, args.sidecar_b)
    elif args.cmd == "compare-pass-lists":
        res = adapter.compare_pass_lists(args.file_a, args.file_b)
    elif args.cmd == "compare-packet-artifacts":
        res = adapter.compare_packet_artifacts(args.file_a, args.file_b)
    elif args.cmd == "compare-draw-packets":
        res = adapter.compare_draw_packets(args.file_a, args.file_b)
    elif args.cmd == "compare-texture-usage-artifacts":
        res = adapter.compare_texture_usage_artifacts(args.file_a, args.file_b)
    else:
        res = adapter.get_capture_status()

    _print(res)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
