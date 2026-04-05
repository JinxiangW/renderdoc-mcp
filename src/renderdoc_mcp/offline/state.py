"""Local persisted state for offline bootstrap."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


STATE_DIR = Path(".state")
STATE_FILE = STATE_DIR / "active_capture.json"


@dataclass(slots=True)
class ActiveCaptureState:
    cap: str
    path: str
    name: str
    size: int
    mtime: str
    thumb_path: str | None
    api: str | None = None


def load_state() -> ActiveCaptureState | None:
    if not STATE_FILE.exists():
        return None

    raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return ActiveCaptureState(**raw)


def save_state(state: ActiveCaptureState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
