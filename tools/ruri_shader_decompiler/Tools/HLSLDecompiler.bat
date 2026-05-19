@echo off
setlocal enabledelayedexpansion

: Decompile DXBC/DXIL/SPIR-V to HLSL
"%~dp0HLSLDecompiler.exe" %*

: Redirect to stdout
for %%f in ("%1") do type "%%~dpnf.hlsl"

endlocal
