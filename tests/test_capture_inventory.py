import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


_previous = sys.modules.get("renderdoc")
sys.modules["renderdoc"] = types.SimpleNamespace(ShaderStage=types.SimpleNamespace(Compute=5))
try:
    _path = Path(__file__).resolve().parents[1] / "bridge_extension/renderdoc_mcp_bridge/domains/inventory.py"
    _spec = importlib.util.spec_from_file_location("capture_inventory_test_module", _path)
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
finally:
    if _previous is None:
        sys.modules.pop("renderdoc", None)
    else:
        sys.modules["renderdoc"] = _previous


def action(eid, name, children=()):
    return types.SimpleNamespace(eventId=eid, customName=name, children=list(children), flags="Drawcall",
                                 events=[types.SimpleNamespace(eventId=eid, chunkIndex=eid + 100)],
                                 outputs=["ResourceId::4"], depthOut="ResourceId::5", numIndices=3,
                                 GetName=lambda unused: name)


class Controller:
    def GetTextures(self):
        return [types.SimpleNamespace(resourceId="ResourceId::4", width=32, height=32, mips=2)]

    def GetBuffers(self):
        return []

    def GetResources(self):
        return [types.SimpleNamespace(resourceId="ResourceId::4", name="OriginalResourceName")]

    def GetUsage(self, rid):
        return [types.SimpleNamespace(eventId=1, usage="ColorTarget", view="Mip0"),
                types.SimpleNamespace(eventId=2, usage="ColorTarget", view="Mip0"),
                types.SimpleNamespace(eventId=3, usage="PS_Resource", view="Mip1")]


class Context:
    def __init__(self, controller=None):
        self.controller = controller or Controller()

    def IsCaptureLoaded(self):
        return True

    def GetStructuredFile(self):
        return None

    def CurRootActions(self):
        return [action(10, "OriginalPass", [action(1, "OriginalDraw1"), action(2, "OriginalDraw2")])]

    def GetCaptureFilename(self):
        return "C:/Caps/OriginalCapture.rdc"

    def APIProps(self):
        return types.SimpleNamespace(pipelineType="D3D11")

    def Replay(self):
        return types.SimpleNamespace(BlockInvoke=lambda callback: callback(self.controller))


class Service(_module.CaptureInventoryServiceMixin):
    def __init__(self, controller=None):
        self.ctx = Context(controller)

    def _action_type(self, unused):
        return "Draw"

    def _resource_display_name(self, unused):
        return "OriginalResourceName"


class CaptureInventoryTests(unittest.TestCase):
    def test_preserves_names_parents_and_every_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            result = Service().export_capture_inventory({"dest": str(path)})
            self.assertTrue(result["ok"])
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual([item["eid"] for item in data["actions"]], [10, 1, 2])
            self.assertEqual(data["actions"][1]["parents"], [10])
            self.assertEqual(data["actions"][1]["name"], "OriginalDraw1")
            self.assertEqual([item["eid"] for item in data["resources"][0]["usage"]], [1, 2, 3])
            self.assertEqual(data["resources"][0]["usage"][2]["view"], "Mip1")

    def test_existing_artifact_is_not_overwritten_implicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            path.write_text("original", encoding="utf-8")
            result = Service().export_capture_inventory({"dest": str(path)})
            self.assertFalse(result["ok"])
            self.assertEqual(path.read_text(), "original")

    def test_resource_failure_is_explicit_and_keeps_partial_evidence(self):
        controller = Controller()
        def fail(unused):
            raise RuntimeError("missing usage")
        controller.GetUsage = fail
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            result = Service(controller).export_capture_inventory({"dest": str(path)})
            self.assertFalse(result["ok"])
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(data["complete"])
            self.assertEqual(data["errors"][0]["operation"], "GetUsage")
            self.assertEqual(len(data["actions"]), 3)

    def test_slot_zero_and_subresource_ranges_are_preserved(self):
        value = types.SimpleNamespace(access=types.SimpleNamespace(index=0),
            descriptor=types.SimpleNamespace(resource="ResourceId::4", firstMip=0, numMips=2, firstSlice=1, numSlices=3))
        encoded = _module._plain(value)
        self.assertEqual(encoded["access"]["index"], 0)
        self.assertEqual(encoded["descriptor"]["firstMip"], 0)
        self.assertEqual(encoded["descriptor"]["numSlices"], 3)

    def test_swig_style_getitem_only_array_keeps_descriptors(self):
        class LegacySequence:
            def __getitem__(self, index):
                return [types.SimpleNamespace(resource="ResourceId::4", firstMip=2, firstSlice=3)][index]
            def __str__(self):
                return "[<Swig Object of type 'Descriptor *'>]"
        self.assertFalse(hasattr(LegacySequence(), "__iter__"))
        self.assertEqual(_module._plain(LegacySequence()),
                         [{"resource": "ResourceId::4", "firstMip": 2, "firstSlice": 3}])

    def test_opaque_objects_fail_explicitly(self):
        self.assertIn("serialization_error", _module._plain(object()))


