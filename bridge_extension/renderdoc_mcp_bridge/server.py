"""File-based local bridge server for qrenderdoc extension mode."""

import json
import os
import shutil
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
INSTANCES_DIR = os.path.join(IPC_DIR, "instances")
STALE_INSTANCE_SECONDS = 60.0


class BridgeServer(QObject):
    """Simple polling bridge server for qrenderdoc extension mode."""

    def __init__(self, handler, parent=None, bridge_id=None):
        if QTimer is not None:
            super().__init__(parent)
        self.handler = handler
        self.bridge_id = bridge_id or "{}-{}".format(os.getpid(), uuid.uuid4().hex[:8])
        self.started_at = time.time()
        self.instance_dir = os.path.join(INSTANCES_DIR, self.bridge_id)
        self.requests_dir = os.path.join(self.instance_dir, "requests")
        self.responses_dir = os.path.join(self.instance_dir, "responses")
        self.heartbeat_file = os.path.join(self.instance_dir, "heartbeat")
        self.info_file = os.path.join(self.instance_dir, "info.json")
        self._timer = None
        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        os.makedirs(IPC_DIR, exist_ok=True)
        os.makedirs(INSTANCES_DIR, exist_ok=True)
        os.makedirs(self.requests_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def start(self):
        self._running = True
        self._stop_event.clear()
        self._cleanup_instance_files()
        self._cleanup_stale_instances()
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
        self._cleanup_instance_dir()

    def _thread_main(self):
        while not self._stop_event.is_set():
            self._poll()
            self._stop_event.wait(0.1)

    def _cleanup_instance_files(self):
        for path in (self.heartbeat_file, self.info_file):
            self._safe_remove(path)
        for directory in (self.requests_dir, self.responses_dir):
            try:
                for name in os.listdir(directory):
                    path = os.path.join(directory, name)
                    if os.path.isfile(path):
                        os.remove(path)
            except OSError:
                pass

    def _cleanup_instance_dir(self):
        try:
            shutil.rmtree(self.instance_dir)
        except OSError:
            self._cleanup_instance_files()

    def _cleanup_stale_instances(self):
        try:
            names = os.listdir(INSTANCES_DIR)
        except OSError:
            return
        now = time.time()
        for name in names:
            if name == self.bridge_id:
                continue
            instance_dir = os.path.join(INSTANCES_DIR, name)
            heartbeat_file = os.path.join(instance_dir, "heartbeat")
            try:
                with open(heartbeat_file, "r", encoding="utf-8") as handle:
                    heartbeat = float(handle.read().strip())
            except (OSError, ValueError):
                try:
                    heartbeat = os.path.getmtime(instance_dir)
                except OSError:
                    continue
            if now - heartbeat > STALE_INSTANCE_SECONDS:
                try:
                    shutil.rmtree(instance_dir)
                except OSError:
                    pass

    @staticmethod
    def _safe_remove(path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    @staticmethod
    def _write_json_atomic(path, payload):
        temp_path = "{}.{}.tmp".format(path, uuid.uuid4().hex)
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)

    def _next_request_file(self):
        try:
            items = [
                os.path.join(self.requests_dir, name)
                for name in os.listdir(self.requests_dir)
                if name.endswith(".json")
            ]
        except OSError:
            return None
        if not items:
            return None
        items.sort(key=lambda path: os.path.getmtime(path))
        return items[0]

    def _instance_info(self):
        info = {
            "window_id": self.bridge_id,
            "bridge_id": self.bridge_id,
            "pid": os.getpid(),
            "started_at": self.started_at,
            "updated_at": time.time(),
        }
        describe = getattr(self.handler, "describe_instance", None)
        if callable(describe):
            details = describe() or {}
            info.update(details)
        return info

    def _write_liveness(self):
        try:
            with open(self.heartbeat_file, "w", encoding="utf-8") as handle:
                handle.write(str(time.time()))
        except OSError:
            pass
        try:
            self._write_json_atomic(self.info_file, self._instance_info())
        except OSError:
            pass

    def _poll(self):
        if not self._running:
            return
        self._write_liveness()
        request_file = self._next_request_file()
        if request_file is None:
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
                response_file = os.path.join(self.responses_dir, "{}.json".format(response_id))
            else:
                response_file = os.path.join(self.responses_dir, "unknown.json")

            self._write_json_atomic(response_file, response)
        except Exception:  # pragma: no cover - runtime safety
            traceback.print_exc()
