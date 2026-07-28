"""Register the bundled Ruri DXBC decompiler with RenderDoc."""

from pathlib import Path
import os

import qrenderdoc as qrd
import renderdoc as rd


RURI_DXBC_PROCESSOR = (
    "Ruri DXBC -> HLSL",
    rd.ShaderEncoding.DXBC,
    rd.ShaderEncoding.HLSL,
    "{input_file} {output_file} --format dxbc --shader-model 50",
)


def bundled_decompiler_exe():
    override = os.environ.get("RURI_DXBC_DECOMPILER_EXE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "tools" / "ruri_shader_decompiler" / "Ruri.ShaderDecompiler.exe"


def _is_dxbc_hlsl_processor(tool):
    return (
        int(getattr(tool, "input", -1)) == int(rd.ShaderEncoding.DXBC)
        and int(getattr(tool, "output", -1)) == int(rd.ShaderEncoding.HLSL)
    )


def _same_processor(tool, name, exe):
    if str(getattr(tool, "name", "")) == name:
        return True

    tool_exe = Path(str(getattr(tool, "executable", "")))
    try:
        tool_exe = tool_exe.resolve()
    except Exception:
        tool_exe = Path(os.path.abspath(str(tool_exe)))

    try:
        exe = exe.resolve()
    except Exception:
        exe = Path(os.path.abspath(str(exe)))

    return os.path.normcase(str(tool_exe)) == os.path.normcase(str(exe))


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


def install_ruri_dxbc_processor(ctx):
    exe = bundled_decompiler_exe()
    if not exe.exists():
        print("[renderdoc_mcp_bridge] Ruri DXBC decompiler not found: {}".format(exe))
        return False

    config = ctx.Config()
    processors = config.ShaderProcessors
    changed = False
    name, input_encoding, output_encoding, args = RURI_DXBC_PROCESSOR

    kept = []
    existing = None
    for tool in processors:
        if _is_dxbc_hlsl_processor(tool):
            if existing is None and _same_processor(tool, name, exe):
                existing = tool
                kept.append(tool)
            else:
                changed = True
            continue
        kept.append(tool)

    if existing is None:
        existing = qrd.ShaderProcessingTool()
        kept.append(existing)
        changed = True

    changed = _set_processor(existing, exe, name, input_encoding, output_encoding, args) or changed
    if changed:
        config.ShaderProcessors = kept
        config.Save()
        print("[renderdoc_mcp_bridge] registered bundled Ruri DXBC shader processor")

    return changed
