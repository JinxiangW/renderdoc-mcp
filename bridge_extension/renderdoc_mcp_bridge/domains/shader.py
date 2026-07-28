"""Shader inspection services."""

import hashlib
import os
import shlex
import shutil
import subprocess
import tempfile

import renderdoc as rd

from .pipeline import ShaderSupportMixin


class ShaderServiceMixin(ShaderSupportMixin):
    def _shader_replacement_maps(self):
        if not hasattr(self, "_shader_replacements"):
            self._shader_replacements = {}
            self._replacement_to_original = {}
        return self._shader_replacements, self._replacement_to_original

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _safe_text(value):
        try:
            if value is None:
                return None
            text = str(value)
            return text if text else None
        except Exception:
            return None

    @staticmethod
    def _safe_bool(value):
        try:
            if value is None:
                return None
            return bool(value)
        except Exception:
            return None

    @classmethod
    def _safe_source_filename(cls, value):
        text = cls._safe_text(value)
        if text is None or isinstance(value, bool):
            return None

        number = cls._safe_int(value)
        if number is not None and number < 0 and text == str(number):
            return None

        return text

    @classmethod
    def _coerce_source_text(cls, value):
        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, (bytes, bytearray)):
            try:
                text = bytes(value).decode("utf-8-sig")
            except Exception:
                text = bytes(value).decode("utf-8", errors="replace")
        else:
            text = str(value)

        if not text:
            return None

        stripped = text.strip()
        if stripped in {"False", "True", "None"}:
            return None

        number = cls._safe_int(stripped)
        if number is not None and number < 0 and stripped == str(number):
            return None

        return text

    @staticmethod
    def _code_window(lines, offset, max_lines):
        window = lines[offset : offset + max_lines]
        line_count = len(lines)
        return {
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
        }

    @staticmethod
    def _enum_tail(value):
        try:
            text = str(value)
            return text.split(".")[-1] if text else text
        except Exception:
            return None

    @staticmethod
    def _shader_encoding_name(value):
        names = {
            0: "Unknown",
            1: "DXBC",
            2: "GLSL",
            3: "SPIRV",
            4: "SPIRVAsm",
            5: "HLSL",
            6: "DXIL",
            7: "OpenGLSPIRV",
            8: "OpenGLSPIRVAsm",
            9: "Slang",
        }
        try:
            return names.get(int(value), str(value).split(".")[-1])
        except Exception:
            text = str(value)
            return text.split(".")[-1] if text else text

    @staticmethod
    def _shader_encoding_from_name(value):
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        normalised = text.lower().replace("-", "").replace("_", "")
        mapping = {
            "hlsl": "HLSL",
            "dxbc": "DXBC",
            "dxil": "DXIL",
            "glsl": "GLSL",
            "spirv": "SPIRV",
            "spv": "SPIRV",
            "slang": "Slang",
        }
        attr = mapping.get(normalised, text)
        try:
            return getattr(rd.ShaderEncoding, attr)
        except Exception:
            return None

    @staticmethod
    def _shader_encoding_int(value):
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _trim_process_output(value, limit=4000):
        if value is None:
            return ""
        if isinstance(value, (bytes, bytearray)):
            text = bytes(value).decode("utf-8", errors="replace")
        else:
            text = str(value)
        if len(text) > limit:
            return text[:limit] + "\n...<truncated>"
        return text

    @staticmethod
    def _replace_processor_placeholders(token, input_file, output_file):
        return (
            str(token)
            .replace("{input_file}", input_file)
            .replace("{output_file}", output_file)
        )

    @classmethod
    def _processor_argv(cls, executable, args, input_file, output_file):
        try:
            tokens = shlex.split(str(args or ""), posix=True)
        except Exception:
            tokens = str(args or "").split()

        argv = [str(executable)]
        for token in tokens:
            argv.append(cls._replace_processor_placeholders(token, input_file, output_file))
        return argv

    @staticmethod
    def _processor_uses_output_file(args):
        return "{output_file}" in str(args or "")

    def _shader_processors(self):
        try:
            processors = getattr(self.ctx.Config(), "ShaderProcessors", [])
        except Exception:
            processors = []

        out = []
        for tool in processors or []:
            in_enc = self._shader_encoding_int(getattr(tool, "input", None))
            out_enc = self._shader_encoding_int(getattr(tool, "output", None))
            executable = self._safe_text(getattr(tool, "executable", None))
            if in_enc is None or out_enc is None or not executable:
                continue
            out.append(
                {
                    "name": self._safe_text(getattr(tool, "name", None)) or executable,
                    "executable": executable,
                    "args": self._safe_text(getattr(tool, "args", None)) or "",
                    "input": in_enc,
                    "output": out_enc,
                }
            )
        return out

    def _select_hlsl_decompiler(self, input_encoding, tool_name=None):
        input_int = self._shader_encoding_int(input_encoding)
        hlsl_int = self._shader_encoding_int(self._shader_encoding_from_name("hlsl"))
        if input_int is None or hlsl_int is None:
            return None

        candidates = [
            tool
            for tool in self._shader_processors()
            if tool.get("input") == input_int and tool.get("output") == hlsl_int
        ]
        if not candidates:
            return None

        query = str(tool_name or "").strip().lower()
        if query:
            for tool in candidates:
                if str(tool.get("name", "")).lower() == query:
                    return tool
            for tool in candidates:
                if query in str(tool.get("name", "")).lower():
                    return tool
            return None

        for tool in candidates:
            name = str(tool.get("name", "")).lower()
            executable = str(tool.get("executable", "")).lower()
            if "ruri" in name or "ruri.shaderdecompiler" in executable:
                return tool

        return candidates[0]

    @staticmethod
    def _write_atomic_bytes(path, data):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix=os.path.basename(path) + ".",
            suffix=".tmp",
            dir=parent or None,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(temp_path, path)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _append_compile_flag(flags, name, value):
        flag = rd.ShaderCompileFlag()
        flag.name = str(name)
        flag.value = str(value)
        flags.flags.append(flag)

    def _copy_compile_flags(self, source_flags):
        flags = rd.ShaderCompileFlags()
        try:
            for source_flag in getattr(source_flags, "flags", []) or []:
                self._append_compile_flag(
                    flags,
                    getattr(source_flag, "name", ""),
                    getattr(source_flag, "value", ""),
                )
        except Exception as exc:
            self._warn_swallow("shader.copy_compile_flags", exc)
        return flags

    def _compile_flags_for_edit(self, params, reflection):
        base_flags = None
        if not bool(params.get("fresh_flags")) and reflection is not None:
            try:
                base_flags = getattr(getattr(reflection, "debugInfo", None), "compileFlags", None)
            except Exception as exc:
                self._warn_swallow("shader.compile_flags.debug_info", exc)

        flags = self._copy_compile_flags(base_flags) if base_flags is not None else rd.ShaderCompileFlags()

        for item in params.get("flags", []) or []:
            if isinstance(item, dict):
                name = item.get("name")
                value = item.get("value", "")
                if name:
                    self._append_compile_flag(flags, name, value)

        cmdline = params.get("compile_cmdline")
        if cmdline is None:
            cmdline = params.get("cmdline")
        profile = params.get("profile")
        if profile and (cmdline is None or "/T" not in str(cmdline)):
            cmdline = ("/T {}".format(profile) if cmdline is None else "/T {} {}".format(profile, cmdline))

        if cmdline is not None:
            replaced = False
            try:
                for flag in flags.flags:
                    if str(getattr(flag, "name", "")) == "@cmdline":
                        flag.value = str(cmdline)
                        replaced = True
                        break
            except Exception as exc:
                self._warn_swallow("shader.compile_flags.replace_cmdline", exc)
            if not replaced:
                self._append_compile_flag(flags, "@cmdline", cmdline)

        return flags

    @staticmethod
    def _read_shader_source_from_params(params):
        if params.get("source") is not None:
            return str(params.get("source")), None

        source_path = params.get("source_path") or params.get("path")
        if not source_path:
            return None, "source or source_path is required"

        source_path = os.path.abspath(str(source_path))
        try:
            with open(source_path, "r", encoding="utf-8-sig") as handle:
                return handle.read(), None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def _encoding_names(encodings):
        names = []
        for encoding in encodings or []:
            names.append(ShaderServiceMixin._shader_encoding_name(encoding))
        return names

    def _shader_debug_summary(self, reflection):
        debug_info = getattr(reflection, "debugInfo", None) if reflection is not None else None
        if debug_info is None:
            return {
                "available": False,
                "has_source": False,
                "file_count": 0,
            }

        files = self._source_files(debug_info)
        summary = {
            "available": True,
            "debuggable": self._safe_bool(getattr(debug_info, "debuggable", None)),
            "status": self._enum_tail(getattr(debug_info, "debugStatus", None)),
            "compiler": self._safe_text(getattr(debug_info, "compiler", None)),
            "encoding": self._enum_tail(getattr(debug_info, "encoding", None)),
            "base_file": self._safe_source_filename(getattr(debug_info, "editBaseFile", None)),
            "file_count": len(files),
            "has_source": any(file_info.get("line_count", 0) > 0 for file_info in files),
        }
        return summary

    def _source_files(self, debug_info):
        files = []
        try:
            for idx, source_file in enumerate(getattr(debug_info, "files", []) or []):
                filename = self._safe_source_filename(getattr(source_file, "filename", None)) or "<source>"
                text = self._coerce_source_text(getattr(source_file, "contents", None))
                if text is None:
                    continue
                files.append(
                    {
                        "index": idx,
                        "filename": filename,
                        "text": text,
                        "line_count": len(text.splitlines()),
                    }
                )
        except Exception as exc:
            self._warn_swallow("shader.source_files", exc)

        if any(file_info.get("line_count", 0) > 0 for file_info in files):
            return files

        try:
            source_blob = getattr(debug_info, "sourceDebugInformation", None)
            source_text = self._coerce_source_text(source_blob) or ""
        except Exception as exc:
            self._warn_swallow("shader.source_debug_information", exc)
            source_text = ""

        if source_text:
            files = [
                {
                    "index": 0,
                    "filename": self._safe_source_filename(getattr(debug_info, "editBaseFile", None)) or "<source>",
                    "text": source_text,
                    "line_count": len(source_text.splitlines()),
                }
            ]

        return files

    @staticmethod
    def _select_source_file(files, file_query, file_index, preferred_filename):
        if not files:
            return None

        query = str(file_query or "").strip().lower()
        if query:
            for file_info in files:
                filename = str(file_info.get("filename", ""))
                if filename.lower() == query:
                    return file_info
            for file_info in files:
                filename = str(file_info.get("filename", ""))
                if query in filename.lower():
                    return file_info

        preferred = str(preferred_filename or "").strip().lower()
        if preferred:
            for file_info in files:
                filename = str(file_info.get("filename", ""))
                if filename.lower() == preferred:
                    return file_info

        idx = max(0, int(file_index or 0))
        if idx >= len(files):
            idx = len(files) - 1
        return files[idx]

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
                    "shader_id": shader_str,
                    "shader": self._shader_info(refl, shader, entry),
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

    def get_target_shader_encodings(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        result = None

        def collect(controller):
            nonlocal result
            try:
                encodings = list(controller.GetTargetShaderEncodings() or [])
            except Exception as exc:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "query_failed", "msg": str(exc)},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "api": str(self.ctx.APIProps().pipelineType),
                    "encodings": self._encoding_names(encodings),
                },
                "err": None,
                "meta": {"cap": "active", "truncated": False},
            }

        self.ctx.Replay().BlockInvoke(collect)
        return result

    def apply_shader_edit(self, params):
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

        source_text, source_error = self._read_shader_source_from_params(params)
        if source_text is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_source", "msg": source_error},
                "meta": {"cap": "active", "truncated": False},
            }

        source_encoding = self._shader_encoding_from_name(params.get("source_encoding") or "hlsl")
        if source_encoding is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_encoding", "msg": "Unsupported source_encoding"},
                "meta": {"cap": "active", "truncated": False},
            }

        result = None
        old_local_replacement = None

        def collect(controller):
            nonlocal result, old_local_replacement
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

            target_encodings = list(controller.GetTargetShaderEncodings() or [])
            if int(source_encoding) not in [int(item) for item in target_encodings]:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": {
                        "api": str(self.ctx.APIProps().pipelineType),
                        "supported_encodings": self._encoding_names(target_encodings),
                    },
                    "err": {
                        "code": "unsupported_encoding",
                        "msg": "{} is not a target shader encoding for this capture API".format(
                            self._shader_encoding_name(source_encoding)
                        ),
                    },
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            entry = params.get("entry")
            if entry is None:
                entry = params.get("entry_point")
            if entry is None:
                entry = pipe.GetShaderEntryPoint(stage_enum)

            refl = pipe.GetShaderReflection(stage_enum)
            flags = self._compile_flags_for_edit(params, refl)
            shader_bytes = source_text.encode("utf-8")

            try:
                new_shader, errors = controller.BuildTargetShader(
                    str(entry),
                    source_encoding,
                    shader_bytes,
                    flags,
                    stage_enum,
                )
            except Exception as exc:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "build_exception", "msg": str(exc)},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            if self._is_null_rid(new_shader):
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": {
                        "eid": eid,
                        "stage": stage_name,
                        "original_shader": shader_str,
                        "entry": str(entry),
                        "source_encoding": self._shader_encoding_name(source_encoding),
                        "errors": str(errors or ""),
                    },
                    "err": {"code": "build_failed", "msg": str(errors or "Shader compilation failed")},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            replacements, replacement_to_original = self._shader_replacement_maps()
            old_local_replacement = replacements.get(shader_str)

            controller.ReplaceResource(shader, new_shader)
            controller.SetFrameEvent(eid, True)

            replacements[shader_str] = new_shader
            replacement_to_original[str(new_shader)] = shader
            if old_local_replacement is not None:
                replacement_to_original.pop(str(old_local_replacement), None)

            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": eid,
                    "stage": stage_name,
                    "api": str(self.ctx.APIProps().pipelineType),
                    "shader": self._shader_info(refl, shader, str(entry)),
                    "source_encoding": self._shader_encoding_name(source_encoding),
                    "replacement_shader": str(new_shader),
                    "errors": str(errors or ""),
                },
                "err": None,
                "meta": {"cap": "active", "truncated": False},
            }

        self.ctx.Replay().BlockInvoke(collect)

        if result and result.get("ok"):
            if old_local_replacement is not None:
                def free_old(controller):
                    try:
                        controller.FreeTargetResource(old_local_replacement)
                    except Exception as exc:
                        self._warn_swallow("shader.apply_edit.free_old", exc)

                self.ctx.Replay().BlockInvoke(free_old)

        return result

    def revert_shader_edit(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        stage_name = params.get("stage")
        shader_id = params.get("shader_id")
        if shader_id is None and (eid is None or not stage_name):
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "shader_id or eid and stage are required"},
                "meta": {"cap": "active", "truncated": False},
            }

        stage_enum = self._stage_enum_from_name(stage_name) if stage_name else None
        if stage_name and stage_enum is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_stage", "msg": "Unsupported stage"},
                "meta": {"cap": "active", "truncated": False},
            }

        result = None
        freed_replacement = None

        def collect(controller):
            nonlocal result, freed_replacement
            replacements, replacement_to_original = self._shader_replacement_maps()
            original = None
            original_key = None

            if shader_id is not None:
                key = str(shader_id)
                if key in replacements:
                    original = replacement_to_original.get(str(replacements[key]))
                    original_key = key
            elif eid is not None and stage_enum is not None:
                controller.SetFrameEvent(int(eid), True)
                pipe = controller.GetPipelineState()
                current_shader = pipe.GetShader(stage_enum)
                current_key = str(current_shader)
                if current_key in replacements:
                    original = current_shader
                    original_key = current_key
                elif current_key in replacement_to_original:
                    original = replacement_to_original[current_key]
                    original_key = str(original)

            if original is None or original_key is None:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "replacement_not_found", "msg": "No MCP shader replacement found"},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            replacement = replacements.pop(original_key, None)
            if replacement is not None:
                replacement_to_original.pop(str(replacement), None)

            controller.RemoveReplacement(original)
            if eid is not None:
                controller.SetFrameEvent(int(eid), True)

            freed_replacement = replacement
            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": int(eid) if eid is not None else None,
                    "stage": str(stage_name).lower() if stage_name else None,
                    "shader_id": str(original),
                    "freed_replacement": str(replacement) if replacement is not None else None,
                },
                "err": None,
                "meta": {"cap": "active", "truncated": False},
            }

        self.ctx.Replay().BlockInvoke(collect)

        if result and result.get("ok"):
            if freed_replacement is not None:
                def free_target(controller):
                    try:
                        controller.FreeTargetResource(freed_replacement)
                    except Exception as exc:
                        self._warn_swallow("shader.revert_edit.free_target", exc)

                self.ctx.Replay().BlockInvoke(free_target)

        return result

    def export_shader_raw_bytes(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        stage_name = params.get("stage")
        dest = params.get("dest")
        if eid is None or not stage_name or not dest:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "eid, stage, and dest are required"},
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

        dest = os.path.abspath(str(dest))
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

            refl = pipe.GetShaderReflection(stage_enum)
            try:
                raw = bytes(getattr(refl, "rawBytes", b"") or b"")
            except Exception:
                try:
                    raw = bytearray(getattr(refl, "rawBytes", []) or [])
                    raw = bytes(raw)
                except Exception as exc:
                    result = {
                        "ok": False,
                        "mode": "summary",
                        "data": None,
                        "err": {"code": "raw_bytes_failed", "msg": str(exc)},
                        "meta": {"cap": "active", "truncated": False},
                    }
                    return

            if not raw:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "empty_raw_bytes", "msg": "Shader reflection returned no raw bytes"},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            parent = os.path.dirname(dest)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(dest, "wb") as handle:
                handle.write(raw)

            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": eid,
                    "stage": stage_name,
                    "shader": self._shader_info(refl, shader, pipe.GetShaderEntryPoint(stage_enum)),
                    "encoding": self._enum_tail(getattr(refl, "encoding", None)),
                    "dest": dest,
                    "byte_count": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
                "err": None,
                "meta": {"cap": "active", "truncated": False},
            }

        self.ctx.Replay().BlockInvoke(collect)
        return result

    def export_shader_decompiled_hlsl(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()

        eid = params.get("eid")
        stage_name = params.get("stage")
        dest = params.get("dest")
        if eid is None or not stage_name or not dest:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "missing_args", "msg": "eid, stage, and dest are required"},
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

        dest = os.path.abspath(str(dest))
        overwrite = bool(params.get("overwrite", False))
        if os.path.exists(dest) and not overwrite:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "dest_exists", "msg": "Destination already exists; pass overwrite=true"},
                "meta": {"cap": "active", "truncated": False},
            }

        shader_data = {}
        collect_error = None

        def collect(controller):
            nonlocal shader_data, collect_error
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()
            shader = pipe.GetShader(stage_enum)
            shader_str = str(shader)
            if not shader_str or "Null" in shader_str or shader_str == "ResourceId::0":
                collect_error = {"code": "no_shader", "msg": "No shader bound for stage"}
                return

            refl = pipe.GetShaderReflection(stage_enum)
            try:
                raw = bytes(getattr(refl, "rawBytes", b"") or b"")
            except Exception:
                try:
                    raw = bytearray(getattr(refl, "rawBytes", []) or [])
                    raw = bytes(raw)
                except Exception as exc:
                    collect_error = {"code": "raw_bytes_failed", "msg": str(exc)}
                    return

            if not raw:
                collect_error = {"code": "empty_raw_bytes", "msg": "Shader reflection returned no raw bytes"}
                return

            shader_data = {
                "shader": self._shader_info(refl, shader, pipe.GetShaderEntryPoint(stage_enum)),
                "encoding": getattr(refl, "encoding", None),
                "raw": raw,
            }

        self.ctx.Replay().BlockInvoke(collect)
        if collect_error is not None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": collect_error,
                "meta": {"cap": "active", "truncated": False},
            }

        input_encoding = shader_data.get("encoding")
        processor = self._select_hlsl_decompiler(input_encoding, params.get("processor") or params.get("tool_name"))
        if processor is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {
                    "code": "hlsl_decompiler_not_found",
                    "msg": "No RenderDoc shader processor registered for {} -> HLSL".format(
                        self._shader_encoding_name(input_encoding)
                    ),
                },
                "meta": {"cap": "active", "truncated": False},
            }

        executable = processor.get("executable")
        if not executable or not os.path.exists(executable):
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {
                    "code": "decompiler_executable_not_found",
                    "msg": str(executable or ""),
                },
                "meta": {"cap": "active", "truncated": False},
            }

        try:
            timeout = float(params.get("timeout", 60.0) or 60.0)
        except Exception:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_timeout", "msg": "timeout must be a number"},
                "meta": {"cap": "active", "truncated": False},
            }

        raw = shader_data["raw"]
        temp_dir = tempfile.mkdtemp(prefix="renderdoc_mcp_shader_")
        try:
            input_ext = {
                "DXBC": ".dxbc",
                "DXIL": ".dxil",
                "SPIRV": ".spv",
            }.get(self._shader_encoding_name(input_encoding), ".bin")
            input_path = os.path.join(temp_dir, "shader" + input_ext)
            output_path = os.path.join(temp_dir, "shader.hlsl")
            with open(input_path, "wb") as handle:
                handle.write(raw)

            argv = self._processor_argv(executable, processor.get("args", ""), input_path, output_path)
            try:
                completed = subprocess.run(
                    argv,
                    cwd=os.path.dirname(executable) or None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                return {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {
                        "code": "decompile_timeout",
                        "msg": "Decompiler timed out after {} seconds".format(timeout),
                        "stdout": self._trim_process_output(getattr(exc, "stdout", None)),
                        "stderr": self._trim_process_output(getattr(exc, "stderr", None)),
                    },
                    "meta": {"cap": "active", "truncated": False},
                }
            except Exception as exc:
                return {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "decompile_failed", "msg": str(exc)},
                    "meta": {"cap": "active", "truncated": False},
                }

            if completed.returncode != 0:
                return {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {
                        "code": "decompile_failed",
                        "msg": "Decompiler exited with code {}".format(completed.returncode),
                        "stdout": self._trim_process_output(completed.stdout),
                        "stderr": self._trim_process_output(completed.stderr),
                    },
                    "meta": {"cap": "active", "truncated": False},
                }

            if self._processor_uses_output_file(processor.get("args", "")):
                if not os.path.exists(output_path):
                    return {
                        "ok": False,
                        "mode": "summary",
                        "data": None,
                        "err": {
                            "code": "decompile_output_missing",
                            "msg": "Decompiler did not write the expected output file",
                            "stdout": self._trim_process_output(completed.stdout),
                            "stderr": self._trim_process_output(completed.stderr),
                        },
                        "meta": {"cap": "active", "truncated": False},
                    }
                with open(output_path, "rb") as handle:
                    hlsl = handle.read()
            else:
                hlsl = completed.stdout or b""

            if not hlsl:
                return {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {
                        "code": "empty_decompiled_hlsl",
                        "msg": "Decompiler produced no HLSL output",
                        "stderr": self._trim_process_output(completed.stderr),
                    },
                    "meta": {"cap": "active", "truncated": False},
                }

            try:
                self._write_atomic_bytes(dest, hlsl)
            except Exception as exc:
                return {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "write_failed", "msg": str(exc)},
                    "meta": {"cap": "active", "truncated": False},
                }
        finally:
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass

        text = hlsl.decode("utf-8", errors="replace")
        return {
            "ok": True,
            "mode": "summary",
            "data": {
                "eid": eid,
                "stage": stage_name,
                "shader": shader_data.get("shader"),
                "source_encoding": self._shader_encoding_name(input_encoding),
                "dest": dest,
                "processor": {
                    "name": processor.get("name"),
                    "input": self._shader_encoding_name(processor.get("input")),
                    "output": self._shader_encoding_name(processor.get("output")),
                    "executable": processor.get("executable"),
                },
                "byte_count": len(hlsl),
                "line_count": len(text.splitlines()),
                "sha256": hashlib.sha256(hlsl).hexdigest(),
                "raw_byte_count": len(raw),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            },
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }

    def get_shader_source(self, params):
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
        file_query = params.get("file")
        file_index = int(params.get("file_index", 0) or 0)
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
            debug_info = getattr(refl, "debugInfo", None) if refl is not None else None
            debug_summary = self._shader_debug_summary(refl)
            source_files = self._source_files(debug_info) if debug_info is not None else []

            if not source_files:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {
                        "code": "shader_source_unavailable",
                        "msg": "Shader source/debug information is not available for this shader",
                    },
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            selected = self._select_source_file(
                source_files,
                file_query,
                file_index,
                debug_summary.get("base_file"),
            )
            if selected is None:
                result = {
                    "ok": False,
                    "mode": "summary",
                    "data": None,
                    "err": {"code": "shader_source_not_found", "msg": "Requested shader source file was not found"},
                    "meta": {"cap": "active", "truncated": False},
                }
                return

            code = self._code_window(str(selected.get("text", "")).splitlines(), offset, max_lines)
            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": eid,
                    "stage": stage_name,
                    "shader": self._shader_info(refl, shader, entry),
                    "debug": debug_summary,
                    "files": [
                        {
                            "index": int(file_info.get("index", 0) or 0),
                            "filename": file_info.get("filename"),
                            "line_count": int(file_info.get("line_count", 0) or 0),
                        }
                        for file_info in source_files
                    ],
                    "file": {
                        "index": int(selected.get("index", 0) or 0),
                        "filename": selected.get("filename"),
                        **code,
                    },
                },
                "err": None,
                "meta": {"cap": "active", "truncated": code["truncated"]},
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
                    "shader": self._shader_info(refl, shader, entry),
                    "cbufs": cbufs,
                },
                "err": None,
                "meta": {"cap": "active", "truncated": any_truncated},
            }

        self.ctx.Replay().BlockInvoke(collect)
        return result

    def get_shader_code(self, params):
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
        file_query = params.get("file")
        file_index = int(params.get("file_index", 0) or 0)
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
            debug_info = getattr(refl, "debugInfo", None) if refl is not None else None
            debug_summary = self._shader_debug_summary(refl)
            source_files = self._source_files(debug_info) if debug_info is not None else []

            if source_files:
                selected = self._select_source_file(
                    source_files,
                    file_query,
                    file_index,
                    debug_summary.get("base_file"),
                )
                if selected is not None:
                    code = self._code_window(str(selected.get("text", "")).splitlines(), offset, max_lines)
                    result = {
                        "ok": True,
                        "mode": "summary",
                        "data": {
                            "eid": eid,
                            "stage": stage_name,
                            "kind": "source",
                            "shader": self._shader_info(refl, shader, entry),
                            "debug": debug_summary,
                            "files": [
                                {
                                    "index": int(file_info.get("index", 0) or 0),
                                    "filename": file_info.get("filename"),
                                    "line_count": int(file_info.get("line_count", 0) or 0),
                                }
                                for file_info in source_files
                            ],
                            "file": {
                                "index": int(selected.get("index", 0) or 0),
                                "filename": selected.get("filename"),
                            },
                            "code": code,
                        },
                        "err": None,
                        "meta": {"cap": "active", "truncated": code["truncated"]},
                    }
                    return

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

            code = self._code_window(disasm.get("text", "").splitlines(), offset, max_lines)
            result = {
                "ok": True,
                "mode": "summary",
                "data": {
                    "eid": eid,
                    "stage": stage_name,
                    "kind": "disasm",
                    "shader": self._shader_info(refl, shader, entry),
                    "debug": debug_summary,
                    "target": disasm.get("target"),
                    "code": code,
                },
                "err": None,
                "meta": {"cap": "active", "truncated": code["truncated"]},
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
                    "shader": self._shader_info(refl, shader, entry),
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
