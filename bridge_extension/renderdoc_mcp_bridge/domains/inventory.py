"""Lossless capture inventory and bounded pipeline-page export for offline analysis."""

import hashlib
import json
import os
import time
import math

import renderdoc as rd


def binding_location(binding, reflection_items):
    """DescriptorAccess.index addresses reflection, not the hardware register."""
    access = getattr(binding, "access", None)
    index = getattr(access, "index", None)
    if index is not None:
        index = int(index)
        items = list(reflection_items or [])
        declared = items[index] if 0 <= index < len(items) else None
        slot = getattr(declared, "fixedBindNumber", None)
        slot = int(slot) if slot is not None and 0 <= int(slot) < 0xffffffff else None
        return {"reflection_index": index, "slot": slot,
                "array_element": int(getattr(access, "arrayElement", 0)),
                "name": getattr(declared, "name", "") if declared is not None else "",
                "source": "reflection.fixedBindNumber" if slot is not None else "unresolved"}
    slot = getattr(binding, "fixedBindNumber", None)
    return {"reflection_index": None, "slot": int(slot) if slot is not None else None,
            "array_element": 0, "name": "", "source": "legacy.fixedBindNumber" if slot is not None else "unresolved"}


def _plain(value, depth=0):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if type(value).__name__ == "ResourceId":
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if depth >= 8:
        return {"serialization_limit": type(value).__name__, "value": str(value)}
    if isinstance(value, dict):
        return {str(key): _plain(item, depth + 1) for key, item in value.items()}
    # SWIG rdcarray implements Python's legacy __getitem__ sequence protocol
    # without necessarily exposing __iter__. iter() supports both protocols.
    try:
        iterator = iter(value)
    except TypeError:
        iterator = None
    if iterator is not None:
        return [_plain(item, depth + 1) for item in iterator]
    result = {}
    for name in dir(value):
        if name.startswith("_") or name in ("this", "thisown"):
            continue
        try:
            item = getattr(value, name)
            if not callable(item):
                result[name] = _plain(item, depth + 1)
        except Exception as exc:
            result[name] = {"serialization_error": str(exc)}
    return result or {"serialization_error": "Unsupported opaque object: " + type(value).__name__, "value": str(value)}


def _write_json(path, payload):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
    os.replace(temporary, path)


