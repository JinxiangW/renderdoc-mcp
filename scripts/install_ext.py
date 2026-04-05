"""Install the RenderDoc MCP bridge extension into the qrenderdoc user extensions folder."""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil

EXT_NAME = "renderdoc_mcp_bridge"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "bridge_extension" / EXT_NAME
    dst_root = Path(os.environ["APPDATA"]) / "qrenderdoc" / "extensions"
    dst = dst_root / EXT_NAME
    dst_root.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    ui_config = Path(os.environ["APPDATA"]) / "qrenderdoc" / "UI.config"
    if ui_config.exists():
        data = json.loads(ui_config.read_text(encoding="utf-8"))
    else:
        data = {}

    always = data.setdefault("AlwaysLoad_Extensions", [])
    if EXT_NAME not in always:
        always.append(EXT_NAME)
        data["AlwaysLoad_Extensions"] = sorted(always)
        ui_config.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    print(f"Installed {EXT_NAME} to {dst}")
    print(f"Updated AlwaysLoad_Extensions in {ui_config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
