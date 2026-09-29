"""Exercise camera MCP tools against RenderDuck's owned replay_overrides fixture."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fastmcp import Client
from renderdoc_mcp.server.runtime import maybe_create_fastmcp


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-id", required=True)
    parser.add_argument("--dest", required=True)
    args = parser.parse_args()
    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    async with Client(maybe_create_fastmcp()) as client:
        async def call(name, params=None, ok=True):
            response = await client.call_tool(name, {**(params or {}), "window_id": args.window_id})
            payload = json.loads(response.content[0].text)
            if ok:
                assert payload.get("ok"), payload
            return payload

        async def settled():
            for _ in range(100):
                state = (await call("get_replay_camera_state"))["data"]
                if not state["busy"] and not state["pending_update"]:
                    assert not state["last_error"], state
                    return state
                await asyncio.sleep(.1)
            raise AssertionError("camera replay did not settle")

        state = (await call("get_replay_camera_state"))["data"]
        assert "fixture-" in state["capture_path"], "Run only against the owned fixture, not a user's capture"
        matrices = [float(i % 5 == 0) for i in range(16)]
        cb = (await call("inspect_cbuffer_values", {"eid": 13, "stage": "vs", "slot": 0}))["data"]
        field = {"semantic": "View", "shader": cb["shader"]["sid"], "stage": "VS", "slot": 0,
                 "offset": 0, "first_event": 2, "last_event": 35, "row_major": True, "row_vector": False}
        config = {"view": matrices[:], "projection": matrices[:], "fields": [field], "eid": 35,
                  "output_rid": "ResourceId::48", "expected_capture": state["capture_path"], "show": False}
        await call("configure_replay_camera", config)
        state = await settled()
        assert state["enabled"] and state["field_count"] == 1
        await call("debug_save_texture", {"rid": "ResourceId::48", "eid": 35, "dest": str(dest / "baseline.png")})
        results.append("MCP configuration populated native fields and completed replay")

        response = await call("configure_replay_camera", {**config, "view": [1, 2]}, ok=False)
        assert not response["ok"]
        after = (await call("get_replay_camera_state", {"include_fields": True}))["data"]
        assert after["view"] == matrices and after["fields"] == [field]
        results.append("invalid matrix rejected without changing the visible configuration")

        config["view"][3] = .35
        await call("configure_replay_camera", config)
        await settled()
        await call("debug_save_texture", {"rid": "ResourceId::48", "eid": 35, "dest": str(dest / "moved.png")})
        await call("debug_save_texture", {"rid": "ResourceId::52", "eid": 69, "dest": str(dest / "reference.png")})
        assert (dest / "moved.png").read_bytes() == (dest / "reference.png").read_bytes()
        assert (dest / "baseline.png").read_bytes() != (dest / "moved.png").read_bytes()
        results.append("MCP camera image matches independent engine camera reference")

        await call("reset_replay_camera", {"expected_capture": state["capture_path"]})
        state = await settled()
        assert not state["enabled"] and state["field_count"] == 1
        await call("debug_save_texture", {"rid": "ResourceId::48", "eid": 35, "dest": str(dest / "restored.png")})
        assert (dest / "baseline.png").read_bytes() == (dest / "restored.png").read_bytes()
        results.append("MCP reset restores the exact image and retains field configuration")
    report = {"passed": True, "checks": results, "window_id": args.window_id,
              "images": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.glob("*.png")}}
    (dest / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
