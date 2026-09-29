import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

previous=sys.modules.get('renderdoc')
sys.modules['renderdoc']=types.SimpleNamespace(ShaderStage=types.SimpleNamespace(Pixel=4), DebugPixelInputs=lambda:None)
try:
    file=Path(__file__).resolve().parents[1]/'bridge_extension/renderdoc_mcp_bridge/domains/shader_debug.py'
    spec=importlib.util.spec_from_file_location('shader_debug_export_test',file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
finally:
    if previous is None:sys.modules.pop('renderdoc',None)
    else:sys.modules['renderdoc']=previous


def variable():
    return types.SimpleNamespace(name='r0',type='Float',rows=1,columns=2,
        value=types.SimpleNamespace(u64v=[0x800000007fc00001]+[0]*15),members=[])


class Controller:
    def __init__(self):self.freed=False;self.calls=0
    def SetFrameEvent(self,*args):pass
    def GetPipelineState(self):return self
    def GetShaderReflection(self,*args):return types.SimpleNamespace(rawBytes=b'DXBC')
    def GetShader(self,*args):return 'ResourceId::4'
    def GetGraphicsPipelineObject(self):return None
    def DisassembleShader(self,*args):return '0: mov r0, r1\n1: ret'
    def DebugPixel(self,*args):
        return types.SimpleNamespace(debugger=object(),inputs=[variable()],constantBlocks=[],readOnlyResources=[],readWriteResources=[],samplers=[])
    def ContinueDebug(self,*args):
        self.calls+=1
        if self.calls>1:return []
        return [types.SimpleNamespace(stepIndex=i,nextInstruction=i,flags='NoEvent',callstack=[],
            changes=[types.SimpleNamespace(before=variable(),after=variable())]) for i in range(2)]
    def FreeTrace(self,*args):self.freed=True


class Service(module.ShaderDebugServiceMixin):
    def __init__(self,controller):
        self.ctx=types.SimpleNamespace(IsCaptureLoaded=lambda:True,GetCaptureFilename=lambda:'fixture.rdc',
            Replay=lambda:types.SimpleNamespace(BlockInvoke=lambda callback:callback(controller)))


class ShaderDebugExportTests(unittest.TestCase):
    def test_complete_trace_preserves_nonfinite_bits_and_frees_debugger(self):
        controller=Controller()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.json'
            result=Service(controller).export_shader_debug_trace({'eid':1,'x':2,'y':3,'dest':str(path)})
            data=json.loads(path.read_text())
            self.assertTrue(result['ok']);self.assertTrue(controller.freed)
            self.assertEqual(len(data['states']),2)
            self.assertTrue(data['inputs'][0]['raw_hex'].startswith('0100c07f00000080'))
            self.assertEqual(data['inputs'][0]['float32_view'][0],'nan')

    def test_step_budget_reports_partial_and_still_frees_debugger(self):
        controller=Controller()
        with tempfile.TemporaryDirectory() as directory:
            result=Service(controller).export_shader_debug_trace({'eid':1,'x':2,'y':3,'dest':str(Path(directory)/'trace.json'),'max_steps':1})
            self.assertFalse(result['ok']);self.assertTrue(controller.freed)
            self.assertEqual(result['data']['steps'],1)

    def test_existing_file_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.json';path.write_text('keep')
            with self.assertRaises(FileExistsError):
                Service(Controller()).export_shader_debug_trace({'eid':1,'x':2,'y':3,'dest':str(path)})
            self.assertEqual(path.read_text(),'keep')


if __name__=='__main__':unittest.main()
