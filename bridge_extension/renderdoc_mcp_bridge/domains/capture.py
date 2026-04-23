"""Capture-scoped live bridge services."""

import os
import time

import renderdoc as rd

from .base import BridgeService


class CaptureStatusService(BridgeService):
    def run(self, params):
        params = params or {}
        directory = params.get("directory") or params.get("root")

        if not self.ctx.IsCaptureLoaded():
            latest = self._latest_capture(directory) if directory else None
            return {
                "ok": True,
                "mode": "summary",
                "data": {
                    "loaded": False,
                    "latest": latest,
                    "latest_capture_path": latest.get("path") if latest else None,
                    "stale": bool(latest),
                    "is_latest": False if latest else None,
                },
                "err": None,
                "meta": {"cap": "active", "truncated": False},
            }

        path = self.ctx.GetCaptureFilename()
        status_dir = directory or os.path.dirname(path)
        stat = self._capture_stat(path)
        latest = self._latest_capture(status_dir) if status_dir else None
        freshness = self._freshness(path, stat, latest)

        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "loaded": True,
                "cap": "active",
                "path": path,
                "name": os.path.basename(path),
                "size": stat.get("size"),
                "mtime": stat.get("mtime"),
                "mtime_ts": stat.get("mtime_ts"),
                "api": str(self.ctx.APIProps().pipelineType),
                "directory": status_dir,
                "latest": latest,
                "latest_capture_path": latest.get("path") if latest else None,
                "latest_capture_mtime": latest.get("mtime") if latest else None,
                "is_latest": freshness["is_latest"],
                "stale": freshness["stale"],
                "source_type": self._infer_capture_source_type(),
            },
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }

    def open_capture(self, params):
        capture_path = params.get("path")
        if not capture_path:
            return self._error("missing_args", "path is required")

        path = os.path.abspath(str(capture_path))
        if not os.path.isfile(path):
            return self._error("capture_not_found", "Capture file not found: {}".format(path))
        if os.path.splitext(path)[1].lower() != ".rdc":
            return self._error("invalid_capture_type", "Expected .rdc file: {}".format(path))

        try:
            loaded = self.ctx.LoadCapture(path, rd.ReplayOptions(), path, False, True)
        except TypeError:
            try:
                loaded = self.ctx.LoadCapture(path, rd.ReplayOptions(), path, False)
            except TypeError:
                loaded = self.ctx.LoadCapture(path)
        except Exception as exc:
            return self._error("load_failed", str(exc))

        deadline = time.time() + float(params.get("wait", 10.0) or 10.0)
        while time.time() < deadline:
            try:
                if self.ctx.IsCaptureLoaded() and self._same_path(self.ctx.GetCaptureFilename(), path):
                    return self.run({"directory": os.path.dirname(path)})
            except Exception as exc:
                self._warn_swallow("capture.open.wait_status", exc)
            time.sleep(0.05)

        if self.ctx.IsCaptureLoaded():
            result = self.run({"directory": os.path.dirname(path)})
            result["data"]["requested_path"] = path
            result["data"]["load_result"] = str(loaded)
            if not self._same_path(result["data"].get("path"), path):
                result["data"]["warning"] = "Loaded capture path did not match requested path"
            return result

        return self._error("load_failed", "Capture did not become active: {}".format(path))

    def find_latest_capture(self, params):
        directory = params.get("directory") or params.get("root")
        if not directory:
            return self._error("missing_args", "directory is required")
        latest = self._latest_capture(directory, recursive=bool(params.get("recursive", True)))
        if latest is None:
            return self._error("capture_not_found", "No .rdc capture found under: {}".format(directory))
        return {
            "ok": True,
            "mode": "summary",
            "data": {"directory": os.path.abspath(str(directory)), "latest": latest},
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }

    def load_latest_capture(self, params):
        latest_result = self.find_latest_capture(params)
        if not latest_result["ok"]:
            return latest_result
        latest = latest_result["data"]["latest"]
        result = self.open_capture({"path": latest["path"], "wait": params.get("wait", 10.0)})
        if result.get("ok") and result.get("data") is not None:
            result["data"]["selected_latest"] = latest
        return result

    def wait_for_new_capture(self, params):
        directory = params.get("directory") or params.get("root")
        if not directory:
            return self._error("missing_args", "directory is required")

        previous_path = params.get("previous_path")
        if previous_path is None and self.ctx.IsCaptureLoaded():
            previous_path = self.ctx.GetCaptureFilename()
        previous_path = os.path.abspath(str(previous_path)) if previous_path else None
        timeout = float(params.get("timeout", 30.0) or 30.0)
        interval = float(params.get("interval", 0.5) or 0.5)
        deadline = time.time() + timeout

        previous_mtime = None
        if previous_path and os.path.exists(previous_path):
            previous_mtime = os.path.getmtime(previous_path)

        while time.time() < deadline:
            latest = self._latest_capture(directory, recursive=bool(params.get("recursive", True)))
            if latest is not None:
                is_different = not previous_path or not self._same_path(latest["path"], previous_path)
                is_newer = previous_mtime is None or latest["mtime_ts"] > previous_mtime
                if is_different and is_newer:
                    result = self.open_capture({"path": latest["path"], "wait": params.get("wait", 10.0)})
                    if result.get("ok") and result.get("data") is not None:
                        result["data"]["previous_path"] = previous_path
                        result["data"]["selected_latest"] = latest
                    return result
            time.sleep(interval)

        return self._error("timeout", "Timed out waiting for a newer capture")

    def _latest_capture(self, directory, recursive=True):
        root = os.path.abspath(str(directory))
        if not os.path.isdir(root):
            return None

        latest = None
        walker = os.walk(root) if recursive else [(root, [], os.listdir(root))]
        for current, _dirs, names in walker:
            for name in names:
                if not name.lower().endswith(".rdc"):
                    continue
                path = os.path.join(current, name)
                if not os.path.isfile(path):
                    continue
                stat = self._capture_stat(path)
                item = {
                    "path": path,
                    "name": name,
                    "size": stat.get("size"),
                    "mtime": stat.get("mtime"),
                    "mtime_ts": stat.get("mtime_ts"),
                }
                if latest is None or (item["mtime_ts"], item["name"]) > (latest["mtime_ts"], latest["name"]):
                    latest = item
        return latest

    @staticmethod
    def _capture_stat(path):
        try:
            stat = os.stat(path)
        except OSError:
            return {"size": None, "mtime": None, "mtime_ts": None}
        return {
            "size": stat.st_size,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
            "mtime_ts": stat.st_mtime,
        }

    def _freshness(self, path, stat, latest):
        if latest is None:
            return {"is_latest": None, "stale": False}
        is_latest = self._same_path(path, latest["path"])
        stale = (not is_latest) and bool(stat.get("mtime_ts") is None or latest["mtime_ts"] > stat["mtime_ts"])
        return {"is_latest": is_latest, "stale": stale}

    def _infer_capture_source_type(self):
        names = []

        def visit(actions):
            for action in actions:
                if len(names) >= 2000:
                    return
                try:
                    name = action.customName or action.GetName(self.ctx.GetStructuredFile()) or ""
                except Exception:
                    name = action.customName or ""
                if name:
                    names.append(name)
                if len(action.children) > 0:
                    visit(action.children)

        try:
            visit(self.ctx.CurRootActions())
        except Exception as exc:
            self._warn_swallow("capture.source_type.actions", exc)

        haystack = "\n".join(names).lower()
        signals = []
        editor_tokens = [
            "editorselectionoutlines",
            "compositeeditorprimitives",
            "gizmomaterial",
            "selectionoutline",
            "editorprimitive",
        ]
        pie_tokens = ["pie", "playineditor", "play in editor"]
        standalone_tokens = ["standalone"]

        for token in editor_tokens + pie_tokens + standalone_tokens:
            if token in haystack:
                signals.append(token)

        if any(token in haystack for token in pie_tokens):
            source = "pie"
            confidence = "medium"
        elif any(token in haystack for token in editor_tokens):
            source = "editor_viewport"
            confidence = "high"
        elif any(token in haystack for token in standalone_tokens):
            source = "standalone"
            confidence = "medium"
        else:
            source = "game"
            confidence = "low"

        return {"type": source, "confidence": confidence, "signals": signals[:16]}

    @staticmethod
    def _same_path(left, right):
        if not left or not right:
            return False
        return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))

    @staticmethod
    def _error(code, msg):
        return {
            "ok": False,
            "mode": "summary",
            "data": None,
            "err": {"code": code, "msg": msg},
            "meta": {"cap": "active", "truncated": False},
        }
