import importlib.util
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

_path = Path(__file__).resolve().parents[1] / "bridge_extension/renderdoc_mcp_bridge/server.py"
_spec = importlib.util.spec_from_file_location("bridge_server_liveness_tests", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class BridgeLivenessTests(unittest.TestCase):
    def test_long_request_refreshes_heartbeat_before_response(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(_module, "IPC_DIR", directory), patch.object(_module, "INSTANCES_DIR", str(Path(directory) / "instances")):
                handler = types.SimpleNamespace()
                server = _module.BridgeServer(handler, bridge_id="test")
                server._running = True
                def handle(request):
                    # Reproduces a handler that consumed more than the 2-second
                    # client freshness interval, without sleeping in the test.
                    Path(server.heartbeat_file).write_text("0.0", encoding="utf-8")
                    return {"id": request["id"], "result": {"ok": True}}
                handler.handle = handle
                request = Path(server.requests_dir) / "request.json"
                request.write_text(json.dumps({"id": "request", "method": "long_export"}), encoding="utf-8")
                server._poll()
                response = Path(server.responses_dir) / "request.json"
                self.assertTrue(response.exists())
                self.assertGreater(float(Path(server.heartbeat_file).read_text()), time.time() - 2.0)


if __name__ == "__main__":
    unittest.main()
