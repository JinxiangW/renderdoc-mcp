from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def bridge_script() -> Path:
    return repo_root() / "scripts" / "bridge_req.py"


def image_stats_script() -> Path:
    return Path(__file__).resolve().with_name("Get-RenderDocImageStats.ps1")


def slugify(text: str) -> str:
    safe = []
    for ch in text:
        if ch.isalnum():
            safe.append(ch)
        elif ch in (" ", "-", "_", "#", "(", ")"):
            safe.append("_")
    slug = "".join(safe).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "pass"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def unwrap_envelope(payload: dict) -> dict:
    if "result" in payload and isinstance(payload["result"], dict):
        return payload["result"]
    return payload


def call_bridge(method: str, params: dict, timeout: int = 60) -> dict:
    state_dir = repo_root() / ".state"
    state_dir.mkdir(exist_ok=True)
    params_path = state_dir / f"scan_tmp_{method}.json"
    write_json(params_path, {"params": params})
    cmd = [
        sys.executable,
        str(bridge_script()),
        method,
        "--params-file",
        str(params_path),
        "--timeout",
        str(timeout),
    ]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    last_error = None
    for _ in range(3):
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            last_error = proc.stderr.strip() or proc.stdout.strip() or f"bridge call failed: {method}"
            continue
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            last_error = str(exc)
            continue
        if "error" in payload:
            last_error = payload["error"].get("message", f"bridge error for {method}")
            continue
        result = unwrap_envelope(payload)
        if not result.get("ok", True):
            err = result.get("err") or {}
            last_error = err.get("msg", f"{method} failed")
            continue
        return result
    raise RuntimeError(last_error or f"bridge call failed after retries: {method}")


def call_image_stats(overlay_path: Path, previous_path: Path, current_path: Path) -> dict:
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(image_stats_script()),
        "-OverlayPath",
        str(overlay_path),
        "-PreviousPath",
        str(previous_path),
        "-CurrentPath",
        str(current_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "image stats failed")
    return json.loads(proc.stdout)


