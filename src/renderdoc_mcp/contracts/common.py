"""Shared compact response contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_MODE = "summary"
DEFAULT_LIMIT = 50


@dataclass(slots=True)
class ErrorInfo:
    code: str
    msg: str


@dataclass(slots=True)
class MetaInfo:
    cap: str | None = None
    truncated: bool = False
    count: int | None = None
    next: int | None = None


@dataclass(slots=True)
class Envelope:
    ok: bool
    mode: str = DEFAULT_MODE
    data: Any = None
    err: ErrorInfo | None = None
    meta: MetaInfo | None = None
