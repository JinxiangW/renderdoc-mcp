# Ruri Shader Decompiler

Use this reference when HLSL decompilation is needed in addition to RenderDoc disassembly.

## Install

From the repository root:

```powershell
py -3 scripts\install_ext.py
```

The installer:

- copies `bridge_extension/renderdoc_mcp_bridge` to `%APPDATA%\qrenderdoc\extensions\renderdoc_mcp_bridge`
- copies `tools/ruri_shader_decompiler` into the installed extension
- adds `renderdoc_mcp_bridge` to `AlwaysLoad_Extensions` in `%APPDATA%\qrenderdoc\UI.config`
- registers these shader processors:
  - `Ruri DXBC -> HLSL`
  - `Ruri DXIL -> HLSL`
  - `Ruri SPIR-V -> HLSL`

Restart RenderDoc/qrenderdoc after installing.

## Requirements

- Windows
- Python launcher available as `py -3`
- .NET 8 runtime, because `Ruri.ShaderDecompiler.exe` is framework-dependent

The default installed executable path is:

```text
%APPDATA%\qrenderdoc\extensions\renderdoc_mcp_bridge\tools\ruri_shader_decompiler\Ruri.ShaderDecompiler.exe
```

To use a different executable, set:

```powershell
$env:RURI_SHADER_DECOMPILER_EXE = "C:\path\to\Ruri.ShaderDecompiler.exe"
```

## Use From RenderDoc

After restart, open a capture and use RenderDoc's shader edit/decompile menu. Choose the processor that matches the shader bytecode encoding:

- DXBC: `Ruri DXBC -> HLSL`
- DXIL: `Ruri DXIL -> HLSL`
- SPIR-V: `Ruri SPIR-V -> HLSL`

Use decompiled HLSL as supporting evidence. Keep `inspect_shader`, `get_shader_disasm`, bindings, IO, and resource usage as the primary evidence path for reports.

## Reverse-Action Export Rule

For `reverse-action`, export the inspected action shader stages to HLSL before writing the report:

- use the user-provided action working directory when present
- otherwise use the current report/bundle directory for the action, or `.state/action_reverse/<capture-or-session>/eid_<eid>/`
- for draws, export `vs` and `ps` unless a stage is proven irrelevant
- for dispatches, export `cs`
- use predictable names such as `eid_<eid>_<stage>_<shader-name-or-sid>.hlsl`
- keep any annotated copy or notes beside the exported HLSL, for example `eid_<eid>_<stage>.annotated.hlsl` or `eid_<eid>_<stage>.notes.md`

Annotate HLSL by large functional blocks, not line-by-line translation. Also annotate important input resources near declarations or in the notes file with slot, RID/name, format/dimensions when available, actual code role, and semantic status.

If Ruri output conflicts with RenderDoc disassembly, treat HLSL as a readable aid and keep binding/IO facts plus disassembly as the final authority. If Ruri is unavailable or fails, state that in the report limits and continue with `get_shader_disasm`.

## Use From CLI

The executable accepts input bytecode path, output HLSL path, and shader model:

```powershell
& "$env:APPDATA\qrenderdoc\extensions\renderdoc_mcp_bridge\tools\ruri_shader_decompiler\Ruri.ShaderDecompiler.exe" input.dxbc output.hlsl --shader-model 50
```

Shader model defaults by encoding:

- DXBC: `--shader-model 50`
- DXIL: `--shader-model 60`
- SPIR-V: `--shader-model 60`

## Troubleshooting

- If menu entries are missing, rerun `py -3 scripts\install_ext.py` and restart qrenderdoc.
- If the bridge logs `Ruri decompiler not found`, check the installed `tools\ruri_shader_decompiler` folder or set `RURI_SHADER_DECOMPILER_EXE`.
- If execution fails immediately, verify the .NET 8 runtime is installed.
- If output looks incomplete, compare with `get_shader_disasm` and treat the decompiler output as a hint, not final proof.
