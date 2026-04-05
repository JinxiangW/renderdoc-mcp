from __future__ import annotations

import argparse
import json
from pathlib import Path

from pass_taxonomy import classify_scan


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def bullet(lines: list[str], text: str) -> None:
    lines.append(f"- {text}")


def build_report(scan: dict, taxonomy: dict, evidence: dict | None = None) -> str:
    pass_info = scan.get("pass", {}) or {}
    stats = pass_info.get("stats", {}) or {}
    samples = scan.get("samples", []) or []
    notes = scan.get("notes", []) or []
    primary = taxonomy.get("primary", {}) or {}
    evidence = evidence or {}

    semantic_label = evidence.get("semantic_label") or primary.get("label", "unknown")
    confidence = evidence.get("confidence") or primary.get("confidence", "medium")
    summary = evidence.get("summary") or ""

    lines: list[str] = []
    lines.append(f"Pass: {pass_info.get('pass', 'unknown')} (eid={pass_info.get('eid', 'unknown')})")
    lines.append(f"最终结论: {semantic_label}")
    lines.append(f"Taxonomy: {primary.get('family', 'unknown')} / {primary.get('label', 'unknown')}")
    lines.append(f"置信度: {confidence}")
    lines.append(
        "统计: draw={draw} dispatch={dispatch} clear={clear}".format(
            draw=stats.get("draw", 0),
            dispatch=stats.get("dispatch", 0),
            clear=stats.get("clear", 0),
        )
    )

    if summary:
        lines.append("")
        lines.append("总结:")
        lines.append(summary)

    lines.append("")
    lines.append("Taxonomy 依据:")
    for item in primary.get("evidence", []) or []:
        bullet(lines, item)
    for item in notes:
        bullet(lines, item)

    if evidence.get("mesh_signals") or evidence.get("visual_signals"):
        lines.append("")
        lines.append("补充证据:")
        mesh = evidence.get("mesh_signals", {}) or {}
        visual = evidence.get("visual_signals", {}) or {}
        if mesh.get("skeletal_actions"):
            bullet(lines, f"skeletal_actions={', '.join(str(x) for x in mesh.get('skeletal_actions', []))}")
        if visual.get("subject_reveal_sequence"):
            bullet(lines, "视觉序列显示主体从 silhouette 被逐步补成可见对象")
        if visual.get("translucent_signage"):
            bullet(lines, "视觉与 shader 证据都指向 logo / signage / panel 一类半透覆盖")

    clusters = evidence.get("action_clusters", []) or []
    if clusters:
        lines.append("")
        lines.append("Action Cluster:")
        for item in clusters:
            bullet(
                lines,
                "{label}: role={role} actions={actions}".format(
                    label=item.get("label", "未命名 cluster"),
                    role=item.get("role", "unknown"),
                    actions=", ".join(str(x) for x in item.get("actions", [])) or "unknown",
                ),
            )
            if item.get("detail"):
                bullet(lines, f"{item.get('label', 'cluster')} 说明: {item.get('detail')}")

    if samples:
        lines.append("")
        lines.append("代表样本:")
        for item in samples[:8]:
            bullet(
                lines,
                "eid={eid} 标签={label} 样本分类={sample_role} 语义提示={semantic}".format(
                    eid=item.get("eid", "unknown"),
                    label=item.get("label", ""),
                    sample_role=item.get("sample_role", "unknown"),
                    semantic=item.get("semantic_hint", "none"),
                ),
            )

    evidence_files = evidence.get("evidence_files", []) or []
    if evidence_files:
        lines.append("")
        lines.append("证据文件:")
        for item in evidence_files:
            bullet(lines, item)

    uncertainties = evidence.get("uncertainties", []) or []
    if uncertainties:
        lines.append("")
        lines.append("不确定性:")
        for item in uncertainties:
            bullet(lines, item)

    next_steps = evidence.get("next_steps", []) or []
    if next_steps:
        lines.append("")
        lines.append("后续检查:")
        for item in next_steps:
            bullet(lines, item)

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an automatic final pass report from scan + taxonomy + optional evidence.")
    parser.add_argument("--scan", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--taxonomy-out")
    parser.add_argument("--out")
    args = parser.parse_args()

    scan = load_json(args.scan)
    evidence = load_json(args.evidence) if args.evidence else {}
    taxonomy = classify_scan(scan, evidence)
    if args.taxonomy_out:
        Path(args.taxonomy_out).write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = build_report(scan, taxonomy, evidence)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
