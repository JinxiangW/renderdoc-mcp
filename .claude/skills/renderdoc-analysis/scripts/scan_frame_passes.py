from __future__ import annotations

import argparse
import json
from pathlib import Path

from scan_pass_visuals import call_bridge, repo_root, scan_pass


def build_summary(items: list[dict]) -> str:
    lines: list[str] = []
    lines.append("Pass 粗分类表")
    for item in items:
        pass_info = item.get("pass", {}) or {}
        lines.append(
            "- {name} (eid={eid}) => {role}".format(
                name=pass_info.get("pass", "unknown"),
                eid=pass_info.get("eid", "unknown"),
                role=item.get("pass_role", "unknown"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-scan frame passes with visual sampling.")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--marker-contains")
    parser.add_argument("--out-dir", default=str(repo_root() / ".state" / "frame_pass_scans"))
    parser.add_argument("--out")
    args = parser.parse_args()

    listing = call_bridge("list_passes", {"limit": max(20, args.limit * 4)})
    items = listing.get("data", {}).get("items", []) or []
    if args.marker_contains:
        needle = args.marker_contains.lower()
        items = [item for item in items if needle in str(item.get("pass", "")).lower()]
    items = items[: args.limit]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for item in items:
        marker = str(item.get("pass", ""))
        if not marker:
            continue
        results.append(scan_pass(marker, rep_limit=20, max_samples=4, out_dir=out_dir))

    payload = {"count": len(results), "items": results}
    (out_dir / "summary.md").write_text(build_summary(results), encoding="utf-8")
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
