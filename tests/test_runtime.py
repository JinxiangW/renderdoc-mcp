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
