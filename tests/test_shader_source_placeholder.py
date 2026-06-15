import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _FakeShaderCompileFlag:
    def __init__(self):
        self.name = ""
        self.value = ""


class _FakeShaderCompileFlags:
    def __init__(self):
        self.flags = []


def _install_fake_renderdoc():
    sys.modules.setdefault(
        "renderdoc",
        types.SimpleNamespace(
            ShaderStage=SimpleNamespace(
                Vertex="vs",
                Hull="hs",
                Domain="ds",
                Geometry="gs",
                Pixel="ps",
                Compute="cs",
            ),
            ShaderCompileFlag=_FakeShaderCompileFlag,
            ShaderCompileFlags=_FakeShaderCompileFlags,
            ShaderEncoding=SimpleNamespace(HLSL=5, DXBC=1, DXIL=6, GLSL=2, SPIRV=3, Slang=9),
        ),
    )


_install_fake_renderdoc()

shader_module = importlib.import_module("bridge_extension.renderdoc_mcp_bridge.domains.shader")
base_module = importlib.import_module("bridge_extension.renderdoc_mcp_bridge.domains.base")

ShaderServiceMixin = shader_module.ShaderServiceMixin
BridgeService = base_module.BridgeService


class _FakePipe:
    def __init__(self, reflection):
        self._reflection = reflection

    def GetShader(self, _stage):
        return "ResourceId::1"

    def GetShaderEntryPoint(self, _stage):
        return "main"

    def GetShaderReflection(self, _stage):
        return self._reflection


class _FakeController:
    def __init__(self, reflection):
        self._pipe = _FakePipe(reflection)

    def SetFrameEvent(self, _eid, _force):
        return None

    def GetPipelineState(self):
        return self._pipe


class _FakeReplay:
    def __init__(self, reflection):
        self._controller = _FakeController(reflection)

    def BlockInvoke(self, fn):
        fn(self._controller)


class _FakeCtx:
    def __init__(self, reflection, processors=None):
        self._reflection = reflection
        self._processors = processors or []

    def IsCaptureLoaded(self):
        return True

    def Replay(self):
        return _FakeReplay(self._reflection)

    def GetResourceNameUnsuffixed(self, _rid):
        return ""

    def GetResourceName(self, _rid):
        return ""

    def Config(self):
        return SimpleNamespace(ShaderProcessors=self._processors)


class _TestShaderService(ShaderServiceMixin, BridgeService):
    def _shader_disasm(self, controller, pipe, stage_enum, reflection):
        return {
            "target": "DXBC",
            "text": "ps_5_0\nret",
            "line_count": 2,
            "error": None,
        }


class ShaderSourcePlaceholderTests(unittest.TestCase):
    def test_get_shader_source_rejects_false_placeholder(self):
        reflection = SimpleNamespace(
            debugInfo=SimpleNamespace(
                files=[SimpleNamespace(filename=-1, contents=False)],
                sourceDebugInformation=False,
                editBaseFile=-1,
                debuggable=True,
                debugStatus="",
                compiler="KnownShaderTool.fxc",
                encoding="Unknown",
            ),
            entryPoint="main",
        )
        service = _TestShaderService(_FakeCtx(reflection))

        result = service.get_shader_source({"eid": 14487, "stage": "ps"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["err"]["code"], "shader_source_unavailable")

    def test_get_shader_code_falls_back_to_disasm_for_false_placeholder(self):
        reflection = SimpleNamespace(
            debugInfo=SimpleNamespace(
                files=[SimpleNamespace(filename=-1, contents=False)],
                sourceDebugInformation=False,
                editBaseFile=-1,
                debuggable=True,
                debugStatus="",
                compiler="KnownShaderTool.fxc",
                encoding="Unknown",
            ),
            entryPoint="main",
        )
        service = _TestShaderService(_FakeCtx(reflection))

        result = service.get_shader_code({"eid": 14487, "stage": "ps"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["kind"], "disasm")
        self.assertEqual(result["data"]["debug"]["has_source"], False)
        self.assertEqual(result["data"]["code"]["text"], "ps_5_0\nret")

    def test_source_debug_information_still_works_when_file_entry_is_invalid(self):
        reflection = SimpleNamespace(
            debugInfo=SimpleNamespace(
                files=[SimpleNamespace(filename=-1, contents=False)],
                sourceDebugInformation="float4 main() : SV_Target { return 0; }\n",
                editBaseFile="DeferredLighting.ps.hlsl",
                debuggable=True,
                debugStatus="",
                compiler="KnownShaderTool.fxc",
                encoding="HLSL",
            ),
            entryPoint="main",
        )
        service = _TestShaderService(_FakeCtx(reflection))

        result = service.get_shader_code({"eid": 14487, "stage": "ps"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["kind"], "source")
        self.assertEqual(result["data"]["file"]["filename"], "DeferredLighting.ps.hlsl")
        self.assertIn("float4 main()", result["data"]["code"]["text"])

    def test_export_shader_decompiled_hlsl_uses_registered_processor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = Path(temp_dir) / "fake_decompiler.exe"
            exe.write_bytes(b"")
            dest = Path(temp_dir) / "shader.hlsl"
            processor = SimpleNamespace(
                name="Fake DXBC -> HLSL",
                executable=str(exe),
                args="{input_file} {output_file} --shader-model 50",
                input=1,
                output=5,
            )
            reflection = SimpleNamespace(
                rawBytes=b"DXBC1234",
                encoding=1,
                entryPoint="main",
                debugInfo=None,
            )
            service = _TestShaderService(_FakeCtx(reflection, processors=[processor]))

            def fake_run(argv, **_kwargs):
                output_path = Path(argv[2])
                output_path.write_text("float4 main() : SV_Target { return 1; }\n", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

            with patch("bridge_extension.renderdoc_mcp_bridge.domains.shader.subprocess.run", fake_run):
                result = service.export_shader_decompiled_hlsl(
                    {
                        "eid": 14487,
                        "stage": "ps",
                        "dest": str(dest),
                    }
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["data"]["source_encoding"], "DXBC")
            self.assertEqual(result["data"]["processor"]["name"], "Fake DXBC -> HLSL")
            self.assertEqual(result["data"]["dest"], str(dest.resolve()))
            self.assertEqual(result["data"]["line_count"], 1)
            self.assertTrue(dest.exists())

    def test_hlsl_decompiler_selection_prefers_acat_by_default(self):
        service = _TestShaderService(_FakeCtx(SimpleNamespace()))
        generic_tool = {
            "name": "Generic DXBC -> HLSL",
            "executable": "C:/Tools/OtherDecompiler.exe",
            "args": "{input_file} {output_file}",
            "input": 1,
            "output": 5,
        }
        acat_tool = {
            "name": "ACat DXBC -> HLSL",
            "executable": "C:/Tools/HLSLDecompiler.exe",
            "args": "{input_file} -dxbc {output_file}",
            "input": 1,
            "output": 5,
        }

        with patch.object(service, "_shader_processors", return_value=[generic_tool, acat_tool]):
            selected = service._select_hlsl_decompiler(1)

        self.assertEqual(selected, acat_tool)
