from __future__ import annotations

import argparse
import json
from pathlib import Path

from scan_pass_visuals import call_bridge, previous_write_eid, repo_root, slugify, unique_copy, write_json


def shader_hash_from_draw(draw_data: dict) -> str:
    text = str((((draw_data.get("shader") or {}).get("code") or {}).get("text") or ""))
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("shader hash "):
            return line[len("Shader hash ") :].strip()
    return ""


def classify_draw_cluster(draw_data: dict, mesh_data: dict | None) -> str:
    counts = (draw_data.get("counts") or {})
    idx = int(counts.get("idx", 0) or 0)
    state = draw_data.get("state") or {}
    depth = state.get("depth") or {}

    if idx <= 6:
        return "fullscreen_draw"

    attrs = [str(item.get("name", "")) for item in ((mesh_data or {}).get("attrs") or [])]
    attr_set = set(attrs)

    if "BLENDWEIGHTS" in attr_set and "BLENDINDICES" in attr_set:
        return "skeletal_mesh_draw"

    if attr_set and attr_set.issubset({"POSITION", "TEXCOORD", "TEXCOORD0"}):
        return "simple_effect_mesh_draw"

    if bool(depth.get("enabled")) and str(depth.get("func", "")).lower() == "equal":
        return "depth_equal_geometry_draw"

    return "other_geometry_draw"


def export_texture_if_possible(eid: int, rid: str, target: Path) -> str | None:
    try:
        resp = call_bridge("debug_save_texture", {"eid": eid, "rid": rid, "dest": "PNG"}, timeout=45)
    except Exception:
        return None
    path = ((resp.get("data") or {}).get("path")) or ""
    if not path:
        return None
    return str(unique_copy(path, target))


def representative_actions(pass_packet: dict) -> list[int]:
    reps = []
    for item in (pass_packet.get("data") or {}).get("rep", []) or []:
        if str(item.get("type", "")).lower() not in ("draw", "dispatch"):
            continue
        try:
            reps.append(int(item.get("eid")))
        except Exception:
            continue
    return reps


def bundle_summary(bundle: dict) -> dict:
    clusters = bundle.get("clusters", []) or []
    pass_info = bundle.get("pass", {}) or {}
    dominant = clusters[0] if clusters else {}
    secondary = [item.get("kind", "unknown") for item in clusters[1:3]]

    key_evidence: list[str] = []
    needs_detail: list[str] = []

    if dominant:
        rep_draw = dominant.get("representative_draw", {}) or {}
        state = rep_draw.get("state", {}) or {}
        depth = state.get("depth", {}) or {}
        targets = ((state.get("blend") or {}).get("targets") or [])
        blend_slots = [int(item.get("slot", -1)) for item in targets if bool(item.get("enabled"))]
        if blend_slots:
            key_evidence.append(f"dominant cluster blend enabled on RT slots {blend_slots}")
        if depth:
            key_evidence.append(
                "dominant cluster depth func={func} write={write}".format(
                    func=depth.get("func", "unknown"),
                    write=depth.get("write", False),
                )
            )
        bind = (((rep_draw.get("shader") or {}).get("bind")) or {})
        if bind:
            key_evidence.append(
                "representative shader bind srv={srv} cbv={cbv} smp={smp}".format(
                    srv=bind.get("srv", 0),
                    cbv=bind.get("cbv", 0),
                    smp=bind.get("smp", 0),
                )
            )
        if secondary:
            needs_detail.append("secondary clusters present")

    if len(clusters) > 2:
        needs_detail.append("cluster mix is broad")
    if int((pass_info.get("stats") or {}).get("draw", 0) or 0) > 150:
        needs_detail.append("high draw count; sample dominant cluster first")

    return {
        "pass": {
            "name": pass_info.get("pass", "unknown"),
            "eid": pass_info.get("eid", "unknown"),
            "stats": pass_info.get("stats", {}),
        },
        "dominant_cluster": {
            "kind": dominant.get("kind", "unknown"),
            "count": dominant.get("count", 0),
            "representative": dominant.get("representative"),
        },
        "secondary_clusters": secondary,
        "key_evidence": key_evidence,
        "needs_detail": needs_detail,
        "evidence_refs": [
            "bundle_full.json#clusters[0]",
            "bundle_full.json#actions",
        ],
    }


