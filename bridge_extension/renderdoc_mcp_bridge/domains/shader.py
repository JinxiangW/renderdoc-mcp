"""Shader inspection services."""

import renderdoc as rd

from .pipeline import ShaderSupportMixin


class ShaderServiceMixin(ShaderSupportMixin):
    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _enum_tail(value):
        try:
            text = str(value)
            return text.split(".")[-1] if text else text
        except Exception:
            return None

    def _var_type_summary(self, var_type):
        if var_type is None:
            return None
        try:
            desc = getattr(var_type, "descriptor", None)
            if desc is not None:
                rows = self._safe_int(getattr(desc, "rows", None))
                cols = self._safe_int(getattr(desc, "cols", None))
                elements = self._safe_int(getattr(desc, "elements", None))
                var_class = self._enum_tail(getattr(desc, "varClass", None))
                var_type_name = self._enum_tail(getattr(desc, "type", None))
                summary = {
                    "class": var_class,
                    "type": var_type_name,
                    "rows": rows,
                    "cols": cols,
                }
                if elements and elements > 1:
                    summary["elements"] = elements
                return summary
        except Exception as exc:
            self._warn_swallow("shader.var_type_summary", exc)
        return None

    def _constant_buffer_summary(self, block, slot, max_vars=24):
        item = {
            "slot": slot,
            "name": getattr(block, "name", "") or "",
            "vars": 0,
            "size": self._safe_int(getattr(block, "byteSize", None)),
            "variables": [],
            "truncated": False,
        }
        try:
            variables = list(getattr(block, "variables", []) or [])
        except Exception as exc:
            self._warn_swallow("shader.constant_buffer_summary.variables", exc)
            variables = []
        item["vars"] = len(variables)
        if len(variables) > max_vars:
            item["truncated"] = True
        for var in variables[:max_vars]:
            info = {
                "name": getattr(var, "name", "") or "",
                "offset": self._safe_int(getattr(var, "byteOffset", None)),
                "size": self._safe_int(getattr(var, "byteSize", None)),
            }
            type_summary = self._var_type_summary(getattr(var, "type", None))
            if type_summary is not None:
                info["type"] = type_summary
            item["variables"].append(info)
        return item

    def _signature_items(self, items, kind):
        out = []
        try:
            for item in items or []:
                entry = {
                    "name": getattr(item, "semanticIdxName", "") or getattr(item, "varName", "") or "",
                    "index": self._safe_int(getattr(item, "semanticIndex", None)),
                    "reg": self._safe_int(getattr(item, "regIndex", None)),
                    "comp_count": self._safe_int(getattr(item, "compCount", None)),
                }
                sys_value = self._enum_tail(getattr(item, "systemValue", None))
                if sys_value and sys_value != "Undefined":
                    entry["system_value"] = sys_value
                var_type = self._enum_tail(getattr(item, "varType", None))
                if var_type:
                    entry["type"] = var_type
                if kind == "output":
                    entry["mask"] = self._safe_int(getattr(item, "regChannelMask", None))
                out.append(entry)
        except Exception as exc:
            self._warn_swallow("shader.signature_items", exc)
        return out

    def _binding_name_map(self, items):
        mapping = {}
        try:
            for item in items or []:
                slot = getattr(item, "fixedBindNumber", None)
                if slot is None:
                    slot = getattr(item, "bindPoint", None)
                if slot is None:
                    continue
                mapping[int(slot)] = getattr(item, "name", "") or ""
        except Exception as exc:
            self._warn_swallow("shader.binding_name_map", exc)
        return mapping

    @staticmethod
    def _binding_slot(item):
        try:
            access = getattr(item, "access", None)
            if access is not None and getattr(access, "index", None) is not None:
                return int(access.index)
        except Exception:
            pass
        try:
            return int(getattr(item, "fixedBindNumber", -1))
        except Exception:
            return -1

    @staticmethod
    def _binding_resource_id(item):
        try:
            desc = getattr(item, "descriptor", None)
            if desc is not None:
                rid = getattr(desc, "resource", None)
                rid_str = str(rid)
                if rid_str and "Null" not in rid_str and rid_str != "ResourceId::0":
                    return rid
        except Exception:
            pass
        return None

    def _binding_resource_info(self, rid):
        if rid is None:
            return None
        rid_str = str(rid)
        return {
            "rid": rid_str,
            "name": self.ctx.GetResourceName(rid),
            "meta": self._resource_meta(rid),
        }

    def _collect_shader_bindings(self, pipe, stage_enum, refl):
        bindings = {
            "srv": [],
            "uav": [],
            "cbv": [],
            "smp": [],
        }

        srv_names = self._binding_name_map(getattr(refl, "readOnlyResources", None))
        uav_names = self._binding_name_map(getattr(refl, "readWriteResources", None))
        cbv_names = self._binding_name_map(getattr(refl, "constantBlocks", None))
        smp_names = self._binding_name_map(getattr(refl, "samplers", None))

        try:
            for srv in pipe.GetReadOnlyResources(stage_enum, False):
                slot = self._binding_slot(srv)
                rid = self._binding_resource_id(srv)
                info = {
                    "slot": slot,
                    "name": srv_names.get(slot, ""),
                }
                resource_info = self._binding_resource_info(rid)
                if resource_info is not None:
                    info.update(resource_info)
                bindings["srv"].append(info)
        except Exception as exc:
            self._warn_swallow("shader.collect_bindings.srv", exc)

        try:
            for uav in pipe.GetReadWriteResources(stage_enum, False):
                slot = self._binding_slot(uav)
                rid = self._binding_resource_id(uav)
                info = {
                    "slot": slot,
                    "name": uav_names.get(slot, ""),
                }
                resource_info = self._binding_resource_info(rid)
                if resource_info is not None:
                    info.update(resource_info)
                bindings["uav"].append(info)
        except Exception as exc:
            self._warn_swallow("shader.collect_bindings.uav", exc)

        try:
            for cbv in pipe.GetConstantBlocks(stage_enum, False):
                slot = self._binding_slot(cbv)
                rid = self._binding_resource_id(cbv)
                info = {
                    "slot": slot,
                    "name": cbv_names.get(slot, ""),
                }
                resource_info = self._binding_resource_info(rid)
                if resource_info is not None:
                    info.update(resource_info)
                bindings["cbv"].append(info)
        except Exception as exc:
            self._warn_swallow("shader.collect_bindings.cbv", exc)

        try:
            for smp in pipe.GetSamplers(stage_enum, False):
                slot = self._binding_slot(smp)
                bindings["smp"].append(
                    {
                        "slot": slot,
                        "name": smp_names.get(slot, ""),
                    }
                )
        except Exception as exc:
            self._warn_swallow("shader.collect_bindings.smp", exc)

        for key in bindings:
            try:
                bindings[key].sort(key=lambda item: int(item.get("slot", -1)))
            except Exception:
                pass

        return bindings

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
                blocks = list(refl.constantBlocks)
            except Exception:
                blocks = []
            for slot, block in enumerate(blocks):
                cbufs.append(self._constant_buffer_summary(block, slot))

            sig = {
                "inputs": self._signature_items(getattr(refl, "inputSignature", None), "input"),
                "outputs": self._signature_items(getattr(refl, "outputSignature", None), "output"),
            }

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
                    "bindings": self._collect_shader_bindings(pipe, stage_enum, refl),
                    "cbufs": cbufs,
                    "sig": sig,
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
                    "line_start": offset + 1 if line_count else 0,
                    "line_end": offset + len(window),
                    "returned": len(window),
                    "truncated": offset + len(window) < line_count,
                    "lines": [
                        {"line": offset + idx + 1, "text": line}
                        for idx, line in enumerate(window)
                    ],
                    "text": "\n".join(window),
                },
                "err": None,
                "meta": {"cap": "active", "truncated": offset + len(window) < line_count},
            }

        self.ctx.Replay().BlockInvoke(collect)
        return result
