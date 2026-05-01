"""File-based local bridge server for qrenderdoc extension mode."""

import json
import os
import tempfile
import time
import traceback
import uuid

from PySide2.QtCore import QObject, QTimer

IPC_DIR = os.path.join(tempfile.gettempdir(), "renderdoc_mcp_bridge")
REQUESTS_DIR = os.path.join(IPC_DIR, "requests")
RESPONSES_DIR = os.path.join(IPC_DIR, "responses")
LOCK_FILE = os.path.join(IPC_DIR, "lock")
HEARTBEAT_FILE = os.path.join(IPC_DIR, "heartbeat")


class BridgeServer(QObject):
    """Simple polling bridge server for qrenderdoc extension mode."""

    def __init__(self, handler, parent=None):
        super().__init__(parent)
        self.handler = handler
        self._timer = None
        self._running = False
        os.makedirs(IPC_DIR, exist_ok=True)
        os.makedirs(REQUESTS_DIR, exist_ok=True)
        os.makedirs(RESPONSES_DIR, exist_ok=True)

    def start(self):
        self._running = True
        self._cleanup()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(100)
        return True

    def stop(self):
        self._running = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._cleanup()

    def _cleanup(self):
        for path in (LOCK_FILE, HEARTBEAT_FILE):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        for directory in (REQUESTS_DIR, RESPONSES_DIR):
            try:
                for name in os.listdir(directory):
                    path = os.path.join(directory, name)
                    if os.path.isfile(path):
                        os.remove(path)
            except OSError:
                pass

    @staticmethod
    def _write_json_atomic(path, payload):
        temp_path = "{}.{}.tmp".format(path, uuid.uuid4().hex)
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(temp_path, path)

    @staticmethod
    def _next_request_file():
        try:
            items = [
                os.path.join(REQUESTS_DIR, name)
                for name in os.listdir(REQUESTS_DIR)
                if name.endswith(".json")
            ]
        except OSError:
            return None
        if not items:
            return None
        items.sort(key=lambda path: os.path.getmtime(path))
        return items[0]

    def _poll(self):
        if not self._running:
            return
        try:
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as handle:
                handle.write(str(time.time()))
        except OSError:
            pass
        request_file = self._next_request_file()
        if request_file is None or os.path.exists(LOCK_FILE):
            return

        try:
            with open(request_file, "r", encoding="utf-8") as handle:
                request = json.load(handle)
            os.remove(request_file)

            try:
                response = self.handler.handle(request)
            except Exception as exc:  # pragma: no cover - runtime safety
                traceback.print_exc()
                response = {
                    "id": request.get("id"),
                    "error": {
                        "code": "internal_error",
                        "message": str(exc),
                    },
                }

            response_id = request.get("id")
            if response_id:
                response_file = os.path.join(RESPONSES_DIR, "{}.json".format(response_id))
            else:
                response_file = os.path.join(RESPONSES_DIR, "unknown.json")

            self._write_json_atomic(response_file, response)
        except Exception:  # pragma: no cover - runtime safety
            traceback.print_exc()
