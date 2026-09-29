"""Versioned shader-debug evidence; values retain exact bits, including NaN payloads."""
import hashlib
import json
import math
import os
import struct
import renderdoc as rd


def _variable(value):
    raw = b"".join(struct.pack("<Q", int(word)) for word in value.value.u64v)
    count = min(16, int(value.rows) * int(value.columns))
    floats = struct.unpack("<" + "f" * count, raw[:count * 4]) if count else []
    return {"name": value.name, "type": str(value.type), "rows": int(value.rows), "columns": int(value.columns),
            "raw_hex": raw.hex(), "float32_view": [v if math.isfinite(v) else str(v) for v in floats],
            "members": [_variable(member) for member in value.members]}


class ShaderDebugServiceMixin:
    def export_shader_debug_trace(self, params):
        if not self.ctx.IsCaptureLoaded():
            return self._no_capture()
        eid, x, y = (int(params[key]) for key in ("eid", "x", "y"))
        maximum = int(params.get("max_steps", 100000))
        if min(eid, x, y) < 0 or not 1 <= maximum <= 1000000:
            raise ValueError("Invalid event, pixel coordinate or max_steps")
        path = os.path.abspath(params["dest"])
        if os.path.exists(path) and not params.get("overwrite", False):
            raise FileExistsError(path)
        payload = {"schema_version": 1, "capture_path": self.ctx.GetCaptureFilename(), "eid": eid,
                   "stage": "PS", "pixel": {"x": x, "y": y}, "coordinate_origin": "top-left",
                   "interpretation": "RenderDoc shader debugger simulation, separately compare to actual hardware output",
                   "states": [], "complete": False, "errors": []}

        def collect(controller):
            trace = None
            try:
                controller.SetFrameEvent(eid, False)
                pipeline = controller.GetPipelineState()
                reflection = pipeline.GetShaderReflection(rd.ShaderStage.Pixel)
                if reflection is None:
                    raise RuntimeError("No pixel shader at event")
                payload["shader"] = {"rid": str(pipeline.GetShader(rd.ShaderStage.Pixel)),
                    "sha256": hashlib.sha256(bytes(reflection.rawBytes)).hexdigest()}
                payload["disassembly"] = controller.DisassembleShader(pipeline.GetGraphicsPipelineObject(), reflection, "")
                trace = controller.DebugPixel(x, y, rd.DebugPixelInputs())
                if trace is None or trace.debugger is None:
                    raise RuntimeError("Pixel debugger unavailable")
                for field in ("inputs", "constantBlocks", "readOnlyResources", "readWriteResources", "samplers"):
                    payload[field] = [_variable(value) for value in getattr(trace, field)]
                while True:
                    states = controller.ContinueDebug(trace.debugger)
                    if not states:
                        payload["complete"] = True
                        break
                    for state in states:
                        if len(payload["states"]) >= maximum:
                            raise RuntimeError("max_steps reached; trace incomplete")
                        payload["states"].append({"step": int(state.stepIndex), "next_instruction": int(state.nextInstruction),
                            "flags": str(state.flags), "callstack": list(state.callstack),
                            "changes": [{"before": _variable(change.before), "after": _variable(change.after)} for change in state.changes]})
            except Exception as exc:
                payload["errors"].append(str(exc))
            finally:
                if trace is not None:
                    controller.FreeTrace(trace)

        self.ctx.Replay().BlockInvoke(collect)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        os.replace(temporary, path)
        return {"ok": payload["complete"], "mode": "summary",
                "data": {"path": path, "eid": eid, "x": x, "y": y, "steps": len(payload["states"]), "complete": payload["complete"]},
                "err": None if payload["complete"] else {"code": "incomplete_debug_trace", "msg": "; ".join(payload["errors"])},
                "meta": {"cap": "active", "truncated": False}}
