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
        try:
            rid = getattr(item, "resourceId", None)
            rid_str = str(rid)
            if rid_str and "Null" not in rid_str and rid_str != "ResourceId::0":
                return rid
        except Exception:
            pass
        return None

    def _binding_descriptor_summary(self, item, rid=None):
        summary = {}
        try:
            desc = getattr(item, "descriptor", None)
            if desc is not None:
                if rid is None:
                    rid = getattr(desc, "resource", None)
                summary["byteOffset"] = self._safe_int(getattr(desc, "byteOffset", None))
                summary["byteSize"] = self._safe_int(getattr(desc, "byteSize", None))
                summary["descriptorType"] = self._enum_tail(getattr(desc, "type", None))
                summary["elementByteSize"] = self._safe_int(getattr(desc, "elementByteSize", None))
                summary["bufferStructCount"] = self._safe_int(getattr(desc, "bufferStructCount", None))
        except Exception as exc:
            self._warn_swallow("shader.binding_descriptor_summary.descriptor", exc)

        try:
            if "byteOffset" not in summary:
                summary["byteOffset"] = self._safe_int(getattr(item, "byteOffset", None))
            if "byteSize" not in summary:
                summary["byteSize"] = self._safe_int(getattr(item, "byteSize", None))
            inline_data = getattr(item, "inlineData", None)
            if inline_data is not None:
                try:
                    summary["inlineByteSize"] = len(inline_data)
                except Exception:
                    pass
        except Exception as exc:
            self._warn_swallow("shader.binding_descriptor_summary.legacy", exc)

        if rid is not None:
            meta = self._resource_meta(rid)
            if meta and meta.get("kind") == "buf":
                buf_size = int(meta.get("size", 0) or 0)
                offset = summary.get("byteOffset")
                size = summary.get("byteSize")
                if size in (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
                    summary["byteSizeRaw"] = size
                    if offset is not None and buf_size >= int(offset):
                        summary["byteSize"] = buf_size - int(offset)
                summary["bufferSize"] = buf_size

        try:
            access = getattr(item, "access", None)
            if access is not None:
                summary["accessIndex"] = self._safe_int(getattr(access, "index", None))
                summary["arrayElement"] = self._safe_int(getattr(access, "arrayElement", None))
        except Exception:
            pass

        return {key: val for key, val in summary.items() if val is not None}

    def _binding_resource_info(self, rid):
        if rid is None:
            return None
        rid_str = str(rid)
        return {
            "rid": rid_str,
            "name": self.ctx.GetResourceName(rid),
            "meta": self._resource_meta(rid),
        }

    @staticmethod
    def _constant_var_size(var):
        for path in (
            ("byteSize",),
            ("type", "byteSize"),
            ("type", "descriptor", "byteSize"),
        ):
            target = var
            try:
                for name in path:
                    target = getattr(target, name)
                if target is not None:
                    return int(target)
            except Exception:
                pass
        return None

    def _pipeline_object_for_stage(self, pipe, stage_enum):
        try:
            if stage_enum == rd.ShaderStage.Compute:
                return pipe.GetComputePipelineObject()
        except Exception:
            pass
        try:
            return pipe.GetGraphicsPipelineObject()
        except Exception:
            try:
                return rd.ResourceId.Null()
            except Exception:
                return None

    def _block_bind_slot(self, block, binding, fallback_index):
        for obj, attr in ((block, "fixedBindNumber"), (binding, "fixedBindNumber")):
            try:
                value = int(getattr(obj, attr))
                if 0 <= value < 0xFFFFFFFF:
                    return value
            except Exception:
                pass
        try:
            access = getattr(binding, "access", None)
            value = int(getattr(access, "index"))
            if value >= 0:
                return value
        except Exception:
            pass
        return int(fallback_index)

    @staticmethod
    def _sequence_values(values, count):
        out = []
        try:
            for idx in range(min(int(count), len(values))):
                out.append(values[idx])
        except Exception:
            return []
        return out

    def _shader_value_for_type(self, var, count):
        value = getattr(var, "value", None)
        if value is None:
            return None
        type_name = str(self._enum_tail(getattr(var, "type", None)) or "").lower()
        if "double" in type_name or "f64" in type_name:
            vals = self._sequence_values(getattr(value, "f64v", []), count)
        elif "uint" in type_name or type_name.startswith("u"):
            vals = self._sequence_values(getattr(value, "u32v", []), count)
        elif "int" in type_name or "sint" in type_name or type_name.startswith("s"):
            vals = self._sequence_values(getattr(value, "s32v", []), count)
        elif "bool" in type_name:
            vals = [bool(x) for x in self._sequence_values(getattr(value, "u32v", []), count)]
        else:
            vals = self._sequence_values(getattr(value, "f32v", []), count)
        return vals

    def _shader_variable_value(self, var):
        try:
            members = list(getattr(var, "members", []) or [])
        except Exception:
            members = []
        if members:
            return [self._shader_variable_record(member, None, idx) for idx, member in enumerate(members)]

        rows = self._safe_int(getattr(var, "rows", None)) or 1
        cols = self._safe_int(getattr(var, "columns", None)) or 1
        count = max(1, rows * cols)
        vals = self._shader_value_for_type(var, count)
        if vals is None:
            return None
        if rows > 1 and cols > 1:
            return [vals[idx * cols : (idx + 1) * cols] for idx in range(rows)]
        if count == 1:
            return vals[0] if vals else None
        return vals

    def _shader_variable_record(self, value_var, meta_var, index):
        name = getattr(value_var, "name", "") or ""
        if not name and meta_var is not None:
            name = getattr(meta_var, "name", "") or ""
        if not name:
            name = "v{}".format(index)

        record = {
            "name": name,
            "offset": self._safe_int(getattr(meta_var, "byteOffset", None)) if meta_var is not None else None,
            "size": self._constant_var_size(meta_var) if meta_var is not None else None,
            "rows": self._safe_int(getattr(value_var, "rows", None)),
            "columns": self._safe_int(getattr(value_var, "columns", None)),
            "value": self._shader_variable_value(value_var),
        }

        type_summary = None
        if meta_var is not None:
            type_summary = self._var_type_summary(getattr(meta_var, "type", None))
        if type_summary is None:
            type_summary = {
                "type": self._enum_tail(getattr(value_var, "type", None)),
                "rows": record["rows"],
                "cols": record["columns"],
            }
        record["type"] = type_summary
        return {key: val for key, val in record.items() if val is not None}

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
                    info.update(self._binding_descriptor_summary(srv, rid))
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
                    info.update(self._binding_descriptor_summary(uav, rid))
                bindings["uav"].append(info)
        except Exception as exc:
            self._warn_swallow("shader.collect_bindings.uav", exc)

        try:
            for cbv in pipe.GetConstantBlocks(stage_enum, False):
                access_index = self._binding_slot(cbv)
                try:
                    block = list(getattr(refl, "constantBlocks", []) or [])[access_index]
                except Exception:
                    block = None
                slot = self._block_bind_slot(block, cbv, access_index)
                rid = self._binding_resource_id(cbv)
                info = {
                    "slot": slot,
                    "name": getattr(block, "name", "") if block is not None else cbv_names.get(slot, ""),
                }
                resource_info = self._binding_resource_info(rid)
                if resource_info is not None:
                    info.update(resource_info)
                    info.update(self._binding_descriptor_summary(cbv, rid))
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
            for block_index, block in enumerate(blocks):
                slot = self._block_bind_slot(block, None, block_index)
                summary = self._constant_buffer_summary(block, slot)
                summary["block_index"] = block_index
                cbufs.append(summary)

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

    def inspect_cbuffer_values(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        stage_name = params.get("stage")
        slot_filter = params.get("slot")
        if eid is None or not stage_name:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "eid and stage are required"},
                "meta": {"cap": "active", "truncated": False},
            }

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

        slot_filter_int = None
        if slot_filter is not None:
            slot_filter_int = int(slot_filter)

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
            try:
                blocks = list(getattr(refl, "constantBlocks", []) or [])
            except Exception:
                blocks = []
            try:
                bound_blocks = list(pipe.GetConstantBlocks(stage_enum, False) or [])
            except Exception:
                bound_blocks = []

            if not blocks:
                blocks = [None for _ in bound_blocks]

            pipe_obj = self._pipeline_object_for_stage(pipe, stage_enum)
            cbufs = []
            any_truncated = False

            for block_index, block in enumerate(blocks):
                binding = None
                try:
                    binding = pipe.GetConstantBlock(stage_enum, block_index, 0)
                except Exception:
                    if block_index < len(bound_blocks):
                        binding = bound_blocks[block_index]

                slot = self._block_bind_slot(block, binding, block_index)
                if slot_filter_int is not None and slot_filter_int not in (slot, block_index):
                    continue

                rid = self._binding_resource_id(binding)
                range_info = self._binding_descriptor_summary(binding, rid)
                block_size = self._safe_int(getattr(block, "byteSize", None)) if block is not None else None
                byte_offset = int(range_info.get("byteOffset", 0) or 0)
                byte_size = range_info.get("byteSize")
                if byte_size in (None, 0):
                    byte_size = block_size or 0
                byte_size = int(byte_size or 0)

                values = []
                value_error = None
                if rid is not None and not self._is_null_rid(rid):
                    try:
                        raw_vars = list(
                            controller.GetCBufferVariableContents(
                                pipe_obj,
                                shader,
                                stage_enum,
                                entry,
                                block_index,
                                rid,
                                byte_offset,
                                byte_size,
                            )
                            or []
                        )
                    except Exception as exc:
                        raw_vars = []
                        value_error = str(exc)

                    try:
                        meta_vars = list(getattr(block, "variables", []) or []) if block is not None else []
                    except Exception:
                        meta_vars = []

                    for idx, value_var in enumerate(raw_vars):
                        meta_var = meta_vars[idx] if idx < len(meta_vars) else None
                        record = self._shader_variable_record(value_var, meta_var, idx)
                        if record.get("name") == "v{}".format(idx):
                            record["name"] = "cb{}_v{}".format(slot, idx)
                        values.append(record)
                else:
                    raw_vars = []

                raw = None
                if rid is not None and not self._is_null_rid(rid) and (not values or params.get("raw")):
                    read_len = block_size or byte_size or 0
                    if read_len > 0:
                        capped = min(read_len, self._MAX_BUFFER_READ_BYTES)
                        try:
                            data = self._byte_list(controller.GetBufferData(rid, byte_offset, capped))
                            raw = self._decode_raw_rows(data, byte_offset)
                            raw["read_length"] = len(data)
                            raw["requested_length"] = read_len
                            raw["truncated"] = bool(raw.get("truncated")) or read_len > len(data)
                            any_truncated = any_truncated or raw["truncated"]
                        except Exception as exc:
                            value_error = value_error or str(exc)

                item = {
                    "name": getattr(block, "name", "") if block is not None else "cb{}".format(slot),
                    "slot": slot,
                    "block_index": block_index,
                    "bound": {
                        "rid": str(rid) if rid is not None else None,
                        "name": self.ctx.GetResourceName(rid) if rid is not None and not self._is_null_rid(rid) else "",
                        "byteOffset": byte_offset,
                        "byteSize": byte_size,
                        "blockByteSize": block_size,
                    },
                    "variables": values,
                    "variables_count": len(values),
                }
                item["bound"].update(range_info)
                if raw is not None:
                    item["raw"] = raw
                if value_error is not None:
                    item["value_error"] = value_error
                cbufs.append(item)

            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": eid,
                    "stage": stage_name,
                    "shader": {
                        "name": self._shader_name(refl, shader_str),
                        "entry": entry,
                        "sid": shader_str,
                    },
                    "cbufs": cbufs,
                },
                "err": None,
                "meta": {"cap": "active", "truncated": any_truncated},
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