def unique_copy(src: str, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def classify_sample(sample: dict) -> str:
    overlay_ratio = float(sample.get("overlay", {}).get("coverage", 0.0) or 0.0)
    diff_ratio = float(sample.get("diff", {}).get("changeRatio", 0.0) or 0.0)
    idx_count = int(sample.get("draw", {}).get("counts", {}).get("idx", 0) or 0)

    if overlay_ratio >= 0.85 and idx_count <= 6:
        if diff_ratio < 0.001:
            return "全屏初始化或拷贝"
        return "全屏合成或全屏着色"
    if overlay_ratio <= 0.005:
        return "极小局部覆盖"
    if overlay_ratio <= 0.05:
        return "局部覆盖"
    if overlay_ratio <= 0.25:
        return "中等范围覆盖"
    return "大范围覆盖"


def semantic_hint(sample: dict) -> str | None:
    draw = sample.get("draw", {}) or {}
    counts = draw.get("counts", {}) or {}
    idx_count = int(counts.get("idx", 0) or 0)
    overlay_ratio = float(sample.get("overlay", {}).get("coverage", 0.0) or 0.0)
    shader = draw.get("shader", {}) or {}
    bind = shader.get("bind", {}) or {}
    io_info = draw.get("io", {}) or {}
    state = draw.get("state", {}) or {}
    inputs = io_info.get("in_tex", []) or []
    input_rt_count = sum(1 for item in inputs if "render target" in str(item.get("name", "")).lower())
    input_tex2d_count = sum(1 for item in inputs if "2d texture" in str(item.get("name", "")).lower())
    depth_write = bool((state.get("depth") or {}).get("write", False))
    disasm_text = str((sample.get("shader_disasm") or {}).get("text") or "")
    lines = disasm_text.lower().splitlines()
    tex_sample_count = sum(1 for line in lines if "sample_b(texture2d)" in line or "sample_l(texture2d)" in line)
    has_uv_rotation = any("sincos" in line for line in lines)
    has_centered_uv = any("-0.500000" in line or "0.500000" in line for line in lines)
    writes_alpha = any("o0.w" in line for line in lines)
    writes_aux_rt = any("dcl_output o1" in line for line in lines)

    if (
        idx_count <= 6
        and overlay_ratio < 0.02
        and not depth_write
        and input_rt_count >= 1
        and input_tex2d_count >= 2
        and tex_sample_count >= 3
        and has_uv_rotation
        and has_centered_uv
        and writes_alpha
        and writes_aux_rt
    ):
        return "translucent_signage_finalize"

    if (
        overlay_ratio < 0.02
        and not depth_write
        and input_tex2d_count >= 2
        and int(bind.get("srv", 0) or 0) >= 3
        and tex_sample_count >= 2
    ):
        return "translucent_signage_local"

    return None


def previous_write_eid(rid: str, current_eid: int) -> int:
    usage = call_bridge("inspect_texture_usage", {"rid": rid, "limit": 5000})
    data = usage.get("data", {}) or {}
    items = data.get("items", []) or []
    candidate = None

    for item in items:
        try:
            eid = int(item.get("eid", 0) or 0)
        except Exception:
            continue
        if eid >= current_eid:
            break
        if str(item.get("type", "")) == "write":
            candidate = eid

    if candidate is not None:
        return candidate

    producer = data.get("producer") or {}
    try:
        producer_eid = int(producer.get("eid", 0) or 0)
        if 0 < producer_eid < current_eid:
            return producer_eid
    except Exception:
        pass

    return max(0, current_eid - 1)


def summarize_pass(pass_packet: dict, samples: list[dict]) -> tuple[str, list[str]]:
    data = pass_packet.get("data", {}) or {}
    pass_info = data.get("pass", {}) or {}
    out_rt = (data.get("io", {}) or {}).get("out_rt", []) or []
    draw_count = int((pass_info.get("stats") or {}).get("draw", 0) or 0)

    full_screen = sum(1 for item in samples if float(item.get("overlay", {}).get("coverage", 0.0) or 0.0) >= 0.85)
    local = sum(1 for item in samples if float(item.get("overlay", {}).get("coverage", 0.0) or 0.0) < 0.25)
    tiny = sum(1 for item in samples if float(item.get("overlay", {}).get("coverage", 0.0) or 0.0) <= 0.01)
    nonzero_diff = sum(1 for item in samples if float(item.get("diff", {}).get("changeRatio", 0.0) or 0.0) > 0.0)
    semantic_hints = [item.get("semantic_hint") for item in samples if item.get("semantic_hint")]
    logo_like = sum(1 for hint in semantic_hints if "translucent_signage" in hint)

    notes: list[str] = []
    if samples:
        notes.append(f"样本中全屏 action 数量={full_screen}")
        notes.append(f"样本中局部 action 数量={local}")
        notes.append(f"样本中极小局部 action 数量={tiny}")
        notes.append(f"样本中非零差分数量={nonzero_diff}")
        notes.append(f"样本中 translucent_signage 候选数量={logo_like}")
    if len(out_rt) >= 2:
        notes.append(f"pass 最终输出包含 {len(out_rt)} 个颜色 RT")
    if draw_count > 0:
        notes.append(f"pass 共包含 {draw_count} 个 draw")

    if samples and full_screen >= 1 and logo_like >= 2:
        return "场景 logo / 标识 半透覆盖 pass", notes
    if samples and full_screen >= 1 and tiny >= max(1, len(samples) // 2) and len(out_rt) >= 2:
        return "混合型 pass：全屏初始化 + 局部覆盖/投影收集", notes
    if samples and full_screen >= max(1, len(samples) - 1):
        return "全屏合成或延迟光照 pass", notes
    if samples and local >= max(1, len(samples) - 1):
        return "局部覆盖/贴花/投影类 pass", notes
    return "混合型 graphics pass", notes


def build_markdown(pass_packet: dict, samples: list[dict], pass_role: str, notes: list[str]) -> str:
    data = pass_packet.get("data", {}) or {}
    pass_info = data.get("pass", {}) or {}
    io_info = data.get("io", {}) or {}

    lines: list[str] = []
    lines.append(f"Pass: {pass_info.get('pass', 'unknown')} (eid={pass_info.get('eid', 'unknown')})")
    lines.append(f"粗分类: {pass_role}")
    lines.append(
        "统计: draw={draw} dispatch={dispatch} clear={clear}".format(
            draw=(pass_info.get("stats") or {}).get("draw", 0),
            dispatch=(pass_info.get("stats") or {}).get("dispatch", 0),
            clear=(pass_info.get("stats") or {}).get("clear", 0),
        )
    )
    lines.append("")
    lines.append("Pass 输出:")
    for item in io_info.get("out_rt", []) or []:
        lines.append(
            "- RT slot={slot} rid={rid} fmt={fmt}".format(
                slot=item.get("slot"),
                rid=item.get("rid"),
                fmt=(item.get("meta") or {}).get("fmt", "unknown"),
            )
        )
    if io_info.get("out_ds"):
        lines.append(
            "- DS rid={rid} fmt={fmt}".format(
                rid=io_info["out_ds"].get("rid"),
                fmt=(io_info["out_ds"].get("meta") or {}).get("fmt", "unknown"),
            )
        )
    lines.append("")
    lines.append("Pass 结论依据:")
    for note in notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("样本:")
    for item in samples:
        lines.append(
            "- eid={eid} 标签={label} prev_write={prev} overlay={overlay:.4f} diff={diff:.4f} 样本分类={kind} 语义提示={semantic}".format(
                eid=item.get("eid"),
                label=item.get("label", ""),
                prev=item.get("previous_write_eid", "unknown"),
                overlay=float(item.get("overlay", {}).get("coverage", 0.0) or 0.0),
                diff=float(item.get("diff", {}).get("changeRatio", 0.0) or 0.0),
                kind=item.get("sample_role", "unknown"),
                semantic=item.get("semantic_hint", "none"),
            )
        )
    return "\n".join(lines) + "\n"


def select_sample_eids(pass_packet: dict, max_samples: int) -> list[tuple[int, str]]:
    data = pass_packet.get("data", {}) or {}
    selected: list[tuple[int, str]] = []
    seen: set[int] = set()

    rep_draw = data.get("rep_draw") or {}
    rep_items = [
        item
        for item in (data.get("rep", []) or [])
        if str(item.get("type", "")).lower() in ("draw", "dispatch")
    ]

    def add(eid: int | None, label: str) -> None:
        if eid is None:
            return
        eid = int(eid)
        if eid in seen:
            return
        seen.add(eid)
        selected.append((eid, label))

    add(rep_draw.get("eid"), "开头代表")
    if rep_items:
        add(rep_items[0].get("eid"), "前段样本")
        positions = [0.20, 0.35, 0.50, 0.65, 0.80]
        for idx, pos in enumerate(positions, start=1):
            sample_index = min(len(rep_items) - 1, max(0, int(round((len(rep_items) - 1) * pos))))
            add(rep_items[sample_index].get("eid"), f"位置样本{idx}")
        add(rep_items[-1].get("eid"), "尾段样本")

    io_info = data.get("io", {}) or {}
    for idx, item in enumerate(io_info.get("out_rt", []), start=1):
        producer = item.get("producer") or {}
        add(producer.get("eid"), f"最终写出RT{idx}")
    if io_info.get("out_ds"):
        producer = (io_info.get("out_ds") or {}).get("producer") or {}
        add(producer.get("eid"), "最终写出DS")

    return selected[:max_samples]


def scan_pass(marker: str, rep_limit: int, max_samples: int, out_dir: Path) -> dict:
    pass_packet = call_bridge("get_pass_packet", {"marker": marker, "limit": rep_limit})
    data = pass_packet.get("data", {}) or {}
    pass_name = str((data.get("pass") or {}).get("pass", marker))
    slug = slugify(pass_name)
    pass_dir = out_dir / slug
    pass_dir.mkdir(parents=True, exist_ok=True)

    samples: list[dict] = []
    for eid, label in select_sample_eids(pass_packet, max_samples):
        draw = call_bridge("get_draw_packet", {"eid": eid})
        draw_data = draw.get("data", {}) or {}
        out_rt = (draw_data.get("io", {}) or {}).get("out_rt", []) or []
        if not out_rt:
            continue

        rid = str(out_rt[0].get("rid"))
        prev_eid = previous_write_eid(rid, int(eid))
        overlay_resp = call_bridge("debug_save_overlay", {"eid": eid, "overlay": "drawcall", "rid": rid, "dest": "PNG"})
        prev_resp = call_bridge("debug_save_texture", {"eid": prev_eid, "rid": rid, "dest": "PNG"})
        curr_resp = call_bridge("debug_save_texture", {"eid": eid, "rid": rid, "dest": "PNG"})
        shader_disasm = call_bridge("get_shader_disasm", {"eid": eid, "stage": "ps", "offset": 0, "max_lines": 220})

        overlay_path = unique_copy(overlay_resp["data"]["path"], pass_dir / f"overlay_{eid}.png")
        prev_path = unique_copy(prev_resp["data"]["path"], pass_dir / f"prev_{eid}.png")
        curr_path = unique_copy(curr_resp["data"]["path"], pass_dir / f"curr_{eid}.png")

        stats = call_image_stats(overlay_path, prev_path, curr_path)
        sample = {
            "eid": eid,
            "label": label,
            "previous_write_eid": prev_eid,
            "draw": draw_data,
            "shader_disasm": shader_disasm.get("data", {}),
            "overlay": stats.get("overlay", {}),
            "diff": stats.get("diff", {}),
            "files": {
                "overlay": str(overlay_path),
                "previous": str(prev_path),
                "current": str(curr_path),
            },
        }
        sample["sample_role"] = classify_sample(sample)
        sample["semantic_hint"] = semantic_hint(sample)
        samples.append(sample)

    pass_role, notes = summarize_pass(pass_packet, samples)
    result = {
        "pass": data.get("pass", {}),
        "pass_role": pass_role,
        "notes": notes,
        "samples": samples,
    }
    write_json(pass_dir / "scan.json", result)
    (pass_dir / "scan.md").write_text(build_markdown(pass_packet, samples, pass_role, notes), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan one pass with overlay and before/after RT comparisons.")
    parser.add_argument("--marker", required=True)
    parser.add_argument("--rep-limit", type=int, default=24)
    parser.add_argument("--max-samples", type=int, default=4)
    parser.add_argument("--out-dir", default=str(repo_root() / ".state" / "pass_scans"))
    parser.add_argument("--out")
    args = parser.parse_args()

    result = scan_pass(args.marker, args.rep_limit, args.max_samples, Path(args.out_dir))
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