def build_bundle(marker: str, rep_limit: int, export_limit: int, out_dir: Path) -> dict:
    pass_packet = call_bridge("get_pass_packet", {"marker": marker, "limit": rep_limit}, timeout=60)
    pass_info = ((pass_packet.get("data") or {}).get("pass") or {})
    pass_name = str(pass_info.get("pass", marker))
    pass_dir = out_dir / slugify(pass_name)
    pass_dir.mkdir(parents=True, exist_ok=True)

    bundle = {
        "pass": pass_info,
        "clusters": [],
        "actions": [],
    }

    clusters: dict[str, dict] = {}

    for eid in representative_actions(pass_packet):
        draw_resp = call_bridge("get_draw_packet", {"eid": eid}, timeout=45)
        draw_data = draw_resp.get("data") or {}

        mesh_data = None
        if str(draw_data.get("type", "")).lower() == "draw":
            try:
                mesh_resp = call_bridge("inspect_mesh", {"eid": eid}, timeout=45)
                mesh_data = mesh_resp.get("data") or {}
            except Exception:
                mesh_data = None

        cluster_kind = classify_draw_cluster(draw_data, mesh_data)
        shader_hash = shader_hash_from_draw(draw_data)

        action_item = {
            "eid": eid,
            "name": draw_data.get("name"),
            "cluster": cluster_kind,
            "shader_hash": shader_hash,
            "counts": draw_data.get("counts"),
            "state": draw_data.get("state"),
            "mesh": mesh_data,
            "draw": draw_data,
        }
        bundle["actions"].append(action_item)

        cluster = clusters.setdefault(
            cluster_kind,
            {
                "kind": cluster_kind,
                "count": 0,
                "eids": [],
                "shader_hashes": {},
                "representative": None,
            },
        )
        cluster["count"] += 1
        cluster["eids"].append(eid)
        if shader_hash:
            cluster["shader_hashes"][shader_hash] = cluster["shader_hashes"].get(shader_hash, 0) + 1
        if cluster["representative"] is None:
            cluster["representative"] = eid

    cluster_list = sorted(clusters.values(), key=lambda item: (-int(item["count"]), str(item["kind"])))

    for cluster in cluster_list:
        rep_eid = int(cluster["representative"])
        action = next(item for item in bundle["actions"] if int(item["eid"]) == rep_eid)
        draw_data = action["draw"]
        cluster_dir = pass_dir / f"{cluster['kind']}_{rep_eid}"
        cluster_dir.mkdir(parents=True, exist_ok=True)

        write_json(cluster_dir / "draw.json", draw_data)
        if action.get("mesh") is not None:
            write_json(cluster_dir / "mesh.json", action["mesh"])

        shader = (draw_data.get("shader") or {})
        write_json(cluster_dir / "shader.json", shader)

        exports = {
            "overlay": None,
            "previous_rt0": None,
            "current_rt0": None,
            "bound_textures": [],
        }

        out_rt = (draw_data.get("io") or {}).get("out_rt", []) or []
        if out_rt:
            primary_rid = str(out_rt[0].get("rid"))
            try:
                overlay_resp = call_bridge(
                    "debug_save_overlay",
                    {"eid": rep_eid, "overlay": "drawcall", "rid": primary_rid, "dest": "PNG"},
                    timeout=45,
                )
                overlay_path = ((overlay_resp.get("data") or {}).get("path")) or ""
                if overlay_path:
                    exports["overlay"] = str(unique_copy(overlay_path, cluster_dir / "overlay.png"))
            except Exception:
                pass

            prev_eid = previous_write_eid(primary_rid, rep_eid)
            prev_path = export_texture_if_possible(prev_eid, primary_rid, cluster_dir / "prev_rt0.png")
            curr_path = export_texture_if_possible(rep_eid, primary_rid, cluster_dir / "curr_rt0.png")
            exports["previous_rt0"] = prev_path
            exports["current_rt0"] = curr_path

        bindings = ((shader.get("bindings") or {}).get("srv") or [])
        exported = 0
        for item in bindings:
            if exported >= export_limit:
                break
            meta = item.get("meta") or {}
            if meta.get("kind") != "tex":
                continue
            rid = str(item.get("rid") or "")
            if not rid:
                continue
            filename = f"srv_slot_{int(item.get('slot', -1))}_{slugify(str(item.get('name') or rid))}.png"
            exported_path = export_texture_if_possible(rep_eid, rid, cluster_dir / filename)
            bound_item = dict(item)
            bound_item["export"] = exported_path
            exports["bound_textures"].append(bound_item)
            exported += 1

        cluster["representative_draw"] = draw_data
        cluster["representative_mesh"] = action.get("mesh")
        cluster["exports"] = exports

        write_json(cluster_dir / "cluster.json", cluster)

    bundle["clusters"] = cluster_list
    summary = bundle_summary(bundle)
    write_json(pass_dir / "bundle_full.json", bundle)
    write_json(pass_dir / "bundle_summary.json", summary)
    write_json(pass_dir / "bundle.json", bundle)

    lines = []
    lines.append(f"Pass: {pass_name}")
    lines.append(f"EID: {pass_info.get('eid', 'unknown')}")
    lines.append("")
    lines.append("Action 簇:")
    for cluster in cluster_list:
        rep_eid = cluster["representative"]
        lines.append(f"- {cluster['kind']}: count={cluster['count']} rep={rep_eid}")
        top_hashes = sorted(cluster["shader_hashes"].items(), key=lambda item: (-item[1], item[0]))[:3]
        if top_hashes:
            lines.append(f"  shader_hashes={top_hashes}")
        rep_draw = cluster.get("representative_draw") or {}
        counts = rep_draw.get("counts") or {}
        lines.append(f"  idx={counts.get('idx', 0)} inst={counts.get('inst', 0)}")
        rep_mesh = cluster.get("representative_mesh") or {}
        attrs = [item.get("name") for item in (rep_mesh.get("attrs") or [])]
        if attrs:
            lines.append(f"  attrs={attrs}")
        exports = cluster.get("exports") or {}
        if exports.get("overlay"):
            lines.append(f"  overlay={exports['overlay']}")
        if exports.get("current_rt0"):
            lines.append(f"  current_rt0={exports['current_rt0']}")
        if exports.get("bound_textures"):
            lines.append("  bound_textures:")
            for tex in exports["bound_textures"]:
                lines.append(
                    "    - slot={slot} name={name} rid={rid} export={export}".format(
                        slot=tex.get("slot"),
                        name=tex.get("name"),
                        rid=tex.get("rid"),
                        export=tex.get("export"),
                    )
                )

    (pass_dir / "bundle.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a clustered evidence bundle for one pass.")
    parser.add_argument("--marker", required=True)
    parser.add_argument("--rep-limit", type=int, default=160)
    parser.add_argument("--export-limit", type=int, default=6)
    parser.add_argument("--out-dir", default=str(repo_root() / ".state" / "pass_bundles"))
    parser.add_argument("--out")
    parser.add_argument("--summary-out")
    parser.add_argument("--full-out")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    result = build_bundle(args.marker, args.rep_limit, args.export_limit, Path(args.out_dir))
    summary = bundle_summary(result)
    full_output = json.dumps(result, ensure_ascii=False, indent=2)
    summary_output = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.full_out:
        Path(args.full_out).write_text(full_output + "\n", encoding="utf-8")
    if args.summary_out:
        Path(args.summary_out).write_text(summary_output + "\n", encoding="utf-8")
    if args.out:
        Path(args.out).write_text((summary_output if args.summary_only else full_output) + "\n", encoding="utf-8")
    else:
        print(summary_output if args.summary_only else full_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
