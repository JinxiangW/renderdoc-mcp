"""Resume a corpus inventory through the RenderDoc MCP bridge, one window at a time."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from renderdoc_mcp.integration import LiveBridgeClient
from index_capture_files import write_json


def same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def check_serialization(value: object) -> None:
    if isinstance(value, str) and ("<Swig Object" in value or "<SwigPyObject" in value):
        raise RuntimeError("Opaque SWIG object in serialized evidence: " + value[:120])
    if isinstance(value, dict):
        if "serialization_limit" in value or "serialization_error" in value:
            raise RuntimeError("Incomplete serialization: " + str(value))
        for item in value.values():
            check_serialization(item)
    elif isinstance(value, list):
        for item in value:
            check_serialization(item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--window-id", required=True)
    parser.add_argument("--only")
    parser.add_argument("--page-size", type=int, default=128)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    if not manifest.get("complete"):
        raise RuntimeError("Finish file hash inventory first")
    captures = manifest["captures"]
    priority = ["World/Endfield-frame238195.rdc", "Foliage/Endfield_2026.05.19_22.53_frame56480.rdc"]
    captures.sort(key=lambda item: (priority.index(item["relative_path"]) if item["relative_path"] in priority else 2, item["relative_path"]))
    if args.only:
        captures = [item for item in captures if args.only in item["relative_path"]]
        if not captures:
            raise ValueError("--only matched no capture")
    client = LiveBridgeClient(timeout=240)
    status_file = args.output / "corpus-status.json"
    status = json.loads(status_file.read_text(encoding="utf-8-sig")) if status_file.exists() else {"schema_version": 1, "captures": {}}

    def call(method, params=None):
        result = client.call(method, params or {}, window_id=args.window_id)
        if not result.get("ok"):
            raise RuntimeError(json.dumps(result, ensure_ascii=False))
        return result["data"]

    for index, capture in enumerate(captures, 1):
        relative = capture["relative_path"]
        capture_dir = args.output / relative
        record = status["captures"].get(relative, {})
        if record.get("complete") and record.get("schema_version", 0) >= 2 and record.get("sha256") == capture["sha256"]:
            print("[{}/{}] cached {}".format(index, len(captures), relative), flush=True)
            continue
        stat = Path(capture["path"]).stat()
        if (stat.st_size, stat.st_mtime_ns) != (capture["bytes"], capture["mtime_ns"]):
            raise RuntimeError("Capture changed since hash inventory: " + relative)
        record = {"schema_version": 2, "sha256": capture["sha256"], "complete": False, "state": "opening", "started_at": time.time()}
        status["captures"][relative] = record
        write_json(status_file, status)
        print("[{}/{}] opening {}".format(index, len(captures), relative), flush=True)
        try:
            current = call("get_capture_status")
            if not current.get("loaded") or not same_path(current.get("path", ""), capture["path"]):
                call("open_capture", {"path": capture["path"], "wait": 180})
            inventory_file = capture_dir / "inventory.json"
            if not inventory_file.exists():
                call("export_capture_inventory", {"dest": str(inventory_file), "mode": "resources"})
            inventory = json.loads(inventory_file.read_text(encoding="utf-8"))
            if inventory.get("schema_version", 0) < 2 or not inventory["complete"] or not same_path(inventory["capture_path"], capture["path"]):
                raise RuntimeError("Incomplete or mismatched resource inventory")
            check_serialization(inventory)
            record.update(state="pipelines", actions=inventory["actions_total"], resources=len(inventory["resources"]))
            write_json(status_file, status)
            after = 0
            pipelines = []
            while True:
                page_file = capture_dir / ("pipelines_{:06d}.json".format(after))
                if not page_file.exists():
                    call("export_capture_inventory", {"dest": str(page_file), "mode": "pipelines", "after_eid": after, "limit": args.page_size})
                page = json.loads(page_file.read_text(encoding="utf-8"))
                if page.get("schema_version", 0) < 2 or not page["complete"] or page["after_eid"] != after or not same_path(page["capture_path"], capture["path"]):
                    raise RuntimeError("Incomplete or mismatched pipeline page: " + str(page_file))
                check_serialization(page)
                pipelines.extend(page["pipelines"])
                record["pipeline_events"] = len(pipelines)
                write_json(status_file, status)
                if not page["has_more"]:
                    break
                if page["next_after_eid"] <= after:
                    raise RuntimeError("Non-advancing pipeline cursor")
                after = page["next_after_eid"]
            expected = {item["eid"] for item in inventory["actions"] if item["kind"] in ("Draw", "Dispatch")}
            observed = [item["eid"] for item in pipelines]
            if set(observed) != expected or len(observed) != len(set(observed)):
                raise RuntimeError("Pipeline event coverage mismatch")
            shaders = {}
            for event in pipelines:
                for stage, shader in event["stages"].items():
                    key = stage + ":" + shader.get("bytecode_sha256", shader["sid"])
                    item = shaders.setdefault(key, {"stage": stage, "sha256": shader.get("bytecode_sha256"), "names": [], "sids": [], "eids": []})
                    for field, source in (("names", shader["name"]), ("sids", shader["sid"])):
                        if source not in item[field]:
                            item[field].append(source)
                    item["eids"].append(event["eid"])
            summary = {"schema_version": 2, "capture": capture, "api": inventory["api"],
                       "event_counts": dict(Counter(item["kind"] for item in inventory["actions"])),
                       "resources": len(inventory["resources"]), "textures": len(inventory["textures"]),
                       "buffers": len(inventory["buffers"]), "pipeline_events": len(pipelines),
                       "unique_stage_bytecodes": len(shaders), "shaders": list(shaders.values()),
                       "passes": [item for item in inventory["actions"] if item["kind"] == "Marker"],
                       "inventory_complete": True, "algorithm_validation": "pending"}
            write_json(capture_dir / "summary.json", summary)
            record.update(complete=True, state="inventoried", completed_at=time.time(), unique_stage_bytecodes=len(shaders))
            write_json(status_file, status)
            print("[done] {}: {} draw/dispatch, {} shaders".format(relative, len(pipelines), len(shaders)), flush=True)
        except Exception as exc:
            record.update(state="error", error=str(exc), failed_at=time.time())
            write_json(status_file, status)
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
