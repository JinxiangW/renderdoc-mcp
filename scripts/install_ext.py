"""Install the RenderDoc MCP bridge extension into the qrenderdoc user extensions folder."""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil

EXT_NAME = "renderdoc_mcp_bridge"
ACAT_PACKAGE = "acat_dxbc_decompiler"
ACAT_TOOL_ENTRY = {
    "args": "{input_file} -dxbc {output_file}",
    "input": 1,  # DXBC
    "name": "ACat DXBC -> HLSL",
    "output": 5,  # HLSL
    "tool": 0,
}


def remove_tree_inside(path: Path, parent: Path) -> None:
    resolved_path = path.resolve()
    resolved_parent = parent.resolve()
    if not resolved_path.is_relative_to(resolved_parent):
        raise RuntimeError(f"Refusing to remove path outside {resolved_parent}: {resolved_path}")
    shutil.rmtree(resolved_path)


def install_bundled_decompiler(repo_root: Path, extension_dir: Path) -> Path | None:
    src = repo_root / "tools" / ACAT_PACKAGE
    if not src.exists():
        return None

    dst = extension_dir / "tools" / ACAT_PACKAGE
    if dst.exists():
        remove_tree_inside(dst, extension_dir)
    shutil.copytree(src, dst)
    return dst / "HLSLDecompiler.exe"


def should_remove_legacy_processor(tool: dict) -> bool:
    token = "r" + "uri"
    name = str(tool.get("name", "")).lower()
    executable = str(tool.get("executable", "")).lower()
    return token in name or token in executable


def configure_ui(ui_config: Path, decompiler_exe: Path | None) -> bool:
    if ui_config.exists():
        data = json.loads(ui_config.read_text(encoding="utf-8-sig"))
    else:
        data = {}

    changed = False
    always = data.setdefault("AlwaysLoad_Extensions", [])
    if EXT_NAME not in always:
        always.append(EXT_NAME)
        data["AlwaysLoad_Extensions"] = sorted(always)
        changed = True

    if decompiler_exe is not None:
        processors = data.setdefault("ShaderProcessors", [])
        cleaned = [tool for tool in processors if not should_remove_legacy_processor(tool)]
        if len(cleaned) != len(processors):
            processors = cleaned
            data["ShaderProcessors"] = processors
            changed = True

        desired = dict(ACAT_TOOL_ENTRY)
        desired["executable"] = str(decompiler_exe)
        existing = next((tool for tool in processors if tool.get("name") == desired["name"]), None)
        if existing is None:
            processors.append(desired)
            changed = True
        else:
            for key, value in desired.items():
                if existing.get(key) != value:
                    existing[key] = value
                    changed = True

    if changed:
        ui_config.parent.mkdir(parents=True, exist_ok=True)
        ui_config.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    return changed


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "bridge_extension" / EXT_NAME
    dst_root = Path(os.environ["APPDATA"]) / "qrenderdoc" / "extensions"
    dst = dst_root / EXT_NAME
    dst_root.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        remove_tree_inside(dst, dst_root)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    decompiler_exe = install_bundled_decompiler(repo_root, dst)
    ui_config = Path(os.environ["APPDATA"]) / "qrenderdoc" / "UI.config"
    configure_ui(ui_config, decompiler_exe)

    print(f"Installed {EXT_NAME} to {dst}")
    if decompiler_exe is not None:
        print(f"Installed bundled ACat DXBC decompiler to {decompiler_exe.parent}")
    else:
        print(f"Bundled ACat DXBC decompiler not found under {repo_root / 'tools' / ACAT_PACKAGE}")
    print(f"Updated AlwaysLoad_Extensions in {ui_config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
