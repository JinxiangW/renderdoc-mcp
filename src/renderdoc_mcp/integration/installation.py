"""Local RenderDoc installation discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True, slots=True)
class RenderDocInstallation:
    root: Path
    renderdoccmd: Path
    qrenderdoc: Path | None
    renderdoc_dll: Path | None


def _candidate_roots() -> list[Path]:
    candidates: list[Path] = []

    env_root = os.environ.get("RENDERDOC_PATH")
    if env_root:
        candidates.append(Path(env_root))

    candidates.append(Path(r"C:\Program Files\RenderDoc"))
    candidates.append(Path(r"C:\Program Files (x86)\RenderDoc"))

    return candidates


def discover_installation() -> RenderDocInstallation:
    for root in _candidate_roots():
        cmd = root / "renderdoccmd.exe"
        if cmd.exists():
            qrd = root / "qrenderdoc.exe"
            dll = root / "renderdoc.dll"
            return RenderDocInstallation(
                root=root,
                renderdoccmd=cmd,
                qrenderdoc=qrd if qrd.exists() else None,
                renderdoc_dll=dll if dll.exists() else None,
            )

    raise FileNotFoundError(
        "Could not find a local RenderDoc installation. Set RENDERDOC_PATH if needed."
    )
