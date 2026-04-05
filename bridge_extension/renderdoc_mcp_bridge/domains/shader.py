"""Shader inspection services."""

import renderdoc as rd

from .pipeline import ShaderSupportMixin


class ShaderServiceMixin(ShaderSupportMixin):
    def inspect_shader(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        stage_name = params.get("stage")
        if eid is None or not stage_name:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "eid and stage are required"},
                "meta": {"cap": "active", "truncated": False},
            }

        eid = int(eid)
        stage_enum = self._stage_enum_from_name(stage_name)
        if stage_enum is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_stage", "msg": "Unsupported stage"},
                "meta": {"cap": "active", "truncated": False},
            }

        result = None

        def collect(controller):
            nonlocal result
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()
            shader = pipe.GetShader(stage_enum)
            shader_str = str(shader)
            if not shader_str or "Null" in shader_str or shader_str == "ResourceId::0":
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "no_shader", "msg": "No shader bound for stage"},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            entry = pipe.GetShaderEntryPoint(stage_enum)
            refl = pipe.GetShaderReflection(stage_enum)
            bind = {
                "srv": self._safe_len(lambda: refl.readOnlyResources),
                "uav": self._safe_len(lambda: refl.readWriteResources),
                "cbv": self._safe_len(lambda: refl.constantBlocks),
                "smp": self._safe_len(lambda: refl.samplers),
            }
            cbufs = []
            try:
                for block in refl.constantBlocks:
                    cbufs.append(
                        {
                            "name": block.name,
                            "vars": len(block.variables),
                        }
                    )
            except Exception:
                pass

            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": eid,
                    "stage": str(stage_name).lower(),
                    "shader": {
                        "name": self._shader_name(refl, shader_str),
                        "entry": entry,
                    },
                    "bind": bind,
                    "cbufs": cbufs,
                    "code": self._shader_snippet(controller, pipe, stage_enum, refl),
                },
                "err": None,
                "meta": {"cap": "active", "truncated": False},
            }

        self.ctx.Replay().BlockInvoke(collect)
        return result

    def get_shader_disasm(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        stage_name = params.get("stage")
        if eid is None or not stage_name:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "eid and stage are required"},
                "meta": {"cap": "active", "truncated": False},
            }

        offset = max(0, int(params.get("offset", 0) or 0))
        max_lines = int(params.get("max_lines", 400) or 400)
        if max_lines <= 0:
            max_lines = 400

        eid = int(eid)
        stage_name = str(stage_name).lower()
        stage_enum = self._stage_enum_from_name(stage_name)
        if stage_enum is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_stage", "msg": "Unsupported stage"},
                "meta": {"cap": "active", "truncated": False},
            }

        result = None

        def collect(controller):
            nonlocal result
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()
            shader = pipe.GetShader(stage_enum)
            shader_str = str(shader)
            if not shader_str or "Null" in shader_str or shader_str == "ResourceId::0":
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "no_shader", "msg": "No shader bound for stage"},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            entry = pipe.GetShaderEntryPoint(stage_enum)
            refl = pipe.GetShaderReflection(stage_enum)
            disasm = self._shader_disasm(controller, pipe, stage_enum, refl)
            if disasm.get("error"):
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "disasm_failed", "msg": disasm["error"]},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            all_lines = disasm.get("text", "").splitlines()
            window = all_lines[offset : offset + max_lines]
            line_count = int(disasm.get("line_count", len(all_lines)) or 0)

            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": eid,
                    "stage": stage_name,
                    "shader": {
                        "name": self._shader_name(refl, shader_str),
                        "entry": entry,
                    },
                    "target": disasm.get("target"),
                    "line_count": line_count,
                    "offset": offset,
                    "returned": len(window),
                    "truncated": offset + len(window) < line_count,
                    "text": "\n".join(window),
                },
                "err": None,
                "meta": {"cap": "active", "truncated": offset + len(window) < line_count},
            }

        self.ctx.Replay().BlockInvoke(collect)
        return result
