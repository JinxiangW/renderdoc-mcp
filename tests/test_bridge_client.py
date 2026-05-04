import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from renderdoc_mcp.integration.bridge_client import LiveBridgeClient, LiveBridgeError


def make_instance(ipc_dir: Path, window_id: str) -> Path:
    instance_dir = ipc_dir / "instances" / window_id
    (instance_dir / "requests").mkdir(parents=True)
    (instance_dir / "responses").mkdir()
    (instance_dir / "heartbeat").write_text(str(time.time()), encoding="utf-8")
    (instance_dir / "info.json").write_text(
        json.dumps(
            {
                "window_id": window_id,
                "bridge_id": window_id,
                "pid": 1234,
                "loaded": True,
                "capture_path": f"C:/Caps/{window_id}.rdc",
                "updated_at": time.time(),
            }
        ),
        encoding="utf-8",
    )
    return instance_dir


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

    def test_call_requires_window_id_when_multiple_instances_are_active(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ipc_dir = Path(temp_dir)
            make_instance(ipc_dir, "alpha")
            make_instance(ipc_dir, "beta")

            client = LiveBridgeClient(timeout=0.2)
            client.ipc_dir = ipc_dir

            self.assertTrue(client.available())
            with self.assertRaisesRegex(LiveBridgeError, "Multiple live qrenderdoc bridges"):
                client.call("ping", {})

    def test_call_routes_to_selected_window_instance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ipc_dir = Path(temp_dir)
            make_instance(ipc_dir, "alpha")
            beta_dir = make_instance(ipc_dir, "beta")
            beta_requests = beta_dir / "requests"
            beta_responses = beta_dir / "responses"

            client = LiveBridgeClient(timeout=1.0)
            client.ipc_dir = ipc_dir

            def respond():
                deadline = time.time() + 1.0
                request_path = None
                while time.time() < deadline:
                    items = list(beta_requests.glob("*.json"))
                    if items:
                        request_path = items[0]
                        break
                    time.sleep(0.01)

                if request_path is None:
                    return

                payload = json.loads(request_path.read_text(encoding="utf-8"))
                request_path.unlink()
                (beta_responses / "{}.json".format(payload["id"])).write_text(
                    json.dumps(
                        {
                            "id": payload["id"],
                            "result": {
                                "ok": True,
                                "window_id": "beta",
                                "params": payload["params"],
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            worker = threading.Thread(target=respond)
            worker.start()
            result = client.call("ping", {"value": 1}, window_id="beta")
            worker.join()

        self.assertEqual(result, {"ok": True, "window_id": "beta", "params": {"value": 1}})
