"""Register the bundled Ruri shader decompiler with RenderDoc."""

from pathlib import Path
import os

import qrenderdoc as qrd
import renderdoc as rd


RURI_PROCESSORS = (
    ("Ruri DXBC -> HLSL", rd.ShaderEncoding.DXBC, rd.ShaderEncoding.HLSL, "{input_file} {output_file} --shader-model 50"),
    ("Ruri DXIL -> HLSL", rd.ShaderEncoding.DXIL, rd.ShaderEncoding.HLSL, "{input_file} {output_file} --shader-model 60"),
    ("Ruri SPIR-V -> HLSL", rd.ShaderEncoding.SPIRV, rd.ShaderEncoding.HLSL, "{input_file} {output_file} --shader-model 60"),
)


def bundled_decompiler_exe():
    override = os.environ.get("RURI_SHADER_DECOMPILER_EXE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "tools" / "ruri_shader_decompiler" / "Ruri.ShaderDecompiler.exe"


def _same_processor(tool, name, input_encoding, output_encoding):
    if str(getattr(tool, "name", "")) == name:
        return True

    exe = Path(str(getattr(tool, "executable", "")))
    try:
        exe = exe.resolve()
    except Exception:
        exe = Path(os.path.abspath(str(exe)))

    ruri = bundled_decompiler_exe()
    try:
        ruri = ruri.resolve()
    except Exception:
        ruri = Path(os.path.abspath(str(ruri)))

    return (
        os.path.normcase(str(exe)) == os.path.normcase(str(ruri))
        and int(getattr(tool, "input", -1)) == int(input_encoding)
        and int(getattr(tool, "output", -1)) == int(output_encoding)
    )


def _set_processor(tool, exe, name, input_encoding, output_encoding, args):
    changed = False
    values = {
        "tool": rd.KnownShaderTool.Unknown,
        "name": name,
        "executable": str(exe),
        "args": args,
        "input": input_encoding,
        "output": output_encoding,
    }
    for key, value in values.items():
        if getattr(tool, key, None) != value:
            setattr(tool, key, value)
            changed = True
    return changed


def install_ruri_shader_processors(ctx):
    exe = bundled_decompiler_exe()
    if not exe.exists():
        print("[renderdoc_mcp_bridge] Ruri decompiler not found: {}".format(exe))
        return False

    config = ctx.Config()
    processors = config.ShaderProcessors
    changed = False

    for name, input_encoding, output_encoding, args in RURI_PROCESSORS:
        existing = None
        for tool in processors:
            if _same_processor(tool, name, input_encoding, output_encoding):
                existing = tool
                break

        if existing is None:
            tool = qrd.ShaderProcessingTool()
            _set_processor(tool, exe, name, input_encoding, output_encoding, args)
            processors.append(tool)
            changed = True
        else:
            changed = _set_processor(existing, exe, name, input_encoding, output_encoding, args) or changed

    if changed:
        config.ShaderProcessors = processors
        config.Save()
        print("[renderdoc_mcp_bridge] registered bundled Ruri shader processors")

    return changed
