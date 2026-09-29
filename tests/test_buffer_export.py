import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest


previous = sys.modules.get("renderdoc")
sys.modules["renderdoc"] = types.ModuleType("renderdoc")
try:
    path = Path(__file__).resolve().parents[1] / "bridge_extension/renderdoc_mcp_bridge/domains/export.py"
    spec = importlib.util.spec_from_file_location("buffer_export_domain_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
finally:
    if previous is None:
        sys.modules.pop("renderdoc", None)
    else:
        sys.modules["renderdoc"] = previous


class Controller:
    def __init__(self, data, truncate=False):
        self.data, self.truncate = data, truncate
        self.reads = []
        self.eid = None

    def SetFrameEvent(self, eid, force):
        self.eid = eid

    def GetBufferData(self, rid, offset, length):
        self.reads.append((offset, length))
        data = self.data[offset:offset+length]
        return data[:-1] if self.truncate else data


class Exporter(module.ExportServiceMixin):
    def __init__(self, data, truncate=False):
        self.controller = Controller(data, truncate)
        self.ctx = types.SimpleNamespace(Replay=lambda: types.SimpleNamespace(BlockInvoke=lambda fn: fn(self.controller)))

    def _resolve_buffer_rid(self, controller, rid):
        return rid if rid == "ResourceId::1" else None

    def _resource_meta(self, rid):
        return {"size": len(self.controller.data)}

    _byte_list = staticmethod(bytes)

class BufferExportTests(unittest.TestCase):
    def test_large_range_is_complete_and_hashed(self):
        data = bytes(range(256)) * 32769
        service = Exporter(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Buffer 1.bin"
            result = service.export_buffer({"rid": "ResourceId::1", "dest": str(path), "eid": 67, "offset": 3})
            self.assertTrue(result["ok"])
            self.assertEqual(result["data"]["path"], str(path.resolve()))
            self.assertEqual(path.read_bytes(), data[3:])
            self.assertEqual(result["data"]["sha256"], hashlib.sha256(data[3:]).hexdigest())
            self.assertEqual(result["data"]["bytes"], len(data)-3)
            self.assertEqual(len(service.controller.reads), 2)
            self.assertEqual(service.controller.eid, 67)

    def test_truncated_replay_does_not_publish_partial_file(self):
        service = Exporter(b"abcd", truncate=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Buffer.bin"
            result = service.export_buffer({"rid": "ResourceId::1", "dest": str(path)})
            self.assertFalse(result["ok"])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_ranges_and_missing_resources_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            for extra in [{"offset": -1}, {"length": -1}, {"offset": 3, "length": 2}, {"rid": "ResourceId::2"}]:
                service = Exporter(b"abcd")
                result = service.export_buffer({"rid": "ResourceId::1", "dest": str(Path(directory)/"Buffer.bin"), **extra})
                self.assertFalse(result["ok"])
                self.assertEqual(service.controller.reads, [])

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"Buffer.bin"; path.write_bytes(b"previous")
            result = Exporter(b"new").export_buffer({"rid": "ResourceId::1", "dest": str(path)})
            self.assertFalse(result["ok"])
            self.assertEqual(path.read_bytes(), b"previous")

    def test_directory_destination_is_not_silently_reinterpreted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"Buffer.bin"; path.mkdir()
            result = Exporter(b"new").export_buffer({"rid": "ResourceId::1", "dest": str(path)})
            self.assertFalse(result["ok"])
            self.assertEqual(list(path.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
