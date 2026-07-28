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
    def __init__(self):
        self.calls = []

    def call(self, method, params, window_id=None):
        self.calls.append((method, params, window_id))
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

    def test_live_registry_exposes_buffer_value_tools(self):
        registry = runtime.LiveToolRegistry(client=object())

        self.assertIn("inspect_cbuffer_values", registry.handlers)
        self.assertIn("read_buffer", registry.handlers)
        self.assertIn("list_live_windows", registry.handlers)

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
        self.assertIn("export_shader_decompiled_hlsl", registry.handlers)

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

    def test_live_registry_routes_shader_hlsl_export_tool(self):
        client = _RecordingClient()
        registry = runtime.LiveToolRegistry(client=client)

        result = registry.invoke(
            "export_shader_decompiled_hlsl",
            {
                "eid": 8539,
                "stage": "ps",
                "dest": "D:/out/eid_8539_ps.hlsl",
                "processor": "Ruri DXBC -> HLSL",
                "overwrite": True,
                "timeout": 30.0,
                "window_id": "win-a",
            },
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            client.calls,
            [
                (
                    "export_shader_decompiled_hlsl",
                    {
                        "eid": 8539,
                        "stage": "ps",
                        "dest": "D:/out/eid_8539_ps.hlsl",
                        "processor": "Ruri DXBC -> HLSL",
                        "overwrite": True,
                        "timeout": 30.0,
                    },
                    "win-a",
                )
            ],
        )
