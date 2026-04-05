"""Request routing for the qrenderdoc bridge extension."""

from .observe import CaptureStatusService, ObserveService


class RequestHandler:
    """Routes bridge requests to compact extension services."""

    def __init__(self, ctx):
        capture_service = CaptureStatusService(ctx)
        observe_service = ObserveService(ctx)
        self._handlers = {
            "ping": lambda _params: {"status": "ok", "message": "pong"},
            "get_capture_status": capture_service.run,
            "find_events": observe_service.run,
            "list_passes": observe_service.list_passes,
            "get_frame_packet": observe_service.get_frame_packet,
            "get_pass_packet": observe_service.get_pass_packet,
            "get_draw_packet": observe_service.get_draw_packet,
            "debug_resource_ctx": observe_service.debug_resource_ctx,
            "debug_resource_info": observe_service.debug_resource_info,
            "debug_save_texture": observe_service.debug_save_texture,
            "debug_save_overlay": observe_service.debug_save_overlay,
            "inspect_pipeline_state": observe_service.inspect_pipeline_state,
            "inspect_shader": observe_service.inspect_shader,
            "get_shader_disasm": observe_service.get_shader_disasm,
            "inspect_texture_usage": observe_service.inspect_texture_usage,
            "inspect_mesh": observe_service.inspect_mesh,
        }

    def handle(self, request):
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method not in self._handlers:
            return {
                "id": request_id,
                "error": {
                    "code": "method_not_found",
                    "message": "Unknown method: {}".format(method),
                },
            }

        try:
            result = self._handlers[method](params)
            return {"id": request_id, "result": result}
        except Exception as exc:
            return {
                "id": request_id,
                "error": {
                    "code": "request_failed",
                    "message": str(exc),
                },
            }
