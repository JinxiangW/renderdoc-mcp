from __future__ import annotations

from typing import Any


def _sample_stats(scan: dict) -> dict[str, Any]:
    samples = scan.get("samples", []) or []
    full_screen = 0
    local = 0
    tiny = 0
    logo_like = 0
    large_local = 0
    max_overlay = 0.0
    max_idx = 0

    for item in samples:
        overlay = float((item.get("overlay") or {}).get("coverage", 0.0) or 0.0)
        idx = int(((item.get("draw") or {}).get("counts") or {}).get("idx", 0) or 0)
        hint = str(item.get("semantic_hint") or "")
        if overlay >= 0.85:
            full_screen += 1
        if overlay < 0.25:
            local += 1
        if overlay <= 0.01:
            tiny += 1
        if 0.02 <= overlay <= 0.15:
            large_local += 1
        if "translucent_signage" in hint:
            logo_like += 1
        max_overlay = max(max_overlay, overlay)
        max_idx = max(max_idx, idx)

    return {
        "samples": samples,
        "full_screen": full_screen,
        "local": local,
        "tiny": tiny,
        "logo_like": logo_like,
        "large_local": large_local,
        "max_overlay": max_overlay,
        "max_idx": max_idx,
    }


def classify_scan(scan: dict, evidence: dict | None = None) -> dict[str, Any]:
    stats = _sample_stats(scan)
    pass_info = scan.get("pass", {}) or {}
    draw_count = int((pass_info.get("stats") or {}).get("draw", 0) or 0)
    evidence = evidence or {}
    mesh_signals = evidence.get("mesh_signals", {}) or {}
    visual_signals = evidence.get("visual_signals", {}) or {}

    candidates: list[dict[str, Any]] = []

    if visual_signals.get("translucent_signage"):
        candidates.append(
            {
                "family": "overlay_projection",
                "label": "translucent_signage",
                "confidence": "high",
                "evidence": [
                    "补充证据明确指向 signage / logo / panel 一类内容",
                    "允许直接覆盖 scan-only 的中间候选",
                ],
            }
        )

    if stats["logo_like"] >= 2:
        candidates.append(
            {
                "family": "overlay_projection",
                "label": "translucent_signage",
                "confidence": "high",
                "evidence": [
                    f"logo/signage 半透候选样本数量={stats['logo_like']}",
                    "多个样本具有局部小范围覆盖 + 多 2D 纹理 + 与 scene color 合成的特征",
                ],
            }
        )

    skeletal_actions = mesh_signals.get("skeletal_actions", []) or []
    if skeletal_actions and visual_signals.get("subject_reveal_sequence"):
        candidates.append(
            {
                "family": "scene_geometry",
                "label": "foreground_character_pass",
                "confidence": "high",
                "evidence": [
                    f"skeletal mesh action 数量={len(skeletal_actions)}",
                    "视觉序列表明主体从 silhouette 被逐步补成可见角色",
                ],
            }
        )

    if stats["full_screen"] >= 1 and stats["local"] >= 1:
        candidates.append(
            {
                "family": "overlay_projection",
                "label": "decal_pass",
                "confidence": "medium",
                "evidence": [
                    f"全屏样本数量={stats['full_screen']}",
                    f"局部样本数量={stats['local']}",
                    "pass 同时包含 bootstrap 和大量局部覆盖样本",
                ],
            }
        )

    if stats["full_screen"] >= 2 and stats["logo_like"] == 0 and stats["large_local"] >= 1:
        candidates.append(
            {
                "family": "scene_geometry",
                "label": "foreground_character_pass",
                "confidence": "medium",
                "evidence": [
                    f"全屏样本数量={stats['full_screen']}",
                    f"中等覆盖样本数量={stats['large_local']}",
                    "存在前景主体逐步补绘再收尾合成的结构",
                ],
            }
        )

    if stats["full_screen"] >= max(1, len(stats["samples"]) - 1):
        candidates.append(
            {
                "family": "lighting_composite",
                "label": "deferred_lighting",
                "confidence": "medium",
                "evidence": [
                    "绝大多数样本是全屏覆盖",
                    "适合进一步检查是否读取多张前序 RT / depth",
                ],
            }
        )

    if not candidates and draw_count > 0:
        candidates.append(
            {
                "family": "unknown",
                "label": "needs_action_cluster_drilldown",
                "confidence": "low",
                "evidence": [
                    "当前扫描结果不足以落到语义 taxonomy",
                    "应继续下钻到 action cluster",
                ],
            }
        )

    # Keep highest-confidence candidate first, preserving original order among equals.
    order = {"high": 3, "medium": 2, "low": 1}
    candidates = sorted(
        candidates,
        key=lambda item: order.get(str(item.get("confidence", "low")), 0),
        reverse=True,
    )
    primary = candidates[0]
    return {
        "primary": primary,
        "candidates": candidates,
    }
