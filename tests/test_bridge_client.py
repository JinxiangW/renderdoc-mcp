import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from renderdoc_mcp.integration.bridge_client import LiveBridgeClient


class BridgeClientTests(unittest.TestCase):
    def test_call_ignores_unrelated_response_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ipc_dir = Path(temp_dir)
            requests_dir = ipc_dir / "requests"
            responses_dir = ipc_dir / "responses"
            requests_dir.mkdir()
            responses_dir.mkdir()

            client = LiveBridgeClient(timeout=1.0)
            client.ipc_dir = ipc_dir
            client.requests_dir = requests_dir
            client.responses_dir = responses_dir
            client.heartbeat_file = ipc_dir / "heartbeat"
            client.heartbeat_file.write_text(str(time.time()), encoding="utf-8")

            def respond():
                deadline = time.time() + 1.0
                request_path = None
                while time.time() < deadline:
                    items = list(requests_dir.glob("*.json"))
                    if items:
                        request_path = items[0]
                        break
                    time.sleep(0.01)

                if request_path is None:
                    return

                payload = json.loads(request_path.read_text(encoding="utf-8"))
                request_path.unlink()

                (responses_dir / "other.json").write_text(
                    json.dumps({"id": "other", "result": {"ok": False}}),
                    encoding="utf-8",
                )
                time.sleep(0.05)
                (responses_dir / "{}.json".format(payload["id"])).write_text(
                    json.dumps({"id": payload["id"], "result": {"ok": True}}),
                    encoding="utf-8",
                )

            worker = threading.Thread(target=respond)
            worker.start()
            result = client.call("ping", {})
            worker.join()

        self.assertEqual(result, {"ok": True})
