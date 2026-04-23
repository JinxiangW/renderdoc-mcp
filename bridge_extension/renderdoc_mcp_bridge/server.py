"""File-based local bridge server for qrenderdoc extension mode."""

import json
import os
import tempfile
import threading
import time
import traceback
import uuid

try:
    from PySide2.QtCore import QObject, QTimer
except ImportError:  # pragma: no cover - exercised in RenderDuck without PySide2
    QObject = object
    QTimer = None

IPC_DIR = os.path.join(tempfile.gettempdir(), "renderdoc_mcp_bridge")
REQUESTS_DIR = os.path.join(IPC_DIR, "requests")
RESPONSES_DIR = os.path.join(IPC_DIR, "responses")
REQUEST_FILE = os.path.join(IPC_DIR, "request.json")
RESPONSE_FILE = os.path.join(IPC_DIR, "response.json")
LOCK_FILE = os.path.join(IPC_DIR, "lock")
HEARTBEAT_FILE = os.path.join(IPC_DIR, "heartbeat")


class BridgeServer(QObject):
    """Simple polling bridge server for qrenderdoc extension mode."""

    def __init__(self, handler, parent=None):
        if QTimer is not None:
            super().__init__(parent)
        self.handler = handler
        self._timer = None
        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        os.makedirs(IPC_DIR, exist_ok=True)
        os.makedirs(REQUESTS_DIR, exist_ok=True)
        os.makedirs(RESPONSES_DIR, exist_ok=True)

    def start(self):
        self._running = True
        self._stop_event.clear()
        self._cleanup()
        if QTimer is not None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._poll)
            self._timer.start(100)
        else:
            self._thread = threading.Thread(target=self._thread_main, name="renderdoc_mcp_bridge", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._cleanup()

    def _thread_main(self):
        while not self._stop_event.is_set():
            self._poll()
            self._stop_event.wait(0.1)

    def _cleanup(self):
        for path in (REQUEST_FILE, RESPONSE_FILE, LOCK_FILE, HEARTBEAT_FILE):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        for directory in (REQUESTS_DIR, RESPONSES_DIR):
            try:
                for name in os.listdir(directory):
                    if name.endswith(".json"):
                        os.remove(os.path.join(directory, name))
            except OSError:
                pass

    def _poll(self):
        if not self._running:
            return
        try:
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as handle:
                handle.write(str(time.time()))
        except OSError:
            pass
        try:
            request_paths = self._modern_request_paths()
            if request_paths:
                self._handle_request_file(request_paths[0], modern=True)
                return
            if os.path.exists(REQUEST_FILE) and not os.path.exists(LOCK_FILE):
                self._handle_request_file(REQUEST_FILE, modern=False)
        except Exception:  # pragma: no cover - runtime safety
            traceback.print_exc()

    def _modern_request_paths(self):
        try:
            paths = [
                os.path.join(REQUESTS_DIR, name)
                for name in os.listdir(REQUESTS_DIR)
                if name.endswith(".json")
            ]
        except OSError:
            return []
        return sorted(paths, key=lambda item: os.path.getmtime(item))

    def _handle_request_file(self, request_path, modern):
        with open(request_path, "r", encoding="utf-8") as handle:
            request = json.load(handle)
        os.remove(request_path)

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

        response_path = RESPONSE_FILE
        if modern:
            response_id = request.get("id") or "response"
            response_path = os.path.join(RESPONSES_DIR, "{}.json".format(response_id))

        self._atomic_write_json(response_path, response)

    @staticmethod
    def _atomic_write_json(path, payload):
        tmp_path = "{}.{}.tmp".format(path, uuid.uuid4().hex)
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
