from __future__ import annotations

import argparse
from pathlib import Path

from pass_analysis import analyze_pass, load_json


def bullet(lines: list[str], text: str) -> None:
    lines.append(f"- {text}")


def build_report(
    pass_packet: dict,
    pipeline_state: dict | None,
    shader: dict | None,
    shader_disasm: dict | None = None,
    texture_usages: list[dict] | None = None,
    consumer_shader_evidence: list[dict] | None = None,
    visual_validation: dict | None = None,
) -> str:
    analysis = analyze_pass(
        pass_packet,
        pipeline_state,
        shader,
        shader_disasm,
        texture_usages or [],
        consumer_shader_evidence or [],
        visual_validation,
    )
    role = analysis.get("role", {})
    pass_info = analysis.get("pass", {})

    lines: list[str] = []
    lines.append(f"Pass: {pass_info.get('name', 'unknown')} (eid={pass_info.get('eid', 'unknown')})")
    lines.append(f"判断: {role.get('judgment', 'unknown')}")
    lines.append(f"置信度: {role.get('confidence', 'low')}")

    stats = pass_info.get("stats", {})
    if stats:
        lines.append(
            "统计: draw={draw} dispatch={dispatch} clear={clear}".format(
                draw=stats.get("draw", 0),
                dispatch=stats.get("dispatch", 0),
                clear=stats.get("clear", 0),
            )
        )

    lines.append("")
    lines.append("证据:")
    for item in analysis.get("evidence", []):
        bullet(lines, item)

    lines.append("")
    lines.append("输入:")
    for item in analysis.get("inputs", []):
        bullet(
            lines,
            "slot={slot} kind={kind} rid={rid} name={name}".format(
                slot=item.get("slot", ""),
                kind=item.get("kind", "unknown"),
                rid=item.get("rid", "unknown"),
                name=item.get("name", ""),
            ),
        )
    if not analysis.get("inputs"):
        bullet(lines, "当前只拿到了有限的代表性输入绑定。")

    lines.append("")
    lines.append("输出:")
    for item in analysis.get("outputs", []):
        consumer = item.get("first_consumer") or {}
        bullet(
            lines,
            "{kind} slot={slot} rid={rid} fmt={fmt} role_hint={role_hint} consumer={consumer} consumer_shader_evidence={evidence_count}".format(
                kind=item.get("kind", "unknown"),
                slot=item.get("slot", ""),
                rid=item.get("rid", "unknown"),
                fmt=item.get("fmt", ""),
                role_hint=item.get("role_hint", "unknown"),
                consumer=consumer.get("pass", "unknown"),
                evidence_count=item.get("consumer_shader_evidence_count", 0),
            ),
        )

    lines.append("")
    lines.append("Shader 摘要:")
    shader_summary = analysis.get("shader_summary", {})
    bullet(
        lines,
        "stage={stage} name={name} entry={entry} srv={srv} uav={uav} cbv={cbv} smp={smp} disasm_lines={line_count}".format(
            stage=shader_summary.get("stage", ""),
            name=shader_summary.get("name", ""),
            entry=shader_summary.get("entry", ""),
            srv=shader_summary.get("bindings", {}).get("srv", 0),
            uav=shader_summary.get("bindings", {}).get("uav", 0),
            cbv=shader_summary.get("bindings", {}).get("cbv", 0),
            smp=shader_summary.get("bindings", {}).get("smp", 0),
            line_count=shader_summary.get("disasm_line_count", 0),
        ),
    )
    for item in shader_summary.get("behavior", []):
        bullet(lines, item)

    visual = analysis.get("visual_validation", {}) or {}
    if visual:
        lines.append("")
        lines.append("视觉验证:")
        method = visual.get("method")
        if method:
            bullet(lines, f"方法={method}")
        resources = visual.get("resources", {}) or {}
        prev_path = resources.get("previous")
        curr_path = resources.get("current")
        if prev_path or curr_path:
            bullet(lines, f"前图={prev_path or 'unknown'} 当前图={curr_path or 'unknown'}")
        for item in visual.get("observations", []) or []:
            bullet(lines, item)
        contribution = visual.get("screen_contribution")
        if contribution:
            bullet(lines, f"屏幕贡献={contribution}")
        visual_conf = visual.get("confidence")
        if visual_conf:
            bullet(lines, f"置信度={visual_conf}")

    lines.append("")
    lines.append("解释:")
    for item in analysis.get("interpretation", []):
        bullet(lines, item)
    if not analysis.get("interpretation"):
        bullet(lines, "当前证据还不足以支持更强的解释。")

    lines.append("")
    lines.append("后续检查:")
    for item in analysis.get("next_checks", []):
        bullet(lines, item)

    if analysis.get("uncertainties"):
        lines.append("")
        lines.append("不确定性:")
        for item in analysis.get("uncertainties", []):
            bullet(lines, item)

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a markdown pass report from observe packets.")
    parser.add_argument("--pass-packet", required=True)
    parser.add_argument("--pipeline-state")
    parser.add_argument("--shader")
    parser.add_argument("--shader-disasm")
    parser.add_argument("--texture-usage", action="append", default=[])
    parser.add_argument("--consumer-shader-evidence", action="append", default=[])
    parser.add_argument("--visual-validation")
    parser.add_argument("--out")
    args = parser.parse_args()

    report = build_report(
        load_json(args.pass_packet) or {},
        load_json(args.pipeline_state),
        load_json(args.shader),
        load_json(args.shader_disasm),
        [load_json(path) or {} for path in args.texture_usage],
        [load_json(path) or {} for path in args.consumer_shader_evidence],
        load_json(args.visual_validation),
    )

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
