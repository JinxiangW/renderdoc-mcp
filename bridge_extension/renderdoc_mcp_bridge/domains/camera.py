"""Free-camera configuration through RenderDuck's public TextureViewer API.

No simulated input, private Qt access, or arbitrary script execution is used.
Mutations queue replay; inspect state in a subsequent request for completion.
"""

import json
import os

import renderdoc as rd

from .base import BridgeService
from .capture import CaptureStatusService


class ReplayCameraService(BridgeService):
    @staticmethod
    def _response(data=None, code=None, message=None):
        return {
            "ok": code is None,
            "mode": "summary",
            "data": data,
            "err": None if code is None else {"code": code, "msg": message},
            "meta": {"cap": "active", "truncated": False},
        }

    def _invoke(self, callback):
        try:
            return CaptureStatusService(self.ctx)._invoke_on_ui_thread(callback, 30.0)
        except Exception as exc:
            return self._response(code="camera_request_failed", message=str(exc))

    def _viewer(self, expected_capture=None):
        if not self.ctx.IsCaptureLoaded():
            return None, self._no_capture()
        if expected_capture and os.path.normcase(os.path.abspath(expected_capture)) != os.path.normcase(os.path.abspath(self.ctx.GetCaptureFilename())):
            return None, self._response(code="capture_mismatch", message="The selected window has a different capture loaded.")
        viewer = self.ctx.GetTextureViewer()
        if not all(callable(getattr(viewer, name, None)) for name in (
            "GetReplayCameraState", "ConfigureReplayCamera", "ResetReplayCamera"
        )):
            return None, self._response(
                data={"supported": False}, code="unsupported_frontend",
                message="This frontend lacks the replay camera API. Launch the updated RenderDuck build.",
            )
        return viewer, None

    def _state(self, viewer, include_fields=False):
        data = json.loads(viewer.GetReplayCameraState())
        data["capture_path"] = self.ctx.GetCaptureFilename()
        data["output_rid"] = str(viewer.GetCurrentResource())
        data["field_count"] = len(data.get("fields", []))
        if not include_fields:
            data.pop("fields", None)
        return data

    def get_replay_camera_state(self, params):
        def read():
            viewer, error = self._viewer(params.get("expected_capture"))
            if error:
                return error
            return self._response(self._state(viewer, bool(params.get("include_fields", False))))
        return self._invoke(read)

    def configure_replay_camera(self, params):
        # Finite-number validation is also performed by the native API before it changes the form.
        config = {key: params[key] for key in (
            "view", "projection", "fields", "speed", "forward", "world_up", "enabled", "show", "output_rid", "flip_y"
        ) if key in params and params[key] is not None}
        try:
            payload = json.dumps(config, allow_nan=False)
        except (ValueError, TypeError) as exc:
            return self._response(code="invalid_camera_config", message=str(exc))

        def configure():
            viewer, error = self._viewer(params.get("expected_capture"))
            if error:
                return error
            state = self._state(viewer)
            if not state.get("supported"):
                return self._response(state, "unsupported_capture", state.get("reason"))
            if params.get("world_up", "+Y") != "+Y" and not state.get("world_up_axes"):
                return self._response(code="unsupported_frontend", message="Frontend does not support configurable world up")
            if state.get("busy") or state.get("pending_update"):
                return self._response(state, "camera_busy", "Wait for camera replay to finish before configuring it again.")
            eid = params.get("eid")
            if eid is not None:
                if isinstance(eid, bool) or not isinstance(eid, int) or eid < 1 or self.ctx.GetAction(eid) is None:
                    return self._response(code="invalid_event", message="eid must identify an existing capture action.")
            output = None
            if params.get("output_rid"):
                for texture in self.ctx.GetTextures():
                    if str(texture.resourceId) == str(params["output_rid"]):
                        output = rd.ResourceId(texture.resourceId)
                        break
                if output is None:
                    return self._response(code="invalid_output", message="output_rid is not a texture in this capture.")
            error = viewer.ConfigureReplayCamera(payload)
            if error:
                return self._response(code="invalid_camera_config", message=str(error))
            # Both operations are on the UI thread. Native camera replay is already queued;
            # SetEventID queues behind it and keeps the UI/replay event selections in sync.
            if eid is not None:
                self.ctx.SetEventID([], eid, eid, True)
            data = self._state(viewer)
            data["queued"] = bool(data.get("busy") or data.get("pending_update"))
            return self._response(data)
        return self._invoke(configure)

    def reset_replay_camera(self, params):
        def reset():
            viewer, error = self._viewer(params.get("expected_capture"))
            if error:
                return error
            state = self._state(viewer)
            if not state.get("supported"):
                return self._response(state, "unsupported_capture", state.get("reason"))
            viewer.ResetReplayCamera()
            data = self._state(viewer)
            data["queued"] = bool(data.get("busy") or data.get("pending_update"))
            return self._response(data)
        return self._invoke(reset)

    def configure_replay_camera_recipe(self, params):
        recipe = params.get("recipe")
        if not isinstance(recipe, dict):
            return self._response(code="invalid_camera_recipe", message="recipe must be a JSON object")
        try:
            payload = json.dumps({"recipe": recipe, "run_recipe": params.get("run", True),
                                  "show": params.get("show", True)}, allow_nan=False)
        except (TypeError, ValueError) as exc:
            return self._response(code="invalid_camera_recipe", message=str(exc))
        def configure():
            viewer, error = self._viewer(params.get("expected_capture"))
            if error:
                return error
            state = self._state(viewer)
            if not state.get("recipe_supported"):
                return self._response(code="unsupported_frontend", message="Frontend does not support camera recipes")
            if recipe.get("version") == 2 and not state.get("recipe_passes_supported"):
                return self._response(code="unsupported_frontend", message="Frontend does not support version-2 camera/pass recipes")
            if recipe.get("world_up", "+Y") != "+Y" and not state.get("world_up_axes"):
                return self._response(code="unsupported_frontend", message="Frontend does not support configurable world up")
            if state.get("busy") or state.get("pending_update") or state.get("scanning"):
                return self._response(code="camera_busy", message="Wait for the current operation")
            error = viewer.ConfigureReplayCamera(payload)
            if error:
                return self._response(code="invalid_camera_recipe", message=str(error))
            data = self._state(viewer)
            data["queued"] = bool(data.get("scanning") or data.get("busy") or data.get("pending_update"))
            return self._response(data)
        return self._invoke(configure)

    def apply_replay_camera_recipe(self, params):
        def apply():
            viewer, error = self._viewer(params.get("expected_capture"))
            if error:
                return error
            state = self._state(viewer)
            if not state.get("recipe_supported"):
                return self._response(code="unsupported_frontend", message="Frontend does not support camera recipes")
            if state.get("scanning") or state.get("busy") or state.get("pending_update"):
                return self._response(code="camera_busy", message="Wait for the current operation")
            if not state.get("recipe_result_ready"):
                return self._response(code="no_recipe_result", message="Run a recipe and inspect its report first")
            error = viewer.ConfigureReplayCamera(json.dumps({"apply_recipe_result": True}))
            if error:
                return self._response(code="camera_apply_failed", message=str(error))
            data = self._state(viewer)
            data["queued"] = bool(data.get("busy") or data.get("pending_update"))
            return self._response(data)
        return self._invoke(apply)
