import importlib.util
from pathlib import Path
import sys
import threading
import types
import unittest

_package = "capture_ui_thread_tests_package"
_base = types.ModuleType(_package + ".base")
_base.BridgeService = type("BridgeService", (), {"__init__": lambda self, ctx: setattr(self, "ctx", ctx)})
_saved = {name: sys.modules.get(name) for name in ("renderdoc", _package, _package + ".base")}
sys.modules["renderdoc"] = types.SimpleNamespace()
sys.modules[_package] = types.ModuleType(_package)
sys.modules[_package + ".base"] = _base
try:
    _path = Path(__file__).resolve().parents[1] / "bridge_extension/renderdoc_mcp_bridge/domains/capture.py"
    _spec = importlib.util.spec_from_file_location(_package + ".capture", _path)
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
finally:
    for name, value in _saved.items():
        if value is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = value


class CaptureUIThreadTests(unittest.TestCase):
    def service(self):
        helper = types.SimpleNamespace(InvokeOntoUIThread=lambda callback: threading.Thread(target=callback).start())
        return _module.CaptureStatusService(types.SimpleNamespace(
            Extensions=lambda: types.SimpleNamespace(GetMiniQtHelper=lambda: helper)))

    def test_capture_callback_uses_dispatcher(self):
        caller = threading.get_ident()
        actual = self.service()._invoke_on_ui_thread(threading.get_ident, 1.0)
        self.assertNotEqual(caller, actual)

    def test_callback_error_returns_to_request(self):
        def fail():
            raise ValueError("capture failure")
        with self.assertRaisesRegex(ValueError, "capture failure"):
            self.service()._invoke_on_ui_thread(fail, 1.0)


if __name__ == "__main__":
    unittest.main()
