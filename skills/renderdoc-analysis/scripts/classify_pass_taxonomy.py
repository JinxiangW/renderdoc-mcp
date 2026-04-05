from __future__ import annotations

import argparse
import json
from pathlib import Path

from pass_taxonomy import classify_scan


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def build_report(scan: dict, taxonomy: dict) -> str:
    pass_info = scan.get("pass", {}) or {}
    primary = taxonomy.get("primary", {}) or {}
    candidates = taxonomy.get("candidates", []) or []

    lines: list[str] = []
    lines.append(f"Pass: {pass_info.get('pass', 'unknown')} (eid={pass_info.get('eid', 'unknown')})")
    lines.append(f"Taxonomy: {primary.get('family', 'unknown')} / {primary.get('label', 'unknown')}")
    lines.append(f"置信度: {primary.get('confidence', 'low')}")
    lines.append("")
    lines.append("Primary Evidence:")
    for item in primary.get("evidence", []) or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Candidates:")
    for item in candidates:
        lines.append(
            "- {family} / {label} ({confidence})".format(
                family=item.get("family", "unknown"),
                label=item.get("label", "unknown"),
                confidence=item.get("confidence", "low"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a pass scan into taxonomy candidates.")
    parser.add_argument("--scan", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--out")
    parser.add_argument("--report")
    args = parser.parse_args()

    scan = load_json(args.scan)
    evidence = load_json(args.evidence) if args.evidence else {}
    taxonomy = classify_scan(scan, evidence)
    output = json.dumps(taxonomy, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    if args.report:
        Path(args.report).write_text(build_report(scan, taxonomy), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
