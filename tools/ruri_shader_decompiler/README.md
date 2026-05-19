# Bundled Ruri Shader Decompiler

This directory is a portable copy of the Ruri shader decompiler release output.

Origin:

- `C:\RuriRetroWorks\ShaderReverseLab\Ruri.ShaderDecompiler\bin\Release\net8.0`

Install:

```powershell
py -3 scripts\install_ext.py
```

The installer copies this package into the qrenderdoc bridge extension and registers these RenderDoc shader processing tools:

- `Ruri DXBC -> HLSL`
- `Ruri DXIL -> HLSL`
- `Ruri SPIR-V -> HLSL`

The executable is framework-dependent and expects a .NET 8 runtime on the machine.
