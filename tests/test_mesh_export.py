import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest


_FAKE_RENDERDOC = types.ModuleType("renderdoc")
_FAKE_RENDERDOC.ActionFlags = types.SimpleNamespace(Indexed=1)
_FAKE_RENDERDOC.MeshDataStage = types.SimpleNamespace(VSIn=0, VSOut=1)
_PREVIOUS_RENDERDOC = sys.modules.get("renderdoc")
sys.modules["renderdoc"] = _FAKE_RENDERDOC
try:
    _MODULE_PATH = (
        Path(__file__).resolve().parents[1]
        / "bridge_extension"
        / "renderdoc_mcp_bridge"
        / "domains"
        / "mesh.py"
    )
    _SPEC = importlib.util.spec_from_file_location("renderdoc_mcp_bridge_mesh", _MODULE_PATH)
    _MODULE = importlib.util.module_from_spec(_SPEC)
    assert _SPEC is not None and _SPEC.loader is not None
    _SPEC.loader.exec_module(_MODULE)
finally:
    if _PREVIOUS_RENDERDOC is None:
        sys.modules.pop("renderdoc", None)
    else:
        sys.modules["renderdoc"] = _PREVIOUS_RENDERDOC

MeshServiceMixin = _MODULE.MeshServiceMixin


class _Format:
    def __init__(self, comp_type, comp_count, comp_width):
        self.compType = "CompType.{}".format(comp_type)
        self.compCount = comp_count
        self.compByteWidth = comp_width

    def Special(self):
        return False

    def BGRAOrder(self):
        return False


class _Attr:
    def __init__(self, name, offset, fmt, slot=0, per_instance=False):
        self.name = name
        self.byteOffset = offset
        self.format = fmt
        self.vertexBuffer = slot
        self.perInstance = per_instance


class _BufferBinding:
    def __init__(self, resource_id, offset, stride):
        self.resourceId = resource_id
        self.byteOffset = offset
        self.byteStride = stride


class _Action:
    def __init__(
        self,
        count,
        indexed,
        instances=1,
        index_offset=0,
        base_vertex=0,
        vertex_offset=0,
    ):
        self.numIndices = count
        self.numInstances = instances
        self.flags = _FAKE_RENDERDOC.ActionFlags.Indexed if indexed else 0
        self.indexOffset = index_offset
        self.baseVertex = base_vertex
        self.vertexOffset = vertex_offset


class _Pipe:
    def __init__(self, attrs, vbuffers, ibuffer=None, topology="Topology.TriangleList"):
        self._attrs = attrs
        self._vbuffers = vbuffers
        self._ibuffer = ibuffer
        self._topology = topology

    def GetVertexInputs(self):
        return self._attrs

    def GetVBuffers(self):
        return self._vbuffers

    def GetIBuffer(self):
        return self._ibuffer

    def GetPrimitiveTopology(self):
        return self._topology


class _Controller:
    def __init__(self, pipe, buffers):
        self._pipe = pipe
        self._buffers = buffers
        self.eid = None

    def SetFrameEvent(self, eid, force):
        self.eid = eid

    def GetPipelineState(self):
        return self._pipe

    def GetBufferData(self, resource_id, offset, length):
        return self._buffers[resource_id][offset : offset + length]


class _Replay:
    def __init__(self, controller):
        self._controller = controller

    def BlockInvoke(self, callback):
        callback(self._controller)


class _Context:
    def __init__(self, action, controller):
        self._action = action
        self._replay = _Replay(controller)

    def IsCaptureLoaded(self):
        return True

    def GetAction(self, eid):
        return self._action if eid == 42 else None

    def Replay(self):
        return self._replay


class _Service(MeshServiceMixin):
    def __init__(self, ctx):
        self.ctx = ctx


def _write_vertex(buffer, offset, position, normal=None, texcoord=None):
    struct.pack_into("<3f", buffer, offset, *position)
    if normal is not None:
        struct.pack_into("<3f", buffer, offset + 12, *normal)
    if texcoord is not None:
        struct.pack_into("<2f", buffer, offset + 24, *texcoord)


