from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def classify_pass(item: dict) -> str:
    stats = item.get("stats", {})
    name = str(item.get("pass", "")).lower()
    if int(stats.get("dispatch", 0) or 0) > 0:
        return "compute"
    if "depth" in name:
        return "depth"
    if "colour" in name or "color" in name:
        return "colour"
    if int(stats.get("draw", 0) or 0) > 0:
        return "graphics"
    return "other"


def build_report(frame_packet: dict, pass_notes: list[str]) -> str:
    data = frame_packet.get("data", {})
    passes = data.get("passes", [])

    lines: list[str] = []
    lines.append("Frame Overview")
    lines.append(f"- API: {data.get('api', 'unknown')}")
    lines.append(f"- Path: {data.get('path', 'unknown')}")
    lines.append(f"- Pass count: {len(passes)}")
    lines.append("")
    lines.append("Key Passes")
    if passes:
        ranked = sorted(
            passes,
            key=lambda item: (
                int(item.get("stats", {}).get("draw", 0) or 0)
                + int(item.get("stats", {}).get("dispatch", 0) or 0) * 10
            ),
            reverse=True,
        )
        for item in ranked[:8]:
            stats = item.get("stats", {})
            kind = classify_pass(item)
            lines.append(
                "- {name} (eid={eid}) kind={kind} draw={draw} dispatch={dispatch} clear={clear}".format(
                    name=item.get("pass", "unknown"),
                    eid=item.get("eid", "unknown"),
                    kind=kind,
                    draw=stats.get("draw", 0),
                    dispatch=stats.get("dispatch", 0),
                    clear=stats.get("clear", 0),
                )
            )
    else:
        lines.append("- No passes available in frame packet")

    lines.append("")
    lines.append("Likely Frame Structure")
    if passes:
        seen = []
        for item in passes:
            kind = classify_pass(item)
            if kind not in seen:
                seen.append(kind)
        for kind in seen:
            lines.append(f"- {kind}")
    else:
        lines.append("- unknown")

    lines.append("")
    lines.append("Resource Flow Notes")
    if pass_notes:
        for note in pass_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- Add resource-flow observations for the passes that matter to the question.")

    lines.append("")
    lines.append("Next Checks")
    lines.append("- Pull get_pass_packet for the most important passes.")
    lines.append("- Add inspect_pipeline_state and inspect_shader only where they materially affect the conclusion.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a markdown frame report from observe packets.")
    parser.add_argument("--frame-packet", required=True)
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--out")
    args = parser.parse_args()

    report = build_report(load_json(args.frame_packet), args.note)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
