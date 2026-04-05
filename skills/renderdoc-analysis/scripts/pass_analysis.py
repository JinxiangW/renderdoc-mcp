from __future__ import annotations

import json
from pathlib import Path


def load_json(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _stats(pass_info: dict) -> tuple[int, int, int]:
    stats = pass_info.get("stats", {})
    return (
        int(stats.get("draw", 0) or 0),
        int(stats.get("dispatch", 0) or 0),
        int(stats.get("clear", 0) or 0),
    )


def _pipeline_res(pipeline_state: dict | None) -> dict:
    if not pipeline_state:
        return {}
    if pipeline_state.get("ok"):
        return pipeline_state.get("data", {}).get("res", {}) or {}
    if "res" in pipeline_state:
        return pipeline_state.get("res", {}) or {}
    return {}


def _shader_data(shader: dict | None) -> dict:
    if not shader:
        return {}
    if shader.get("ok"):
        return shader.get("data", {}) or {}
    if "shader" in shader or "stage" in shader:
        return shader or {}
    return {}


def _packet_data(packet: dict | None) -> dict:
    if not packet:
        return {}
    if packet.get("ok"):
        return packet.get("data", {}) or {}
    result = packet.get("result")
    if isinstance(result, dict):
        if result.get("ok"):
            return result.get("data", {}) or {}
        if "data" in result:
            return result.get("data", {}) or {}
    if "pass" in packet or "io" in packet or "rep_draw" in packet:
        return packet
    return {}


def _shader_disasm_data(shader_disasm: dict | None) -> dict:
    if not shader_disasm:
        return {}
    if shader_disasm.get("ok"):
        return shader_disasm.get("data", {}) or {}
    if "text" in shader_disasm or "line_count" in shader_disasm:
        return shader_disasm or {}
    return {}


def _pass_name_list(texture_usages: list[dict] | None) -> list[str]:
    hints: list[str] = []
    for item in texture_usages or []:
        data = item.get("data", {}) or {}
        first_read = data.get("first_read") or {}
        if first_read.get("pass"):
            hints.append(str(first_read["pass"]))
    return hints


def _consumer_shader_map(consumer_shader_evidence: list[dict] | None) -> dict[str, list[dict]]:
    mapping: dict[str, list[dict]] = {}
    for item in consumer_shader_evidence or []:
        rid = str(item.get("rid") or item.get("output_rid") or "")
        if not rid:
            continue
        mapping.setdefault(rid, []).append(item)
    return mapping


def _fmt_and_dims(meta: dict | None) -> tuple[str | None, list[int] | None]:
    if not meta:
        return None, None
    dims = meta.get("dims")
    return meta.get("fmt"), dims if isinstance(dims, list) else None


def _summarize_inputs(rep_draw: dict) -> list[dict]:
    items = []
    for entry in (rep_draw.get("io", {}) or {}).get("in_tex", []) or []:
        name = str(entry.get("name", ""))
        kind = "buffer" if "buffer" in name.lower() else "texture"
        items.append(
            {
                "rid": entry.get("rid"),
                "name": name,
                "slot": entry.get("slot"),
                "kind": kind,
            }
        )
    return items


def _consumer_from_output(entry: dict) -> dict | None:
    first_read = entry.get("first_read")
    if first_read:
        return {
            "eid": first_read.get("eid"),
            "usage": first_read.get("usage"),
            "pass": first_read.get("pass"),
        }
    next_items = entry.get("next") or []
    if next_items:
        first = next_items[0]
        return {
            "eid": first.get("eid"),
            "usage": first.get("usage"),
            "pass": first.get("pass"),
        }
    return None


def _infer_output_role(entry: dict, total_rt: int, consumer_shader_items: list[dict] | None = None) -> tuple[str, str, list[str]]:
    consumer = _consumer_from_output(entry)
    kind = str(entry.get("kind", ""))
    if kind == "ds":
        return "depth_output", "high", ["depth output is explicit in the pass packet"]

    if not consumer:
        return "unknown_output_role", "low", ["no downstream consumer is visible yet"]

    consumer_pass = str(consumer.get("pass", "") or "")
    consumer_usage = str(consumer.get("usage", "") or "")
    pass_l = consumer_pass.lower()
    evidence = [f"first visible consumer is `{consumer_pass}` with usage `{consumer_usage}`"]

    consumer_stage = None
    consumer_behaviors: list[str] = []
    if consumer_shader_items:
        first_item = consumer_shader_items[0]
        shader_summary = _shader_summary(first_item.get("shader"), first_item.get("shader_disasm"), {})
        consumer_stage = shader_summary.get("stage")
        consumer_behaviors = shader_summary.get("behavior", []) or []
        if consumer_stage:
            evidence.append(f"consumer shader stage is `{consumer_stage}`")
        if consumer_behaviors:
            evidence.append("consumer shader behavior suggests: {}".format(", ".join(consumer_behaviors[:2])))

    if consumer_stage == "cs" or consumer_usage.startswith("CS_") or "compute" in pass_l:
        return "compute_intermediate_input", "high" if consumer_stage == "cs" else "medium", evidence
    if "light" in pass_l or "composite" in pass_l:
        return "lighting_or_composite_input", "high" if consumer_stage == "ps" else "medium", evidence
    if "post" in pass_l or "tone" in pass_l or "taa" in pass_l or "bloom" in pass_l:
        return "postprocess_input", "high" if consumer_stage == "ps" else "medium", evidence
    if total_rt >= 2 and consumer_usage.startswith("PS_"):
        evidence.append("multiple color outputs suggest a gbuffer-style or intermediate graphics pass")
        return "gbuffer_or_graphics_intermediate", "high" if consumer_stage == "ps" else "medium", evidence
    return "graphics_intermediate", "low", evidence


def _summarize_outputs(pass_packet: dict, consumer_shader_evidence: list[dict] | None = None) -> tuple[list[dict], list[str]]:
    io_info = pass_packet.get("data", {}).get("io", {}) or {}
    out_rt = io_info.get("out_rt", []) or []
    items: list[dict] = []
    uncertainties: list[str] = []
    consumer_map = _consumer_shader_map(consumer_shader_evidence)

    for entry in out_rt:
        meta = entry.get("meta") or {}
        fmt, dims = _fmt_and_dims(meta)
        role_hint, role_confidence, role_evidence = _infer_output_role(
            {"kind": "rt", **entry},
            len(out_rt),
            consumer_map.get(str(entry.get("rid") or "")),
        )
        items.append(
            {
                "rid": entry.get("rid"),
                "name": entry.get("name"),
                "slot": entry.get("slot"),
                "kind": "rt",
                "fmt": fmt,
                "dims": dims,
                "first_consumer": _consumer_from_output(entry),
                "role_hint": role_hint,
                "role_confidence": role_confidence,
                "role_evidence": role_evidence,
                "consumer_shader_evidence_count": len(consumer_map.get(str(entry.get("rid") or ""), [])),
            }
        )
        if len(out_rt) >= 2:
            uncertainties.append(
                "Per-RT and per-channel semantics remain provisional until downstream consumer passes and shaders are inspected."
            )

    out_ds = io_info.get("out_ds")
    if out_ds:
        meta = out_ds.get("meta") or {}
        fmt, dims = _fmt_and_dims(meta)
        role_hint, role_confidence, role_evidence = _infer_output_role(
            {"kind": "ds", **out_ds},
            len(out_rt),
            consumer_map.get(str(out_ds.get("rid") or "")),
        )
        items.append(
            {
                "rid": out_ds.get("rid"),
                "name": out_ds.get("name"),
                "slot": None,
                "kind": "ds",
                "fmt": fmt,
                "dims": dims,
                "first_consumer": _consumer_from_output(out_ds),
                "role_hint": role_hint,
                "role_confidence": role_confidence,
                "role_evidence": role_evidence,
                "consumer_shader_evidence_count": len(consumer_map.get(str(out_ds.get("rid") or ""), [])),
            }
        )

    # Deduplicate repeated uncertainty text while preserving order.
    deduped = []
    seen = set()
    for item in uncertainties:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    return items, deduped


def _shader_summary(shader: dict | None, shader_disasm: dict | None, rep_draw: dict) -> dict:
    shader_data = _shader_data(shader if shader is not None else rep_draw.get("shader"))
    disasm_data = _shader_disasm_data(shader_disasm)
    shader_info = shader_data.get("shader", {}) or {}
    bind = shader_data.get("bind", {}) or {}
    code = shader_data.get("code", {}) or {}

    behavior: list[str] = []
    stage = str(shader_data.get("stage", "") or "")
    if stage == "ps" and int(bind.get("srv", 0) or 0) > 0:
        behavior.append("pixel shader samples texture resources")
    if stage == "cs" and int(bind.get("uav", 0) or 0) > 0:
        behavior.append("compute shader writes UAV outputs")
    if int(bind.get("cbv", 0) or 0) > 0:
        behavior.append("shader depends on one or more constant buffers")
    disasm_text = disasm_data.get("text") or code.get("text")
    if disasm_text:
        preview = str(disasm_text).splitlines()
        if any("dcl_output o1" in line or "dcl_output o2" in line or "dcl_output o3" in line or "dcl_output o4" in line for line in preview):
            behavior.append("shader declares multiple color outputs")
        if any("sample" in line.lower() or "texture" in line.lower() for line in preview):
            behavior.append("shader code preview suggests texture sampling")
        if any("dcl_resource_texture2d" in line.lower() for line in preview):
            behavior.append("disassembly declares one or more 2D texture resources")
        if any("dcl_constantbuffer" in line.lower() for line in preview):
            behavior.append("disassembly declares constant buffers")
        if any("discard" in line.lower() or "clip" in line.lower() for line in preview):
            behavior.append("shader may conditionally discard pixels")

    return {
        "stage": stage or None,
        "name": shader_info.get("name"),
        "entry": shader_info.get("entry"),
        "bindings": {
            "srv": int(bind.get("srv", 0) or 0),
            "uav": int(bind.get("uav", 0) or 0),
            "cbv": int(bind.get("cbv", 0) or 0),
            "smp": int(bind.get("smp", 0) or 0),
        },
        "cbufs": shader_data.get("cbufs", []) or [],
        "behavior": behavior,
        "disasm_target": disasm_data.get("target"),
        "disasm_line_count": disasm_data.get("line_count"),
        "full_disasm_available": bool(disasm_data.get("text")),
        "code_preview": code.get("text"),
        "code_truncated": code.get("truncated"),
    }


def analyze_pass(
    pass_packet: dict,
    pipeline_state: dict | None = None,
    shader: dict | None = None,
    shader_disasm: dict | None = None,
    texture_usages: list[dict] | None = None,
    consumer_shader_evidence: list[dict] | None = None,
    visual_validation: dict | None = None,
) -> dict:
    packet = _packet_data(pass_packet)
    pass_info = packet.get("pass", {}) or {}
    rep_draw = packet.get("rep_draw") or {}
    io_info = packet.get("io", {}) or {}

    if pipeline_state is None:
        pipeline_state = rep_draw.get("pipe")
    if shader is None:
        shader = rep_draw.get("shader")

    pass_name = str(pass_info.get("pass", "unknown"))
    pass_name_l = pass_name.lower()
    draw_count, dispatch_count, clear_count = _stats(pass_info)
    res = _pipeline_res(pipeline_state)
    shader_data = _shader_data(shader)
    shader_stage = str(shader_data.get("stage", ""))
    consumer_hints = _pass_name_list(texture_usages)
    inputs = _summarize_inputs(rep_draw)
    outputs, output_uncertainties = _summarize_outputs(pass_packet, consumer_shader_evidence)
    shader_summary = _shader_summary(shader, shader_disasm, rep_draw)

    evidence: list[str] = []
    interpretation: list[str] = []
    next_checks: list[str] = []
    alternatives: list[str] = []
    uncertainties: list[str] = list(output_uncertainties)
    role = "unknown"
    confidence = "low"

    rep_type = str(rep_draw.get("type", ""))
    rt_count = int(res.get("rt", 0) or 0)
    ds_count = int(res.get("ds", 0) or 0)
    uav_count = int(res.get("uav", 0) or 0)
    output_count = len(io_info.get("out_rt", []) or [])
    has_depth_output = io_info.get("out_ds") is not None

    if dispatch_count > 0 or rep_type == "Dispatch":
        role = "compute_processing_pass"
        confidence = "high" if uav_count > 0 else "medium"
        evidence.append("dispatch count is non-zero or representative event type is Dispatch")
        if uav_count > 0:
            evidence.append("pipeline state shows UAV bindings")
        if consumer_hints:
            evidence.append("output resources have downstream consumers: {}".format(", ".join(consumer_hints[:3])))
        interpretation.append("This pass likely performs compute-side processing on intermediate resources.")
        next_checks.extend(
            [
                "inspect_texture_usage on the main UAV outputs",
                "inspect_shader for compute stage resource usage details",
            ]
        )
    elif draw_count > 0 and (output_count >= 2 or rt_count >= 2 or "colour" in pass_name_l or "color" in pass_name_l):
        role = "graphics_colour_or_gbuffer_pass"
        confidence = "high" if output_count >= 2 or rt_count >= 2 else "medium"
        evidence.append("draw count dominates and the pass looks graphics-oriented")
        if output_count >= 2:
            evidence.append(f"pass packet reports {output_count} color outputs")
        elif rt_count >= 2:
            evidence.append("pipeline state shows multiple render targets")
        if has_depth_output:
            evidence.append("pass packet reports a depth output")
        if shader_stage == "ps":
            evidence.append("representative shader stage is pixel shader")
        if consumer_hints:
            evidence.append("output resources are consumed later by: {}".format(", ".join(consumer_hints[:3])))
        interpretation.append("This pass likely contributes color or gbuffer-style graphics outputs.")
        alternatives.extend(["lighting_composite_pass", "main_graphics_pass"])
        next_checks.extend(
            [
                "inspect_texture_usage on the main render targets",
                "inspect_shader for pixel-stage resource details",
                "inspect downstream consumer passes before assigning semantic roles to each GBuffer RT",
                "read the current and downstream shaders when inferring channel meaning",
            ]
        )
    elif "depth" in pass_name_l and draw_count > 0:
        role = "depth_prepass_or_depth_only"
        confidence = "high" if has_depth_output or (ds_count > 0 and rt_count == 0) else "medium"
        evidence.append("pass name contains depth")
        evidence.append("draw count is non-zero while dispatch count is zero")
        if has_depth_output or ds_count > 0:
            evidence.append("depth output is present")
        if output_count == 0 and rt_count == 0:
            evidence.append("pipeline state shows no color targets")
        interpretation.append("This pass likely prepares or updates depth for later graphics work.")
        next_checks.extend(
            [
                "inspect_texture_usage on the depth output",
                "get_draw_packet for a representative draw if vertex-stage context matters",
            ]
        )
    elif draw_count > 0:
        role = "graphics_pass"
        confidence = "low"
        evidence.append("draw count is non-zero")
        if shader_stage:
            evidence.append(f"representative shader stage is {shader_stage}")
        interpretation.append("This pass is graphics-oriented, but current evidence is too weak for a stronger label.")
        next_checks.extend(
            [
                "inspect_pipeline_state for output bindings",
                "inspect_texture_usage on any visible outputs",
            ]
        )
    else:
        evidence.append("available evidence is insufficient for a stronger classification")
        next_checks.extend(
            [
                "get_pass_packet for a more representative pass selection",
                "inspect_pipeline_state for a representative event",
            ]
        )

    if not evidence:
        evidence.append("no strong evidence collected")

    if not inputs:
        uncertainties.append("Input summary is limited because only representative draw bindings are available.")
    if role == "graphics_colour_or_gbuffer_pass" and output_count >= 2:
        uncertainties.append("Per-RT and per-channel roles should not be treated as settled until downstream consumers and relevant shaders are inspected.")

    deduped_uncertainties = []
    seen_uncertainties = set()
    for item in uncertainties:
        if item not in seen_uncertainties:
            seen_uncertainties.add(item)
            deduped_uncertainties.append(item)

    return {
        "pass": {
            "eid": pass_info.get("eid"),
            "name": pass_name,
            "stats": {
                "draw": draw_count,
                "dispatch": dispatch_count,
                "clear": clear_count,
            },
        },
        "role": {
            "judgment": role,
            "confidence": confidence,
            "alternatives": alternatives,
        },
        "inputs": inputs,
        "outputs": outputs,
        "shader_summary": shader_summary,
        "visual_validation": visual_validation or {},
        "evidence": evidence,
        "interpretation": interpretation,
        "next_checks": next_checks,
        "uncertainties": deduped_uncertainties,
        "context": {
            "rep_draw": rep_draw or None,
            "pipeline_res": res,
            "shader_stage": shader_stage or None,
            "output_count": output_count,
            "has_depth_output": has_depth_output,
            "consumer_hints": consumer_hints,
            "role_analysis_pending": role == "graphics_colour_or_gbuffer_pass" and output_count >= 2,
            "consumer_shader_evidence_count": len(consumer_shader_evidence or []),
            "has_visual_validation": bool(visual_validation),
        },
    }
