"""Shared compact response contract references."""

from __future__ import annotations

from typing import Any, TypedDict

DEFAULT_MODE = "summary"
DEFAULT_LIMIT = 50


class ErrorInfo(TypedDict):
    code: str
    msg: str


class MetaInfo(TypedDict, total=False):
    cap: str | None
    truncated: bool
    count: int | None
    next: int | None


class Envelope(TypedDict):
    ok: bool
    mode: str
    data: Any
    err: ErrorInfo | None
    meta: MetaInfo | None
