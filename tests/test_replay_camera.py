import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import threading
import types
import unittest

from renderdoc_mcp.server import runtime
from tests.test_runtime import _RecordingClient


def camera_module():
    package = "camera_domain_tests_package"
    root = Path(__file__).resolve().parents[1] / "bridge_extension/renderdoc_mcp_bridge/domains"
    names = ["renderdoc", package, package + ".base", package + ".capture", package + ".camera"]
    saved = {name: sys.modules.get(name) for name in names}
    sys.modules["renderdoc"] = types.SimpleNamespace(ResourceId=lambda x: x, CompType=types.SimpleNamespace(Typeless=0))
    sys.modules[package] = types.ModuleType(package)
    try:
        for name in ("base", "capture", "camera"):
            spec = importlib.util.spec_from_file_location(package + "." + name, root / (name + ".py"))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
        return mod
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


module = camera_module()


class Viewer:
    def __init__(self):
        self.state = {"supported": True, "enabled": False, "busy": False, "pending_update": False, "fields": []}
        self.calls = []

    def GetReplayCameraState(self):
        self.calls.append(("read", threading.get_ident()))
        return json.dumps(self.state)

    def GetCurrentResource(self):
        return "ResourceId::9"

    def ConfigureReplayCamera(self, payload):
        self.calls.append(("configure", threading.get_ident()))
        self.config = json.loads(payload)
        self.state.update(self.config)
        self.state.update(busy=True, pending_update=False)
        return ""

    def ResetReplayCamera(self):
        self.calls.append(("reset", threading.get_ident()))
        self.state.update(enabled=False, pending_update=True)

    def ViewTexture(self, *args):
        self.calls.append(("view_texture", threading.get_ident()))


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.viewer = Viewer()
        helper = types.SimpleNamespace(InvokeOntoUIThread=lambda fn: threading.Thread(target=fn).start())
        self.ctx = types.SimpleNamespace(
            IsCaptureLoaded=lambda: True, GetCaptureFilename=lambda: "D:/test.rdc",
            GetTextureViewer=lambda: self.viewer,
            Extensions=lambda: types.SimpleNamespace(GetMiniQtHelper=lambda: helper),
            GetTextures=lambda: [types.SimpleNamespace(resourceId="ResourceId::9")],
            GetAction=lambda eid: object() if eid == 12 else None,
            SetEventID=lambda *args: self.viewer.calls.append(("event", threading.get_ident())),
        )
        self.service = module.ReplayCameraService(self.ctx)

    def test_state_is_read_on_ui_thread_and_summary_hides_fields(self):
        self.viewer.state["fields"] = [{"shader": "ResourceId::1"}]
        result = self.service.get_replay_camera_state({})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["field_count"], 1)
        self.assertNotIn("fields", result["data"])
        self.assertNotEqual(self.viewer.calls[0][1], threading.get_ident())
        self.assertEqual(self.service.get_replay_camera_state({"include_fields": True})["data"]["fields"], self.viewer.state["fields"])

    def test_configure_uses_public_api_and_reports_pending(self):
        params = {"view": list(range(16)), "projection": list(range(16)), "fields": [{"slot": 0}], "enabled": True,
                  "eid": 12, "output_rid": "ResourceId::9", "expected_capture": "D:/test.rdc", "show": True}
        result = self.service.configure_replay_camera(params)
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["queued"])
        self.assertEqual(self.viewer.config["fields"], [{"slot": 0}])
        self.assertNotIn("expected_capture", self.viewer.config)
        self.assertTrue(all(tid != threading.get_ident() for _, tid in self.viewer.calls))

    def test_world_up_passes_through_and_old_frontend_is_guarded(self):
        self.assertEqual(self.service.configure_replay_camera({'world_up': '+Z'})['err']['code'], 'unsupported_frontend')
        self.viewer.state['world_up_axes'] = ['+X','-X','+Y','-Y','+Z','-Z']
        self.assertTrue(self.service.configure_replay_camera({'world_up': '+Z'})['ok'])
        self.assertEqual(self.viewer.config['world_up'], '+Z')
        self.viewer.state['busy'] = False
        self.viewer.state['recipe_supported'] = True
        recipe={'version':1,'world_up':'-X'}
        self.assertTrue(self.service.configure_replay_camera_recipe({'recipe':recipe,'run':False})['ok'])
        self.assertEqual(self.viewer.config['recipe']['world_up'], '-X')

    def test_busy_wrong_capture_invalid_output_and_nonfinite_do_not_mutate(self):
        for params, code in [({"expected_capture": "D:/other.rdc"}, "capture_mismatch"),
                             ({"output_rid": "ResourceId::404"}, "invalid_output"),
                             ({"eid": 404}, "invalid_event"),
                             ({"view": [float("nan")]}, "invalid_camera_config")]:
            result = self.service.configure_replay_camera(params)
            self.assertEqual(result["err"]["code"], code)
        self.viewer.state["busy"] = True
        self.assertEqual(self.service.configure_replay_camera({})["err"]["code"], "camera_busy")
        self.assertNotIn("configure", [name for name, _ in self.viewer.calls])

    def test_no_capture_and_old_frontend_have_explicit_errors(self):
        self.ctx.IsCaptureLoaded = lambda: False
        self.assertEqual(self.service.get_replay_camera_state({})["err"]["code"], "capture_not_loaded")
        self.ctx.IsCaptureLoaded = lambda: True
        self.ctx.GetTextureViewer = lambda: object()
        self.assertEqual(self.service.get_replay_camera_state({})["err"]["code"], "unsupported_frontend")

    def test_native_validation_failure_is_returned(self):
        self.viewer.ConfigureReplayCamera = lambda _: "Invalid matrix"
        result = self.service.configure_replay_camera({})
        self.assertEqual(result["err"]["code"], "invalid_camera_config")

    def test_reset_retains_fields_and_returns_queued(self):
        self.viewer.state["fields"] = [{"slot": 0}]
        result = self.service.reset_replay_camera({})
        self.assertTrue(result["data"]["queued"])
        self.assertFalse(result["data"]["enabled"])
        self.assertEqual(self.viewer.state["fields"], [{"slot": 0}])

    def test_registry_routes_target_window_and_fastmcp_exposes_schemas(self):
        client = _RecordingClient()
        registry = runtime.LiveToolRegistry(client)
        for name in ("get_replay_camera_state", "configure_replay_camera", "reset_replay_camera",
                     "configure_replay_camera_recipe", "apply_replay_camera_recipe"):
            registry.invoke(name, {"window_id": "win-a", "expected_capture": "D:/test.rdc"})
            self.assertEqual(client.calls[-1], (name, {"expected_capture": "D:/test.rdc"}, "win-a"))
        app = runtime.maybe_create_fastmcp()
        self.assertIsNotNone(app)

        async def check():
            from fastmcp import Client
            async with Client(app) as session:
                tools = {t.name: t for t in await session.list_tools()}
                self.assertIn("configure_replay_camera", tools)
                self.assertIn("configure_replay_camera_recipe", tools)
                self.assertIn("apply_replay_camera_recipe", tools)
                self.assertEqual(tools["configure_replay_camera_recipe"].inputSchema["required"], ["recipe"])
                self.assertEqual(set(tools["configure_replay_camera"].inputSchema["required"]), {"view", "projection", "fields"})
        asyncio.run(check())

    def test_recipe_uses_public_api_and_can_store_without_running(self):
        self.viewer.state['recipe_supported'] = True
        recipe = {'version': 1, 'name': 'agent layout', 'camera': {}, 'layouts': []}
        result = self.service.configure_replay_camera_recipe({'recipe': recipe, 'run': False,
                                                             'expected_capture': 'D:/test.rdc'})
        self.assertTrue(result['ok'])
        self.assertEqual(self.viewer.config, {'recipe': recipe, 'run_recipe': False, 'show': True})

    def test_v2_recipe_requires_capability_and_passes_through_unchanged(self):
        self.viewer.state['recipe_supported'] = True
        recipe = {'version': 2, 'passes': [{'mode': 'skip', 'first_event': 2, 'last_event': 4,
                                         'reason': 'verified unused output'}],
                  'capture': {'size': 100, 'sha256': 'a' * 64}}
        self.assertEqual(self.service.configure_replay_camera_recipe({'recipe': recipe})['err']['code'],
                         'unsupported_frontend')
        self.viewer.state['recipe_passes_supported'] = True
        self.assertTrue(self.service.configure_replay_camera_recipe({'recipe': recipe, 'run': False})['ok'])
        self.assertEqual(self.viewer.config['recipe'], recipe)

    def test_recipe_guards_capture_busy_and_missing_frontend(self):
        self.assertEqual(self.service.configure_replay_camera_recipe({'recipe': {}})['err']['code'],
                         'unsupported_frontend')
        self.viewer.state['recipe_supported'] = True
        self.assertEqual(self.service.configure_replay_camera_recipe({'recipe': {}, 'expected_capture': 'D:/other.rdc'})['err']['code'],
                         'capture_mismatch')
        self.viewer.state['scanning'] = True
        self.assertEqual(self.service.configure_replay_camera_recipe({'recipe': {}})['err']['code'], 'camera_busy')
        self.assertEqual(self.service.apply_replay_camera_recipe({})['err']['code'], 'camera_busy')

    def test_recipe_apply_requires_completed_result(self):
        self.viewer.state['recipe_supported'] = True
        self.assertEqual(self.service.apply_replay_camera_recipe({})['err']['code'], 'no_recipe_result')
        self.viewer.state['recipe_result_ready'] = True
        self.assertTrue(self.service.apply_replay_camera_recipe({})['ok'])
        self.assertEqual(self.viewer.config, {'apply_recipe_result': True})

    def test_recipe_rejects_nonfinite_and_nonobject_data(self):
        self.assertEqual(self.service.configure_replay_camera_recipe({'recipe': []})['err']['code'], 'invalid_camera_recipe')
        self.assertEqual(self.service.configure_replay_camera_recipe({'recipe': {'offset': float('nan')}})['err']['code'], 'invalid_camera_recipe')


if __name__ == "__main__":
    unittest.main()
