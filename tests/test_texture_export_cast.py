import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest

previous=sys.modules.get('renderdoc')
casts=types.SimpleNamespace(**{name:name for name in ('Typeless','Float','UNorm','SNorm','UInt','SInt','Depth','Double','UScaled','SScaled')})
stub=types.SimpleNamespace(CompType=casts,TextureSave=lambda:types.SimpleNamespace(slice=types.SimpleNamespace()),FileType=types.SimpleNamespace(DDS='DDS',PNG='PNG',HDR='HDR'),AlphaMapping=types.SimpleNamespace(Preserve='Preserve'))
sys.modules['renderdoc']=stub
try:
    path=Path(__file__).resolve().parents[1]/'bridge_extension/renderdoc_mcp_bridge/domains/export.py'
    spec=importlib.util.spec_from_file_location('texture_export_cast_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
finally:
    if previous is None:sys.modules.pop('renderdoc',None)
    else:sys.modules['renderdoc']=previous

class Controller:
    def __init__(self):self.saves=[]
    def GetTextures(self):return [types.SimpleNamespace(resourceId='ResourceId::1')]
    def SaveTexture(self,settings,path):self.saves.append(settings);Path(path).write_bytes(b'payload');return 'OK'

class Service(module.ExportServiceMixin):
    def _resolve_export_path(self,dest,prefix,rid,eid,ext,overwrite):
        if Path(dest).exists() and not overwrite:raise FileExistsError(dest)
        return dest

class TextureExportCastTests(unittest.TestCase):
    def test_action_metadata_fast_path_selects_requested_event_before_saving(self):
        with tempfile.TemporaryDirectory() as directory:
            class ReplayController(Controller):
                def __init__(self):super().__init__();self.event=3;self.selections=[]
                def SetFrameEvent(self,event,force):self.event=event;self.selections.append((event,force))
                def SaveTexture(self,settings,path):Path(path).write_bytes(str(self.event).encode());return 'OK'
            controller=ReplayController();service=Service()
            service.ctx=types.SimpleNamespace(GetAction=lambda eid:types.SimpleNamespace(outputs=['ResourceId::1'],depthOut='ResourceId::1'),GetResourceName=lambda rid:'target',Replay=lambda:types.SimpleNamespace(BlockInvoke=lambda callback:callback(controller)))
            dest=Path(directory)/'after.dds'
            result=service.save_event_output_texture({'eid':17,'output_index':0,'format':'DDS','dest':str(dest)})
            self.assertTrue(result['ok']);self.assertEqual(dest.read_bytes(),b'17');self.assertEqual(controller.selections,[(17,True)])
    def test_depth_fast_path_selects_event(self):
        selections=[];service=Service();service.ctx=types.SimpleNamespace(GetAction=lambda eid:types.SimpleNamespace(depthOut='ResourceId::1'))
        controller=types.SimpleNamespace(SetFrameEvent=lambda eid,force:selections.append((eid,force)))
        self.assertEqual(service._resolve_event_output_rid(controller,9,0,True),'ResourceId::1')
        self.assertEqual(selections,[(9,True)])
    def test_pipeline_fallback_selects_once(self):
        selections=[];service=Service();service.ctx=types.SimpleNamespace(GetAction=lambda eid:None)
        pipeline=types.SimpleNamespace(GetOutputTargets=lambda:[types.SimpleNamespace(resource='ResourceId::1')])
        controller=types.SimpleNamespace(SetFrameEvent=lambda eid,force:selections.append((eid,force)),GetPipelineState=lambda:pipeline)
        self.assertEqual(service._resolve_event_output_rid(controller,11,0,False),'ResourceId::1');self.assertEqual(selections,[(11,True)])
    def test_explicit_unorm_reaches_save_api_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            controller=Controller();result=Service()._save_texture_resource(controller,'ResourceId::1','DDS',str(Path(directory)/'depth.dds'),7,False,'texture',type_cast='unorm')
            self.assertIsNotNone(result['path']);self.assertEqual(result['type_cast'],'UNorm');self.assertEqual(controller.saves[0].typeCast,'UNorm');self.assertEqual(controller.saves[0].mip,-1);self.assertEqual(controller.saves[0].slice.sliceIndex,-1)
    def test_legacy_default_remains_typeless(self):
        with tempfile.TemporaryDirectory() as directory:
            controller=Controller();result=Service()._save_texture_resource(controller,'ResourceId::1','DDS',str(Path(directory)/'legacy.dds'),7,False,'texture')
            self.assertEqual(result['type_cast'],'Typeless');self.assertEqual(controller.saves[0].typeCast,'Typeless')
    def test_invalid_cast_does_not_create_or_overwrite_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'keep.dds';path.write_bytes(b'keep');controller=Controller();result=Service()._save_texture_resource(controller,'ResourceId::1','DDS',str(path),7,True,'texture',type_cast='R16_MAGIC')
            self.assertIsNone(result['path']);self.assertIn('Unsupported',result['error']);self.assertEqual(controller.saves,[]);self.assertEqual(path.read_bytes(),b'keep')

if __name__=='__main__':unittest.main()
