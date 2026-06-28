import io
import json
import unittest
from unittest.mock import patch

from renderdoc_mcp.server import runtime


class _FakeLiveRegistry:
    def __init__(self):
        self.handlers = {"find_events": object()}

    def available(self, window_id=None):
        return False


class _FakeOfflineRegistry:
    def __init__(self):
        self.handlers = {"get_capture_status": object()}

    def invoke(self, method, params):
        raise AssertionError("offline registry should not be used for live-only methods")


class _RecordingClient:
    def __init__(self, windows=None):
        self.calls = []
        self.windows = windows or [
            {
                "window_id": "win-a",
                "bridge_id": "win-a",
                "pid": 1234,
                "loaded": True,
                "capture_path": "D:/caps/a.rdc",
            }
        ]

    def available(self, bridge_id=None):
        return True

    def list_windows(self):
        return {
            "ok": True,
            "mode": "summary",
            "data": {"count": len(self.windows), "windows": self.windows},
            "err": None,
            "meta": {"cap": None, "truncated": False},
        }

    def call(self, method, params, window_id=None):
        self.calls.append((method, params, window_id))
        if method == "find_events":
            return {
                "ok": True,
                "data": {
                    "items": [
                        {
                            "eid": len(self.calls),
                            "name": "DrawIndexed",
                            "type": "Draw",
                            "marker": params.get("q"),
                        }
                    ]
                },
            }
        if method == "get_capture_status":
            return {"ok": True, "data": {"loaded": True, "path": "D:/caps/a.rdc"}}
        return {"ok": True}


class RuntimeTests(unittest.TestCase):
    def test_run_local_json_returns_structured_error_for_unavailable_live_method(self):
        with patch("renderdoc_mcp.server.runtime.LiveToolRegistry", _FakeLiveRegistry):
            with patch("renderdoc_mcp.server.runtime.OfflineToolRegistry", _FakeOfflineRegistry):
                with patch("sys.stdout", new=io.StringIO()) as stdout:
                    exit_code = runtime.run_local_json("find_events", {})

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["err"]["code"], "live_bridge_unavailable")
        self.assertIn("next_actions", payload["data"])

    def test_live_registry_exposes_buffer_value_tools(self):
        registry = runtime.LiveToolRegistry(client=object())

        self.assertIn("inspect_cbuffer_values", registry.handlers)
        self.assertIn("read_buffer", registry.handlers)
        self.assertIn("list_live_windows", registry.handlers)
        self.assertIn("attach_qrenderdoc", registry.handlers)
        self.assertIn("connect_live_bridge", registry.handlers)
        self.assertIn("close_capture", registry.handlers)
        self.assertIn("search_draw_events_by_ue_hint", registry.handlers)

    def test_live_registry_exposes_event_output_export_tool(self):
        registry = runtime.LiveToolRegistry(client=object())

        self.assertIn("save_event_output_texture", registry.handlers)

    def test_live_registry_exposes_shader_edit_tools(self):
        registry = runtime.LiveToolRegistry(client=object())

        self.assertIn("get_target_shader_encodings", registry.handlers)
        self.assertIn("apply_shader_edit", registry.handlers)
        self.assertIn("revert_shader_edit", registry.handlers)

    def test_live_registry_exposes_shader_raw_export_tool(self):
        registry = runtime.LiveToolRegistry(client=object())

        self.assertIn("export_shader_raw_bytes", registry.handlers)

    def test_live_registry_routes_shader_raw_export_tool(self):
        client = _RecordingClient()
        registry = runtime.LiveToolRegistry(client=client)

        result = registry.invoke(
            "export_shader_raw_bytes",
            {
                "eid": 8539,
                "stage": "ps",
                "dest": "D:/out/eid_8539_ps.dxbc",
                "window_id": "win-a",
            },
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            client.calls,
            [
                (
                    "export_shader_raw_bytes",
                    {"eid": 8539, "stage": "ps", "dest": "D:/out/eid_8539_ps.dxbc"},
                    "win-a",
                )
            ],
        )

    def test_attach_qrenderdoc_checks_selected_window_status(self):
        client = _RecordingClient()
        registry = runtime.LiveToolRegistry(client=client)

        result = registry.invoke("attach_qrenderdoc", {"window_id": "win-a"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["window_id"], "win-a")
        self.assertEqual(client.calls, [("get_capture_status", {}, "win-a")])

    def test_open_capture_routes_window_id_to_live_bridge(self):
        client = _RecordingClient()
        registry = runtime.LiveToolRegistry(client=client)

        result = registry.invoke("open_capture", {"path": "D:/caps/a.rdc", "window_id": "win-a"})

        self.assertEqual(result, {"ok": True})
        self.assertEqual(client.calls, [("open_capture", {"path": "D:/caps/a.rdc"}, "win-a")])

    def test_search_draw_events_by_ue_hint_expands_asset_and_material_terms(self):
        client = _RecordingClient()
        registry = runtime.LiveToolRegistry(client=client)

        result = registry.invoke(
            "search_draw_events_by_ue_hint",
            {
                "asset_path": "/Toon/Render/Blueprints/BP_ToonDisplay.BP_ToonDisplay",
                "material_name": "MI_ToonFace",
                "window_id": "win-a",
                "limit": 10,
            },
        )

        self.assertTrue(result["ok"])
        queries = [call[1]["q"] for call in client.calls if call[0] == "find_events"]
        self.assertIn("MI_ToonFace", queries)
        self.assertIn("BP_ToonDisplay", queries)