class CaptureInventoryServiceMixin:
    def export_pixel_history(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()
        path = os.path.abspath(params["dest"])
        if os.path.exists(path) and not params.get("overwrite", False):
            raise FileExistsError(path)
        rid, x, y = str(params["rid"]), int(params["x"]), int(params["y"])
        minimum, maximum = int(params.get("eid_min", 0)), int(params.get("eid_max", 0xffffffff))
        if min(x, y, minimum, maximum) < 0 or minimum > maximum:
            raise ValueError("Invalid pixel coordinate or event range")
        payload = {"schema_version": 1, "capture_path": self.ctx.GetCaptureFilename(),
                   "rid": rid, "x": x, "y": y, "coordinate_origin": "top-left",
                   "eid_min": minimum, "eid_max": maximum, "modifications": [], "complete": False}
        def finite(value):
            if isinstance(value, float) and not math.isfinite(value):
                return str(value)
            if isinstance(value, dict):
                return {k: finite(v) for k, v in value.items()}
            if isinstance(value, list):
                return [finite(v) for v in value]
            return value
        def collect(controller):
            texture = next((t for t in controller.GetTextures() if str(t.resourceId) == rid), None)
            if texture is None or x >= texture.width or y >= texture.height:
                raise ValueError("Texture missing or pixel outside mip0")
            sub = rd.Subresource()
            sub.mip, sub.slice, sub.sample = 0, 0, 0
            if maximum != 0xffffffff:
                controller.SetFrameEvent(maximum, False)
            history = controller.PixelHistory(texture.resourceId, x, y, sub, rd.CompType.Typeless)
            payload["modifications"] = [finite(_plain(item)) for item in history
                                        if minimum <= int(item.eventId) <= maximum]
            payload["complete"] = True
        self.ctx.Replay().BlockInvoke(collect)
        _write_json(path, payload)
        return {"ok": True, "mode": "summary", "data": {"path": path, "complete": True,
                "modification_count": len(payload["modifications"])}, "err": None,
                "meta": {"cap": "active", "truncated": False}}

    def export_capture_inventory(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()
        dest = params.get("dest")
        if not dest:
            return self._inventory_error("missing_args", "dest is required")
        mode = params.get("mode", "resources")
        if mode not in ("resources", "pipelines"):
            return self._inventory_error("invalid_mode", "mode must be resources or pipelines")
        after_eid = int(params.get("after_eid", 0))
        limit = int(params.get("limit", 64))
        if after_eid < 0 or limit < 1 or limit > 256:
            return self._inventory_error("invalid_range", "after_eid >= 0 and 1 <= limit <= 256 required")
        path = os.path.abspath(str(dest))
        if os.path.exists(path) and not params.get("overwrite", False):
            return self._inventory_error("destination_exists", path)

        structured = self.ctx.GetStructuredFile()
        actions = []
        live_actions = []

        def visit(nodes, parents):
            for action in nodes:
                children = list(action.children)
                name = action.customName or action.GetName(structured)
                kind = "Marker" if children else self._action_type(action)
                record = {"eid": int(action.eventId), "name": name, "kind": kind,
                          "flags": str(action.flags), "parents": list(parents),
                          "children": [int(child.eventId) for child in children],
                          "api_events": [{"eid": int(event.eventId), "chunk_index": int(event.chunkIndex)}
                                         for event in action.events]}
                for field in ("numIndices", "numInstances", "indexOffset", "baseVertex", "vertexOffset",
                              "instanceOffset", "dispatchDimension", "dispatchThreadsDimension", "outputs",
                              "depthOut", "copySource", "copyDestination", "copySourceSubresource",
                              "copyDestinationSubresource"):
                    if hasattr(action, field):
                        record[field] = _plain(getattr(action, field))
                actions.append(record)
                if not children and kind in ("Draw", "Dispatch"):
                    live_actions.append((action, record))
                visit(children, parents + [int(action.eventId)])

        visit(self.ctx.CurRootActions(), [])
        live_actions.sort(key=lambda pair: pair[1]["eid"])
        payload = {"schema_version": 2, "mode": mode, "capture_path": self.ctx.GetCaptureFilename(),
                   "api": str(self.ctx.APIProps().pipelineType), "generated_at": time.time(),
                   "errors": [], "actions_total": len(actions), "draw_dispatch_total": len(live_actions)}

        def collect_resources(controller):
            payload["actions"] = actions
            payload["resources"] = []
            payload["textures"] = [_plain(item) for item in controller.GetTextures()]
            payload["buffers"] = [_plain(item) for item in controller.GetBuffers()]
            for resource in controller.GetResources():
                item = _plain(resource)
                item["display_name"] = self._resource_display_name(resource.resourceId)
                try:
                    item["usage"] = [{"eid": int(use.eventId), "usage": str(use.usage),
                                      "view": str(getattr(use, "view", ""))}
                                     for use in controller.GetUsage(resource.resourceId)]
                except Exception as exc:
                    item["usage"] = None
                    payload["errors"].append({"rid": str(resource.resourceId), "operation": "GetUsage", "error": str(exc)})
                payload["resources"].append(item)
            payload["complete"] = not payload["errors"]
            payload["pipeline_details"] = "collected separately with mode=pipelines"

        def collect_pipelines(controller):
            candidates = [(action, record) for action, record in live_actions if record["eid"] > after_eid]
            selected = candidates[:limit]
            payload["pipelines"] = []
            payload["after_eid"] = after_eid
            for action, record in selected:
                entry = {"eid": record["eid"], "name": record["name"], "kind": record["kind"], "stages": {}, "errors": []}
                controller.SetFrameEvent(record["eid"], False)
                pipe = controller.GetPipelineState()
                stages = [("CS", rd.ShaderStage.Compute)] if record["kind"] == "Dispatch" else self._binding_stages()[:-1]
                for stage_name, stage in stages:
                    shader = pipe.GetShader(stage)
                    if str(shader) in ("ResourceId::Null", "ResourceId::0", "None"):
                        continue
                    reflection = pipe.GetShaderReflection(stage)
                    shader_info = self._shader_info(reflection, shader)
                    if reflection:
                        shader_info["entryPoint"] = reflection.entryPoint
                        shader_info["encoding"] = str(reflection.encoding)
                        raw = bytes(reflection.rawBytes)
                        shader_info["bytecode_sha256"] = hashlib.sha256(raw).hexdigest()
                        shader_info["bytecode_bytes"] = len(raw)
                    shader_info["bindings"] = {}
                    for category, getter in (("srv", pipe.GetReadOnlyResources), ("uav", pipe.GetReadWriteResources),
                                             ("cbv", pipe.GetConstantBlocks), ("sampler", pipe.GetSamplers)):
                        try:
                            reflection_name = {"srv": "readOnlyResources", "uav": "readWriteResources",
                                               "cbv": "constantBlocks", "sampler": "samplers"}[category]
                            records = []
                            for binding in getter(stage, False):
                                item = _plain(binding)
                                item["location"] = binding_location(binding, getattr(reflection, reflection_name, []))
                                records.append(item)
                            shader_info["bindings"][category] = records
                        except Exception as exc:
                            entry["errors"].append({"stage": stage_name, "operation": category, "error": str(exc)})
                    entry["stages"][stage_name] = shader_info
                try:
                    entry["outputs"] = _plain(pipe.GetOutputTargets())
                    entry["depth_target"] = _plain(pipe.GetDepthTarget())
                    entry["vertex_buffers"] = _plain(pipe.GetVBuffers())
                    entry["index_buffer"] = _plain(pipe.GetIBuffer())
                    if "D3D11" in payload["api"]:
                        native = controller.GetD3D11PipelineState()
                        entry["inputAssembly"] = _plain(native.inputAssembly)
                        entry["rasterizer"] = _plain(native.rasterizer)
                        entry["outputMerger"] = _plain(native.outputMerger)
                except Exception as exc:
                    entry["errors"].append({"operation": "pipeline_state", "error": str(exc)})
                payload["pipelines"].append(entry)
                payload["errors"].extend(dict(error, eid=record["eid"]) for error in entry["errors"])
            payload["next_after_eid"] = selected[-1][1]["eid"] if selected else after_eid
            payload["has_more"] = len(candidates) > len(selected)
            payload["complete"] = not payload["errors"]

        try:
            self.ctx.Replay().BlockInvoke(collect_resources if mode == "resources" else collect_pipelines)
            _write_json(path, payload)
        except Exception as exc:
            return self._inventory_error("inventory_failed", str(exc))
        summary = {key: value for key, value in payload.items() if key not in ("actions", "resources", "textures", "buffers", "pipelines")}
        for key in ("actions", "resources", "textures", "buffers", "pipelines"):
            if key in payload:
                summary[key + "_count"] = len(payload[key])
        summary["path"] = path
        return {"ok": not payload["errors"], "mode": "summary", "data": summary,
                "err": None if not payload["errors"] else {"code": "partial_inventory", "msg": "See recorded errors"},
                "meta": {"cap": "active", "truncated": False}}

    @staticmethod
    def _inventory_error(code, message):
        return {"ok": False, "mode": "summary", "data": None, "err": {"code": code, "msg": message},
                "meta": {"cap": "active", "truncated": False}}
