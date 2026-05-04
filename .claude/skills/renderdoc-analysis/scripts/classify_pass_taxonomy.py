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


def taxonomy_summary(scan: dict, taxonomy: dict) -> dict:
    pass_info = scan.get("pass", {}) or {}
    primary = taxonomy.get("primary", {}) or {}
    candidates = taxonomy.get("candidates", []) or []
    sample_roles: dict[str, int] = {}
    for item in scan.get("samples", []) or []:
        role = str(item.get("sample_role", "unknown"))
        sample_roles[role] = sample_roles.get(role, 0) + 1
    dominant_cluster = "unknown"
    if sample_roles:
        dominant_cluster = sorted(sample_roles.items(), key=lambda item: (-item[1], item[0]))[0][0]

    needs_detail: list[str] = []
    if str(primary.get("confidence", "low")) == "low":
        needs_detail.append("primary confidence is low")
    if len(candidates) > 1:
        needs_detail.append("multiple taxonomy candidates remain")

    return {
        "pass": {
            "name": pass_info.get("pass", "unknown"),
            "eid": pass_info.get("eid", "unknown"),
            "stats": pass_info.get("stats", {}),
        },
        "top_candidates": [
            "{family} / {label}".format(
                family=item.get("family", "unknown"),
                label=item.get("label", "unknown"),
            )
            for item in candidates[:3]
        ],
        "confidence": primary.get("confidence", "low"),
        "dominant_cluster": dominant_cluster,
        "key_evidence": primary.get("evidence", []) or [],
        "needs_detail": needs_detail,
        "evidence_refs": [
            "taxonomy_full.json#primary",
            "taxonomy_full.json#candidates",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a pass scan into taxonomy candidates.")
    parser.add_argument("--scan", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--out")
    parser.add_argument("--report")
    parser.add_argument("--summary-out")
    parser.add_argument("--full-out")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    scan = load_json(args.scan)
    evidence = load_json(args.evidence) if args.evidence else {}
    taxonomy = classify_scan(scan, evidence)
    summary = taxonomy_summary(scan, taxonomy)
    full_output = json.dumps(taxonomy, ensure_ascii=False, indent=2)
    summary_output = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.full_out:
        Path(args.full_out).write_text(full_output + "\n", encoding="utf-8")
    if args.summary_out:
        Path(args.summary_out).write_text(summary_output + "\n", encoding="utf-8")
    if args.out:
        Path(args.out).write_text((summary_output if args.summary_only else full_output) + "\n", encoding="utf-8")
    else:
        print(summary_output if args.summary_only else full_output)
    if args.report:
        Path(args.report).write_text(build_report(scan, taxonomy), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
