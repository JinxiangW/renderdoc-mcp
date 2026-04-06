"""Mesh inspection services."""

import renderdoc as rd


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
