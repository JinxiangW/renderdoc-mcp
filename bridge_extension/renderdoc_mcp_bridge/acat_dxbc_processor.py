"""Register the bundled ACat DXBC decompiler with RenderDoc."""

from pathlib import Path
import os

import qrenderdoc as qrd
import renderdoc as rd


ACAT_DXBC_PROCESSOR = (
    "ACat DXBC -> HLSL",
    rd.ShaderEncoding.DXBC,
    rd.ShaderEncoding.HLSL,
    "{input_file} -dxbc {output_file}",
)


def bundled_decompiler_exe():
    override = os.environ.get("ACAT_DXBC_DECOMPILER_EXE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "tools" / "acat_dxbc_decompiler" / "HLSLDecompiler.exe"


def _same_processor(tool, name, input_encoding, output_encoding):
    if str(getattr(tool, "name", "")) == name:
        return True

    exe = Path(str(getattr(tool, "executable", "")))
    try:
        exe = exe.resolve()
    except Exception:
        exe = Path(os.path.abspath(str(exe)))

    acat = bundled_decompiler_exe()
    try:
        acat = acat.resolve()
    except Exception:
        acat = Path(os.path.abspath(str(acat)))

    return (
        os.path.normcase(str(exe)) == os.path.normcase(str(acat))
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


def install_acat_dxbc_processor(ctx):
    exe = bundled_decompiler_exe()
    if not exe.exists():
        print("[renderdoc_mcp_bridge] ACat DXBC decompiler not found: {}".format(exe))
        return False

    config = ctx.Config()
    processors = config.ShaderProcessors
    changed = False
    name, input_encoding, output_encoding, args = ACAT_DXBC_PROCESSOR

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
        print("[renderdoc_mcp_bridge] registered bundled ACat DXBC shader processor")

    return changed
