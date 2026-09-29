"""Lossless per-instance VS output export, retaining replay-owned buffer layouts."""
import hashlib
import json
import math
import os
import renderdoc as rd
from .inventory import _plain


def _finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _finite_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite_json(item) for item in value]
    return value


class PostVSExportServiceMixin:
    def export_postvs(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()
        result = {"complete": False, "error": None}
        try:
            eid = int(params["eid"])
            first = int(params.get("first_instance", 0))
            count = int(params.get("instance_count", 1))
            view = int(params.get("view", 0))
            budget = int(params.get("max_bytes", 512 * 1024 * 1024))
            if first < 0 or not 1 <= count <= 1024 or view < 0 or budget <= 0:
                raise ValueError("Invalid instance/view/export-byte range")
            action = self.ctx.GetAction(eid)
            if action is None or int(action.numIndices) <= 0:
                raise ValueError("A geometry draw event is required")
            instances = max(1, int(action.numInstances))
            if first + count > instances:
                raise ValueError("Requested instances exceed draw instance count")
            if not params.get("dest"):
                raise ValueError("A fresh destination directory is required")
            path = os.path.abspath(str(params["dest"]))
            os.makedirs(path, exist_ok=False)
        except Exception as exc:
            return {"ok": False, "mode": "summary", "data": None,
                    "err": {"code": "postvs_export_args", "msg": str(exc)},
                    "meta": {"cap": "active", "truncated": False}}

        manifest = {"schema_version": 1, "capture_path": self.ctx.GetCaptureFilename(),
                    "eid": eid, "stage": "VSOut", "view": view, "first_instance": first,
                    "instance_count": count, "draw_instance_count": instances,
                    "instances": [], "buffers": [], "complete": False,
                    "scope": "Raw replay-generated VS buffers. MeshFormat offsets/strides are authoritative; numIndices is not a unique vertex count. No normalization, OBJ conversion or semantic float conversion is performed."}

        def collect(controller):
            try:
                controller.SetFrameEvent(eid, True)
                pipe = controller.GetPipelineState()
                manifest["shader_id"] = str(pipe.GetShader(rd.ShaderStage.Vertex))
                reflection = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
                manifest["output_signature"] = _plain(reflection.outputSignature) if reflection else None
                if hasattr(self, "_shader_replacement_maps"):
                    manifest["active_shader_replacements"] = {str(k): str(v) for k, v in self._shader_replacement_maps()[0].items()}
                saved = {}
                total = 0
                for instance in range(first, first + count):
                    mesh = controller.GetPostVSData(instance, view, rd.MeshDataStage.VSOut)
                    if not mesh.vertexResourceId or str(mesh.vertexResourceId) in ("ResourceId::0", "0") or mesh.vertexByteStride <= 0:
                        raise ValueError("No VS output for instance {}".format(instance))
                    record = {"instance": instance, "mesh": _plain(mesh), "files": {}}
                    for role, rid in (("vertex", mesh.vertexResourceId), ("index", mesh.indexResourceId)):
                        key = str(rid)
                        if not rid or key in ("ResourceId::0", "0"):
                            continue
                        if key not in saved:
                            # RenderDoc owns these transient IDs; they need not appear in
                            # the captured-resource inventory. Read each backing buffer once.
                            data = bytes(controller.GetBufferData(rid, 0, 0))
                            if not data:
                                raise ValueError("Empty replay buffer: " + key)
                            if total + len(data) > budget:
                                raise ValueError("VS backing buffers exceed export byte budget")
                            filename = "buffer_{}.bin".format(len(saved))
                            with open(os.path.join(path, filename), "xb") as stream:
                                stream.write(data)
                            saved[key] = filename
                            manifest["buffers"].append({"rid": key, "file": filename,
                                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
                            total += len(data)
                        record["files"][role] = saved[key]
                    manifest["instances"].append(record)
                manifest["complete"] = True
                result.update({"complete": True, "bytes": total})
            except Exception as exc:
                result["error"] = str(exc)
                manifest["error"] = str(exc)
            finally:
                with open(os.path.join(path, "manifest.json"), "x", encoding="utf-8") as stream:
                    json.dump(_finite_json(manifest), stream, indent=2, ensure_ascii=False, allow_nan=False)
                    stream.write("\n")

        self.ctx.Replay().BlockInvoke(collect)
        result.update({"path": path, "manifest": os.path.join(path, "manifest.json"),
                       "instances_exported": len(manifest["instances"]), "buffers": len(manifest["buffers"])})
        return {"ok": result["complete"], "mode": "summary", "data": result,
                "err": None if result["complete"] else {"code": "postvs_export_failed", "msg": result["error"]},
                "meta": {"cap": "active", "truncated": False}}
