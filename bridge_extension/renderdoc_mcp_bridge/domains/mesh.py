"""Mesh inspection services."""

import renderdoc as rd


class MeshServiceMixin:
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
                    result["attrs"].append(
                        {
                            "name": attr.name,
                            "fmt": fmt_name,
                        }
                    )
            except Exception as exc:
                self._warn_swallow("mesh.inspect.vertex_inputs", exc)

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
