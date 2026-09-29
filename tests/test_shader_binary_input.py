from pathlib import Path
import tempfile
import unittest
from tests.test_shader_source_placeholder import shader_module as module

class ShaderBinaryInputTests(unittest.TestCase):
    def test_dxbc_non_utf8_and_zero_bytes_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'probe.dxbc';expected=b'DXBC'+bytes(range(256));path.write_bytes(expected)
            actual,error=module.ShaderServiceMixin._read_shader_source_from_params({'source_path':str(path),'source_encoding':'dxbc'})
            self.assertIsNone(error);self.assertEqual(actual,expected)
    def test_text_path_remains_utf8_bom_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'shader.hlsl';path.write_text('float4 main(){return 1;}',encoding='utf-8-sig')
            actual,error=module.ShaderServiceMixin._read_shader_source_from_params({'source_path':str(path)})
            self.assertIsNone(error);self.assertIsInstance(actual,str);self.assertTrue(actual.startswith('float4'))
    def test_binary_as_text_and_invalid_header_are_rejected(self):
        actual,error=module.ShaderServiceMixin._read_shader_source_from_params({'source':'DXBC','source_encoding':'dxbc'});self.assertIsNone(actual);self.assertIn('source_path',error)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.dxbc';path.write_bytes(b'not bytecode'*8)
            actual,error=module.ShaderServiceMixin._read_shader_source_from_params({'source_path':str(path),'source_encoding':'dxbc'});self.assertIsNone(actual);self.assertIn('header',error)

if __name__=='__main__':unittest.main()