class MeshExportTests(unittest.TestCase):
    def test_export_indexed_obj_applies_offsets_and_exports_common_attributes(self):
        vb_data = bytearray(176)
        _write_vertex(vb_data, 72, (1, 2, 3), (0, 0, 1), (0, 0))
        _write_vertex(vb_data, 104, (4, 5, 6), (0, 1, 0), (1, 0))
        _write_vertex(vb_data, 136, (7, 8, 9), (1, 0, 0), (0, 1))
        ib_data = bytearray(10)
        struct.pack_into("<3H", ib_data, 4, 0, 1, 2)

        attrs = [
            _Attr("POSITION", 0, _Format("Float", 3, 4)),
            _Attr("NORMAL", 12, _Format("Float", 3, 4)),
            _Attr("TEXCOORD0", 24, _Format("Float", 2, 4)),
        ]
        pipe = _Pipe(
            attrs,
            [_BufferBinding("vb", 8, 32)],
            _BufferBinding("ib", 2, 2),
        )
        action = _Action(
            3,
            indexed=True,
            instances=2,
            index_offset=1,
            base_vertex=1,
            vertex_offset=1,
        )
        service = _Service(_Context(action, _Controller(pipe, {"vb": vb_data, "ib": ib_data})))

        with tempfile.TemporaryDirectory() as temp_dir:
            dest = Path(temp_dir) / "mesh.obj"
            result = service.export_mesh({"eid": 42, "dest": str(dest)})
            text = dest.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["vertices"], 3)
        self.assertEqual(result["data"]["triangles"], 1)
        self.assertEqual(result["data"]["attributes"], ["POSITION", "NORMAL", "TEXCOORD0"])
        self.assertIn("v 1 2 3", text)
        self.assertIn("vt 1 0", text)
        self.assertIn("vn 0 0 1", text)
        self.assertIn("f 1/1/1 2/2/2 3/3/3", text)
        self.assertIn("2 instances were not expanded", result["data"]["warnings"][0])

    def test_export_supports_32_bit_indices(self):
        vb_data = bytearray(36)
        _write_vertex(vb_data, 0, (0, 0, 0))
        _write_vertex(vb_data, 12, (1, 0, 0))
        _write_vertex(vb_data, 24, (0, 1, 0))
        ib_data = struct.pack("<3I", 2, 0, 1)
        pipe = _Pipe(
            [_Attr("POSITION", 0, _Format("Float", 3, 4))],
            [_BufferBinding("vb", 0, 12)],
            _BufferBinding("ib", 0, 4),
        )
        action = _Action(3, indexed=True)
        service = _Service(_Context(action, _Controller(pipe, {"vb": vb_data, "ib": ib_data})))

        with tempfile.TemporaryDirectory() as temp_dir:
            result = service.export_mesh({"eid": 42, "dest": str(Path(temp_dir) / "mesh.obj")})

        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["indexed"])
        self.assertEqual(result["data"]["indices"], 3)

    def test_export_supports_non_indexed_draw_and_vertex_offset(self):
        vb_data = bytearray(48)
        _write_vertex(vb_data, 12, (1, 0, 0))
        _write_vertex(vb_data, 24, (0, 1, 0))
        _write_vertex(vb_data, 36, (0, 0, 1))
        pipe = _Pipe(
            [_Attr("POSITION", 0, _Format("Float", 3, 4))],
            [_BufferBinding("vb", 0, 12)],
        )
        action = _Action(3, indexed=False, vertex_offset=1)
        service = _Service(_Context(action, _Controller(pipe, {"vb": vb_data})))

        with tempfile.TemporaryDirectory() as temp_dir:
            dest = Path(temp_dir) / "mesh.obj"
            result = service.export_mesh({"eid": 42, "dest": str(dest)})
            text = dest.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertFalse(result["data"]["indexed"])
        self.assertIn("v 1 0 0", text)
        self.assertIn("f 1 2 3", text)

    def test_export_rejects_non_triangle_topology(self):
        pipe = _Pipe(
            [_Attr("POSITION", 0, _Format("Float", 3, 4))],
            [_BufferBinding("vb", 0, 12)],
            topology="Topology.LineList",
        )
        action = _Action(2, indexed=False)
        service = _Service(_Context(action, _Controller(pipe, {"vb": bytearray(24)})))

        with tempfile.TemporaryDirectory() as temp_dir:
            result = service.export_mesh({"eid": 42, "dest": str(Path(temp_dir) / "mesh.obj")})

        self.assertFalse(result["ok"])
        self.assertEqual(result["err"]["code"], "unsupported_topology")


if __name__ == "__main__":
    unittest.main()
