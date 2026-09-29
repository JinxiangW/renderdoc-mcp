import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

folder = Path(__file__).resolve().parents[1] / 'bridge_extension/renderdoc_mcp_bridge/domains'
package = types.ModuleType('postvs_test_package'); package.__path__ = [str(folder)]
sys.modules[package.__name__] = package
previous = sys.modules.get('renderdoc')
sys.modules['renderdoc'] = types.SimpleNamespace(MeshDataStage=types.SimpleNamespace(VSOut=1), ShaderStage=types.SimpleNamespace(Vertex=0))
try:
    spec = importlib.util.spec_from_file_location('postvs_test_package.postvs', folder/'postvs.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
finally:
    if previous is None: sys.modules.pop('renderdoc', None)
    else: sys.modules['renderdoc'] = previous


class Controller:
    def __init__(self, count=3):
        self.count=count;self.reads=[];self.missing=None;self.unindexed=False
    def SetFrameEvent(self, eid, force): self.eid=eid
    def GetPipelineState(self):return self
    def GetShader(self, stage):return 'ResourceId::9'
    def GetShaderReflection(self, stage):return types.SimpleNamespace(outputSignature=[{'semantic':'SV_Position','mask':15}])
    def GetPostVSData(self, instance, view, stage):
        return types.SimpleNamespace(vertexResourceId='ResourceId::0' if instance==self.missing else 'ResourceId::100',vertexByteOffset=instance*16,vertexByteStride=16,indexResourceId='ResourceId::0' if self.unindexed else 'ResourceId::101',indexByteOffset=0,indexByteStride=2,numIndices=1,nearPlane=float('inf'))
    def GetBufferData(self,rid,offset,length):
        self.reads.append((rid,offset,length));return bytes(range(16))*self.count if rid=='ResourceId::100' else b'\0\0'


class Service(module.PostVSExportServiceMixin):
    def __init__(self, controller):
        self.ctx=types.SimpleNamespace(IsCaptureLoaded=lambda:True,GetAction=lambda eid:types.SimpleNamespace(numIndices=1,numInstances=controller.count),GetCaptureFilename=lambda:'fixture.rdc',Replay=lambda:types.SimpleNamespace(BlockInvoke=lambda f:f(controller)))


class PostVSExportTests(unittest.TestCase):
    def test_shared_backing_buffers_and_instance_offsets(self):
        c=Controller(75)
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/'out';r=Service(c).export_postvs({'eid':12,'dest':str(dest),'instance_count':75})
            self.assertTrue(r['ok']);self.assertEqual(len(c.reads),2)
            data=json.loads((dest/'manifest.json').read_text());self.assertEqual(len(data['instances']),75)
            self.assertEqual(data['instances'][74]['mesh']['vertexByteOffset'],74*16)
            self.assertEqual(data['instances'][0]['mesh']['nearPlane'],'inf')
            self.assertEqual((dest/'buffer_0.bin').read_bytes(),bytes(range(16))*75)
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            marker=Path(root)/'keep';marker.write_text('existing')
            self.assertFalse(Service(Controller()).export_postvs({'eid':12,'dest':root})['ok'])
            self.assertEqual(marker.read_text(),'existing')
    def test_range_rejected_before_replay(self):
        c=Controller(3)
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/'out';r=Service(c).export_postvs({'eid':12,'dest':str(dest),'first_instance':2,'instance_count':2})
            self.assertFalse(r['ok']);self.assertFalse(dest.exists());self.assertFalse(c.reads)
    def test_missing_instance_records_partial_failure(self):
        c=Controller();c.missing=1
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/'out';r=Service(c).export_postvs({'eid':12,'dest':str(dest),'instance_count':3})
            self.assertFalse(r['ok']);data=json.loads((dest/'manifest.json').read_text())
            self.assertFalse(data['complete']);self.assertEqual(len(data['instances']),1);self.assertIn('instance 1',data['error'])
    def test_budget_is_explicit_failure(self):
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/'out';r=Service(Controller()).export_postvs({'eid':12,'dest':str(dest),'max_bytes':1})
            self.assertFalse(r['ok']);self.assertIn('budget',r['err']['msg']);self.assertTrue((dest/'manifest.json').exists())
    def test_unindexed_output(self):
        c=Controller();c.unindexed=True
        with tempfile.TemporaryDirectory() as root:
            r=Service(c).export_postvs({'eid':12,'dest':str(Path(root)/'out')})
            self.assertTrue(r['ok']);self.assertEqual(len(c.reads),1)

if __name__=='__main__':unittest.main()
