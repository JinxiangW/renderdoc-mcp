"""File-based local bridge server for qrenderdoc extension mode."""

import json
import os
import tempfile
import time
import traceback

from PySide2.QtCore import QObject, QTimer

IPC_DIR = os.path.join(tempfile.gettempdir(), "renderdoc_mcp_bridge")
REQUEST_FILE = os.path.join(IPC_DIR, "request.json")
RESPONSE_FILE = os.path.join(IPC_DIR, "response.json")
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
        for path in (REQUEST_FILE, RESPONSE_FILE, LOCK_FILE, HEARTBEAT_FILE):
            try:
                if os.path.exists(path):
                    os.remove(path)
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
        if not os.path.exists(REQUEST_FILE) or os.path.exists(LOCK_FILE):
            return

        try:
            with open(REQUEST_FILE, "r", encoding="utf-8") as handle:
                request = json.load(handle)
            os.remove(REQUEST_FILE)

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

            with open(RESPONSE_FILE, "w", encoding="utf-8") as handle:
                json.dump(response, handle, ensure_ascii=False)
        except Exception:  # pragma: no cover - runtime safety
            traceback.print_exc()