if __name__ == "__main__":
    unittest.main()


class BindingLocationTests(unittest.TestCase):
    def test_sparse_register_is_not_reflection_index(self):
        binding=types.SimpleNamespace(access=types.SimpleNamespace(index=2,arrayElement=0))
        reflection=[types.SimpleNamespace(fixedBindNumber=i,name="t"+str(i)) for i in [0,8,10]]
        result=_module.binding_location(binding,reflection)
        self.assertEqual(result["slot"],10)
        self.assertEqual(result["reflection_index"],2)
        self.assertEqual(result["name"],"t10")
        self.assertEqual(binding.access.index,2)

    def test_missing_reflection_stays_unresolved(self):
        result=_module.binding_location(types.SimpleNamespace(access=types.SimpleNamespace(index=65535,arrayElement=0)),[])
        self.assertIsNone(result["slot"])
        self.assertEqual(result["source"],"unresolved")

    def test_array_element_is_separate_from_binding(self):
        result=_module.binding_location(types.SimpleNamespace(access=types.SimpleNamespace(index=0,arrayElement=3)),[types.SimpleNamespace(fixedBindNumber=8,name="array")])
        self.assertEqual((result["slot"],result["array_element"]),(8,3))

    def test_legacy_declared_binding(self):
        self.assertEqual(_module.binding_location(types.SimpleNamespace(fixedBindNumber=5),[])["slot"],5)


class PixelHistoryTests(unittest.TestCase):
    def setUp(self):
        _module.rd.Subresource=lambda: types.SimpleNamespace()
        _module.rd.CompType=types.SimpleNamespace(Typeless=0)

    def test_filtered_history_keeps_rejection_and_nan_bits(self):
        class HistoryController(Controller):
            def SetFrameEvent(self,*args):pass
            def PixelHistory(self,*args):
                return [types.SimpleNamespace(eventId=e,depthTestFailed=True,shaderDiscarded=False,
                    shaderOut=types.SimpleNamespace(col=types.SimpleNamespace(floatValue=[float("nan"),0.0],uintValue=[0x7fc00001,0]))) for e in [11,12]]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"pixel.json";result=Service(HistoryController()).export_pixel_history({"rid":"ResourceId::4","x":2,"y":3,"eid_min":11,"eid_max":11,"dest":str(path)})
            self.assertTrue(result["ok"]);data=json.loads(path.read_text())
            self.assertEqual(len(data["modifications"]),1)
            self.assertTrue(data["modifications"][0]["depthTestFailed"])
            self.assertEqual(data["modifications"][0]["shaderOut"]["col"]["uintValue"][0],0x7fc00001)
            self.assertEqual(data["modifications"][0]["shaderOut"]["col"]["floatValue"][0],"nan")

    def test_rejects_outside_pixel(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):Service().export_pixel_history({"rid":"ResourceId::4","x":32,"y":0,"dest":str(Path(tmp)/"x.json")})

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.json";path.write_text("keep")
            with self.assertRaises(FileExistsError):Service().export_pixel_history({"rid":"ResourceId::4","x":0,"y":0,"dest":str(path)})
            self.assertEqual(path.read_text(),"keep")
