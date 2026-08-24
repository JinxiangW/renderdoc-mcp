"""Mesh inspection and export services."""

import os
import struct

import renderdoc as rd


class _MeshExportError(RuntimeError):
    def __init__(self, code, message):
        RuntimeError.__init__(self, message)
        self.code = code


class MeshServiceMixin:
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

    def inspect_mesh(self, params):
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
        action = self.ctx.GetAction(eid)
        if action is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_event", "msg": "Event not found"},
                "meta": {"cap": "active", "truncated": False},
            }

        result = {
            "eid": eid,
            "topo": "",
            "idx": int(getattr(action, "numIndices", 0) or 0),
            "inst": int(getattr(action, "numInstances", 0) or 0),
            "attrs": [],
            "vbs": [],
            "ib": None,
            "postvs": {},
        }

        def collect(controller):
            controller.SetFrameEvent(eid, True)
            pipe = controller.GetPipelineState()

            try:
                attrs = pipe.GetVertexInputs()
                for attr in attrs:
                    fmt = attr.format
                    fmt_name = "{}{}".format(str(fmt.compType).split(".")[-1], fmt.compCount)
                    item = {
                        "name": attr.name,
                        "fmt": fmt_name,
                    }
                    slot = self._safe_int(getattr(attr, "vertexBuffer", None))
                    if slot is not None:
                        item["vb_slot"] = slot
                    byte_offset = self._safe_int(getattr(attr, "byteOffset", None))
                    if byte_offset is not None:
                        item["offset"] = byte_offset
                    per_instance = getattr(attr, "perInstance", None)
                    if per_instance is not None:
                        item["per_instance"] = bool(per_instance)
                    instance_rate = self._safe_int(getattr(attr, "instanceRate", None))
                    if instance_rate is not None:
                        item["instance_rate"] = instance_rate
                    result["attrs"].append(item)
            except Exception as exc:
                self._warn_swallow("mesh.inspect.vertex_inputs", exc)

            try:
                getter = getattr(pipe, "GetVBuffers", None)
                buffers = getter() if callable(getter) else []
                for idx, vb in enumerate(buffers or []):
                    rid = getattr(vb, "resourceId", None)
                    rid_str = str(rid)
                    if not rid_str or "Null" in rid_str or rid_str == "ResourceId::0":
                        continue
                    entry = {
                        "slot": idx,
                        "rid": rid_str,
                        "name": self.ctx.GetResourceName(rid),
                        "meta": self._resource_meta(rid),
                        "stride": self._safe_int(getattr(vb, "byteStride", None)),
                        "offset": self._safe_int(getattr(vb, "byteOffset", None)),
                    }
                    per_instance = getattr(vb, "perInstance", None)
                    if per_instance is not None:
                        entry["per_instance"] = bool(per_instance)
                    instance_rate = self._safe_int(getattr(vb, "instanceRate", None))
                    if instance_rate is not None:
                        entry["instance_rate"] = instance_rate
                    result["vbs"].append(entry)
            except Exception as exc:
                self._warn_swallow("mesh.inspect.vertex_buffers", exc)

            try:
                getter = getattr(pipe, "GetIBuffer", None)
                ib = getter() if callable(getter) else None
                rid = getattr(ib, "resourceId", None) if ib is not None else None
                rid_str = str(rid)
                if rid_str and "Null" not in rid_str and rid_str != "ResourceId::0":
                    result["ib"] = {
                        "rid": rid_str,
                        "name": self.ctx.GetResourceName(rid),
                        "meta": self._resource_meta(rid),
                        "offset": self._safe_int(getattr(ib, "byteOffset", None)),
                        "byte_stride": self._safe_int(getattr(ib, "byteStride", None)),
                        "format": self._enum_tail(getattr(getattr(ib, "format", None), "compType", None)),
                    }
            except Exception as exc:
                self._warn_swallow("mesh.inspect.index_buffer", exc)

            try:
                postvs_in = controller.GetPostVSData(0, 0, rd.MeshDataStage.VSIn)
                topo = str(getattr(postvs_in, "topology", ""))
                if topo and "Unknown" not in topo:
                    result["topo"] = topo
                if not result["idx"]:
                    result["idx"] = int(getattr(postvs_in, "numIndices", 0) or 0)
            except Exception as exc:
                self._warn_swallow("mesh.inspect.postvs_in", exc)

            try:
                postvs = controller.GetPostVSData(0, 0, rd.MeshDataStage.VSOut)
                verts = int(getattr(postvs, "numIndices", 0) or 0)
                if verts:
                    result["postvs"]["verts"] = verts
            except Exception as exc:
                self._warn_swallow("mesh.inspect.postvs_out", exc)

            if not result["attrs"]:
                try:
                    vs = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
                    for attr in vs.inputSignature:
                        result["attrs"].append(
                            {
                                "name": attr.semanticIdxName if attr.semanticIdxName else attr.varName,
                                "fmt": "{}{}".format(str(attr.varType).split(".")[-1], attr.compCount),
                            }
                        )
                except Exception as exc:
                    self._warn_swallow("mesh.inspect.vs_input_signature", exc)

        self.ctx.Replay().BlockInvoke(collect)

        return {
            "ok": True,
            "mode": "summary",
            "data": result,
            "err": None,
            "meta": {"cap": "active", "truncated": False},
        }

    @staticmethod
    def _mesh_bytes(data):
        try:
            return bytes(data)
        except Exception:
            return bytes(bytearray(data))

    @classmethod
    def _decode_vertex_value(cls, fmt, data, offset):
        special = getattr(fmt, "Special", None)
        if callable(special) and special():
            raise _MeshExportError("unsupported_vertex_format", "Packed vertex formats are not supported")

        comp_type = cls._enum_tail(getattr(fmt, "compType", None))
        comp_count = int(getattr(fmt, "compCount", 0) or 0)
        comp_width = int(getattr(fmt, "compByteWidth", 0) or 0)
        if comp_count <= 0 or comp_width <= 0:
            raise _MeshExportError("unsupported_vertex_format", "Invalid vertex format")

        chars = {
            "Float": {2: "e", 4: "f", 8: "d"},
            "UInt": {1: "B", 2: "H", 4: "I", 8: "Q"},
            "UNorm": {1: "B", 2: "H", 4: "I", 8: "Q"},
            "UScaled": {1: "B", 2: "H", 4: "I", 8: "Q"},
            "SInt": {1: "b", 2: "h", 4: "i", 8: "q"},
            "SNorm": {1: "b", 2: "h", 4: "i", 8: "q"},
            "SScaled": {1: "b", 2: "h", 4: "i", 8: "q"},
        }
        char = chars.get(comp_type, {}).get(comp_width)
        if char is None:
            raise _MeshExportError(
                "unsupported_vertex_format",
                "Unsupported vertex format {}{}x{}".format(comp_type, comp_width, comp_count),
            )

        size = comp_count * comp_width
        if offset < 0 or offset + size > len(data):
            raise _MeshExportError("buffer_too_short", "Vertex buffer data is shorter than expected")
        values = list(struct.unpack_from("<{}{}".format(comp_count, char), data, offset))

        if comp_type == "UNorm":
            divisor = float((1 << (comp_width * 8)) - 1)
            values = [float(value) / divisor for value in values]
        elif comp_type == "SNorm":
            minimum = -(1 << (comp_width * 8 - 1))
            maximum = float((1 << (comp_width * 8 - 1)) - 1)
            values = [-1.0 if value == minimum else float(value) / maximum for value in values]

        bgra_order = getattr(fmt, "BGRAOrder", None)
        if callable(bgra_order) and bgra_order() and len(values) == 4:
            values = [values[2], values[1], values[0], values[3]]
        return values

    @staticmethod
    def _vertex_format_size(fmt):
        special = getattr(fmt, "Special", None)
        if callable(special) and special():
            raise _MeshExportError("unsupported_vertex_format", "Packed vertex formats are not supported")
        comp_count = int(getattr(fmt, "compCount", 0) or 0)
        comp_width = int(getattr(fmt, "compByteWidth", 0) or 0)
        if comp_count <= 0 or comp_width <= 0:
            raise _MeshExportError("unsupported_vertex_format", "Invalid vertex format")
        return comp_count * comp_width

    @staticmethod
    def _semantic_kind(name):
        semantic = str(name or "").upper()
        if semantic.startswith("POSITION"):
            return "position"
        if semantic.startswith("NORMAL"):
            return "normal"
        if semantic.startswith("TEXCOORD") or semantic.startswith("UV"):
            return "texcoord"
        return None

    @staticmethod
    def _mesh_resource_valid(rid):
        rid_text = str(rid)
        return bool(rid_text) and "Null" not in rid_text and rid_text != "ResourceId::0"

    @staticmethod
    def _resolve_obj_path(dest, eid, overwrite):
        if not dest or not str(dest).strip():
            raise _MeshExportError("missing_destination", "dest is required")

        requested = str(dest)
        path = os.path.abspath(requested)
        _root, suffix = os.path.splitext(path)
        if os.path.isdir(path) or requested.endswith(("\\", "/")) or not suffix:
            path = os.path.join(path, "mesh_eid{}.obj".format(eid))
        elif suffix.lower() != ".obj":
            raise _MeshExportError("unsupported_format", "Only OBJ export is supported")

        out_dir = os.path.dirname(path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        if overwrite or not os.path.exists(path):
            return path

        root, suffix = os.path.splitext(path)
        for index in range(1, 10000):
            candidate = "{}_{:03d}{}".format(root, index, suffix)
            if not os.path.exists(candidate):
                return candidate
        raise _MeshExportError("path_conflict", "Could not find a non-conflicting OBJ path")

    @staticmethod
    def _action_is_indexed(action):
        try:
            return bool(action.flags & rd.ActionFlags.Indexed)
        except Exception:
            return "Indexed" in str(getattr(action, "flags", ""))

    def _read_mesh_indices(self, controller, action, pipe):
        count = int(getattr(action, "numIndices", 0) or 0)
        if count <= 0:
            raise _MeshExportError("empty_mesh", "The action has no vertices or indices")
        if not self._action_is_indexed(action):
            return list(range(count)), False

        getter = getattr(pipe, "GetIBuffer", None)
        ib = getter() if callable(getter) else None
        rid = getattr(ib, "resourceId", None) if ib is not None else None
        stride = int(getattr(ib, "byteStride", 0) or 0) if ib is not None else 0
        if not self._mesh_resource_valid(rid) or stride not in (1, 2, 4):
            raise _MeshExportError("invalid_index_buffer", "Indexed action has no supported index buffer")

        index_offset = int(getattr(action, "indexOffset", 0) or 0)
        byte_offset = int(getattr(ib, "byteOffset", 0) or 0) + index_offset * stride
        raw = self._mesh_bytes(controller.GetBufferData(rid, byte_offset, count * stride))
        if len(raw) < count * stride:
            raise _MeshExportError("buffer_too_short", "Index buffer data is shorter than expected")

        index_char = {1: "B", 2: "H", 4: "I"}[stride]
        indices = list(struct.unpack_from("<{}{}".format(count, index_char), raw, 0))
        base_vertex = int(getattr(action, "baseVertex", 0) or 0)
        if base_vertex:
            indices = [index + base_vertex for index in indices]
        if min(indices) < 0:
            raise _MeshExportError("invalid_vertex_index", "Index plus baseVertex is negative")
        return indices, True

    def _read_mesh_attributes(self, controller, action, pipe, indices):
        selected = {}
        getter = getattr(pipe, "GetVertexInputs", None)
        for attr in (getter() if callable(getter) else []) or []:
            if bool(getattr(attr, "perInstance", False)):
                continue
            kind = self._semantic_kind(getattr(attr, "name", ""))
            if kind is not None and kind not in selected:
                selected[kind] = attr
        if "position" not in selected:
            raise _MeshExportError("position_not_found", "No per-vertex POSITION input was found")

        getter = getattr(pipe, "GetVBuffers", None)
        vbuffers = list((getter() if callable(getter) else []) or [])
        unique_indices = []
        index_map = {}
        for vertex_index in indices:
            if vertex_index not in index_map:
                index_map[vertex_index] = len(unique_indices) + 1
                unique_indices.append(vertex_index)

        min_index = min(unique_indices)
        max_index = max(unique_indices)
        vertex_offset = int(getattr(action, "vertexOffset", 0) or 0)
        specs = {}
        warnings = []

        for kind, attr in selected.items():
            try:
                slot = int(getattr(attr, "vertexBuffer", -1))
                if slot < 0 or slot >= len(vbuffers):
                    raise _MeshExportError("invalid_vertex_buffer", "Vertex buffer slot is out of range")
                vb = vbuffers[slot]
                rid = getattr(vb, "resourceId", None)
                stride = int(getattr(vb, "byteStride", 0) or 0)
                attr_offset = int(getattr(attr, "byteOffset", 0) or 0)
                value_size = self._vertex_format_size(attr.format)
                required_components = {"position": 3, "normal": 3, "texcoord": 2}[kind]
                if int(getattr(attr.format, "compCount", 0) or 0) < required_components:
                    raise _MeshExportError(
                        "unsupported_vertex_format",
                        "{} requires at least {} components".format(
                            getattr(attr, "name", kind), required_components
                        ),
                    )
                if not self._mesh_resource_valid(rid) or stride <= 0:
                    raise _MeshExportError("invalid_vertex_buffer", "Vertex buffer is missing or has zero stride")
                specs[kind] = {
                    "attr": attr,
                    "slot": slot,
                    "vb": vb,
                    "rid": rid,
                    "stride": stride,
                    "attr_offset": attr_offset,
                    "value_size": value_size,
                }
            except _MeshExportError as exc:
                if kind == "position":
                    raise
                warnings.append("Skipped {}: {}".format(getattr(attr, "name", kind), str(exc)))

        slot_data = {}
        for slot in set(spec["slot"] for spec in specs.values()):
            slot_specs = [spec for spec in specs.values() if spec["slot"] == slot]
            first = slot_specs[0]
            stride = first["stride"]
            vb_offset = int(getattr(first["vb"], "byteOffset", 0) or 0)
            read_offset = vb_offset + (vertex_offset + min_index) * stride
            max_value_end = max(spec["attr_offset"] + spec["value_size"] for spec in slot_specs)
            read_length = (max_index - min_index) * stride + max_value_end
            if read_offset < 0:
                raise _MeshExportError("invalid_vertex_offset", "Vertex buffer read offset is negative")
            raw = self._mesh_bytes(
                controller.GetBufferData(first["rid"], read_offset, read_length)
            )
            if len(raw) < read_length:
                raise _MeshExportError("buffer_too_short", "Vertex buffer data is shorter than expected")
            slot_data[slot] = raw

        values = {}
        for kind, spec in specs.items():
            decoded = []
            try:
                for vertex_index in unique_indices:
                    relative_index = vertex_index - min_index
                    offset = relative_index * spec["stride"] + spec["attr_offset"]
                    decoded.append(
                        self._decode_vertex_value(spec["attr"].format, slot_data[spec["slot"]], offset)
                    )
            except _MeshExportError as exc:
                if kind == "position":
                    raise
                warnings.append("Skipped {}: {}".format(getattr(spec["attr"], "name", kind), str(exc)))
                continue
            values[kind] = decoded

        return unique_indices, index_map, values, selected, warnings

    @staticmethod
    def _obj_number(value):
        return "{:.9g}".format(float(value))

    def _write_obj(self, path, eid, indices, index_map, values):
        positions = values["position"]
        normals = values.get("normal")
        texcoords = values.get("texcoord")
        with open(path, "w", encoding="utf-8", newline="\n") as obj:
            obj.write("# Exported from RenderDoc action EID {}\n".format(eid))
            obj.write("o mesh_eid{}\n".format(eid))
            for value in positions:
                if len(value) < 3:
                    raise _MeshExportError("invalid_position", "POSITION requires at least three components")
                obj.write("v {} {} {}\n".format(*[self._obj_number(item) for item in value[:3]]))
            if texcoords is not None:
                for value in texcoords:
                    if len(value) < 2:
                        raise _MeshExportError("invalid_texcoord", "TEXCOORD requires at least two components")
                    obj.write("vt {} {}\n".format(*[self._obj_number(item) for item in value[:2]]))
            if normals is not None:
                for value in normals:
                    if len(value) < 3:
                        raise _MeshExportError("invalid_normal", "NORMAL requires at least three components")
                    obj.write("vn {} {} {}\n".format(*[self._obj_number(item) for item in value[:3]]))

            for offset in range(0, len(indices) - 2, 3):
                face = []
                for vertex_index in indices[offset : offset + 3]:
                    obj_index = index_map[vertex_index]
                    if texcoords is not None and normals is not None:
                        face.append("{0}/{0}/{0}".format(obj_index))
                    elif texcoords is not None:
                        face.append("{0}/{0}".format(obj_index))
                    elif normals is not None:
                        face.append("{0}//{0}".format(obj_index))
                    else:
                        face.append(str(obj_index))
                obj.write("f {}\n".format(" ".join(face)))

    def export_mesh(self, params):
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
        action = self.ctx.GetAction(eid)
        if action is None:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": "bad_event", "msg": "Event not found"},
                "meta": {"cap": "active", "truncated": False},
            }

        try:
            out_path = self._resolve_obj_path(params.get("dest"), eid, bool(params.get("overwrite")))
        except _MeshExportError as exc:
            return {
                "ok": False,
                "mode": "summary",
                "data": None,
                "err": {"code": exc.code, "msg": str(exc)},
                "meta": {"cap": "active", "truncated": False},
            }

        result = {"data": None, "error": None, "error_code": "export_failed"}

        def collect(controller):
            try:
                controller.SetFrameEvent(eid, True)
                pipe = controller.GetPipelineState()
                topology = ""
                topology_getter = getattr(pipe, "GetPrimitiveTopology", None)
                if callable(topology_getter):
                    topology = self._enum_tail(topology_getter()) or ""
                if not topology:
                    postvs_in = controller.GetPostVSData(0, 0, rd.MeshDataStage.VSIn)
                    topology = self._enum_tail(getattr(postvs_in, "topology", None)) or ""
                if topology != "TriangleList":
                    raise _MeshExportError(
                        "unsupported_topology",
                        "Only TriangleList topology is supported, got {}".format(topology or "Unknown"),
                    )

                indices, indexed = self._read_mesh_indices(controller, action, pipe)
                trailing = len(indices) % 3
                warnings = []
                if trailing:
                    warnings.append("Ignored {} trailing indices for TriangleList".format(trailing))
                unique_indices, index_map, values, selected, attr_warnings = self._read_mesh_attributes(
                    controller, action, pipe, indices
                )
                warnings.extend(attr_warnings)
                instances = int(getattr(action, "numInstances", 0) or 0)
                if instances > 1:
                    warnings.append(
                        "Instanced draw: exported base geometry once; {} instances were not expanded".format(
                            instances
                        )
                    )

                self._write_obj(out_path, eid, indices, index_map, values)
                result["data"] = {
                    "eid": eid,
                    "path": out_path,
                    "stage": "vsin",
                    "topology": topology,
                    "indexed": indexed,
                    "vertices": len(unique_indices),
                    "indices": len(indices),
                    "triangles": len(indices) // 3,
                    "instances": instances,
                    "attributes": [
                        getattr(selected[kind], "name", kind)
                        for kind in ("position", "normal", "texcoord")
                        if kind in values
                    ],
                    "warnings": warnings,
                }
            except _MeshExportError as exc:
                result["error"] = str(exc)
                result["error_code"] = exc.code
            except Exception as exc:
                result["error"] = str(exc)

        self.ctx.Replay().BlockInvoke(collect)

        return {
            "ok": result["data"] is not None,
            "mode": "summary",
            "data": result["data"],
            "err": None
            if result["data"] is not None
            else {"code": result["error_code"], "msg": result["error"]},
            "meta": {"cap": "active", "truncated": False},
        }
