"""Pipeline-state services and shader helpers."""

import renderdoc as rd


class ShaderSupportMixin:
    @staticmethod
    def _stage_enum_from_name(stage_name):
        stage_map = {
            "vs": rd.ShaderStage.Vertex,
            "hs": rd.ShaderStage.Hull,
            "ds": rd.ShaderStage.Domain,
            "gs": rd.ShaderStage.Geometry,
            "ps": rd.ShaderStage.Pixel,
            "cs": rd.ShaderStage.Compute,
        }
        return stage_map.get(str(stage_name).lower())

    @staticmethod
    def _binding_stages():
        return [
            ("VS", rd.ShaderStage.Vertex),
            ("HS", rd.ShaderStage.Hull),
            ("DS", rd.ShaderStage.Domain),
            ("GS", rd.ShaderStage.Geometry),
            ("PS", rd.ShaderStage.Pixel),
            ("CS", rd.ShaderStage.Compute),
        ]

    @staticmethod
    def _shader_name(reflection, fallback):
        try:
            if reflection:
                if reflection.debugInfo.entrySourceName:
                    return reflection.debugInfo.entrySourceName
                if reflection.entryPoint:
                    return reflection.entryPoint
        except Exception:
            pass
        return fallback

    @staticmethod
    def _safe_len(fn):
        try:
            return len(fn())
        except Exception:
            return 0

    def _shader_snippet(self, controller, pipe, stage_enum, reflection):
        disasm = self._shader_disasm(controller, pipe, stage_enum, reflection)
        if not disasm.get("text"):
            return disasm
        lines = disasm["text"].splitlines()
        return {
            "target": disasm.get("target"),
            "text": "\n".join(lines[:24]),
            "truncated": disasm.get("line_count", len(lines)) > 24,
            "error": disasm.get("error"),
        }

    def _shader_disasm(self, controller, pipe, stage_enum, reflection):
        try:
            targets = controller.GetDisassemblyTargets(True)
            if not targets:
                return {
                    "target": None,
                    "text": None,
                    "line_count": 0,
                    "error": "No disassembly targets available",
                }

            target = targets[0]
            try:
                pipe_obj = pipe.GetGraphicsPipelineObject()
            except Exception:
                pipe_obj = None
            try:
                if stage_enum == rd.ShaderStage.Compute:
                    pipe_obj = pipe.GetComputePipelineObject()
            except Exception:
                pass

            refl_obj = None
            try:
                refl_obj = reflection.reflection
            except Exception:
                refl_obj = reflection

            disasm = controller.DisassembleShader(pipe_obj, refl_obj, target)
            lines = [line for line in disasm.splitlines() if line.strip()]
            return {
                "target": target,
                "text": "\n".join(lines),
                "line_count": len(lines),
                "error": None,
            }
        except Exception as exc:
            return {
                "target": None,
                "text": None,
                "line_count": 0,
                "error": str(exc),
            }


class PipelineStateServiceMixin(ShaderSupportMixin):
    def inspect_pipeline_state(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        if eid is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_event_id", "msg": "eid is required"},
                "meta": {"cap": "active", "truncated": False},
            }

        eid = int(eid)
        result = {
            "eid": eid,
            "api": str(self.ctx.APIProps().pipelineType),
            "ia": {},
            "sh": {},
            "res": {
                "srv": 0,
                "uav": 0,
                "cbv": 0,
                "smp": 0,
                "rt": 0,
                "ds": 0,
            },
        }
        action = self.ctx.GetAction(eid)
        action_type = self._action_type(action) if action is not None else "Action"
        include_compute = action_type == "Dispatch"
        include_graphics = action_type != "Dispatch"

        def collect(controller):
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()

            try:
                ia = pipe.GetIAState()
                if ia:
                    topo = str(getattr(ia, "topology", ""))
                    if topo:
                        result["ia"] = {"topo": topo}
            except Exception as exc:
                self._warn_swallow("pipeline.inspect.ia_state", exc)

            stage_names = [
                ("vs", rd.ShaderStage.Vertex),
                ("hs", rd.ShaderStage.Hull),
                ("ds", rd.ShaderStage.Domain),
                ("gs", rd.ShaderStage.Geometry),
                ("ps", rd.ShaderStage.Pixel),
                ("cs", rd.ShaderStage.Compute),
            ]

            for short, stage_enum in stage_names:
                if short == "cs" and not include_compute:
                    continue
                if short != "cs" and not include_graphics:
                    continue
                try:
                    shader = pipe.GetShader(stage_enum)
                except Exception:
                    continue
                try:
                    shader_str = str(shader)
                    if shader_str and "Null" not in shader_str and shader_str != "ResourceId::0":
                        entry = pipe.GetShaderEntryPoint(stage_enum)
                        refl = pipe.GetShaderReflection(stage_enum)
                        result["sh"][short] = {
                            "name": self._shader_name(refl, shader_str),
                            "entry": entry,
                        }

                        try:
                            result["res"]["srv"] += len(pipe.GetReadOnlyResources(stage_enum, False))
                        except Exception as exc:
                            self._warn_swallow("pipeline.inspect.read_only_resources", exc)
                        try:
                            result["res"]["uav"] += len(pipe.GetReadWriteResources(stage_enum, False))
                        except Exception as exc:
                            self._warn_swallow("pipeline.inspect.read_write_resources", exc)
                        try:
                            result["res"]["cbv"] += len(pipe.GetConstantBlocks(stage_enum, False))
                        except Exception as exc:
                            self._warn_swallow("pipeline.inspect.constant_blocks", exc)
                        try:
                            result["res"]["smp"] += len(pipe.GetSamplers(stage_enum, False))
                        except Exception as exc:
                            self._warn_swallow("pipeline.inspect.samplers", exc)
                except Exception:
                    continue

            try:
                om = pipe.GetOutputMerger()
                if om:
                    try:
                        result["res"]["rt"] = len(
                            [rt for rt in om.renderTargets if str(rt.resourceId) != "ResourceId::Null"]
                        )
                    except Exception as exc:
                        self._warn_swallow("pipeline.inspect.output_merger.render_targets", exc)
                    try:
                        if str(om.depthTarget.resourceId) != "ResourceId::Null":
                            result["res"]["ds"] = 1
                    except Exception as exc:
                        self._warn_swallow("pipeline.inspect.output_merger.depth_target", exc)
            except Exception as exc:
                self._warn_swallow("pipeline.inspect.output_merger", exc)

        self.ctx.Replay().BlockInvoke(collect)

        return {
            "ok": True,
            "mode": "summary",
            "data": result,
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }
