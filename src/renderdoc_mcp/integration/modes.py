"""Supported integration host modes."""

from __future__ import annotations

from enum import StrEnum


class HostMode(StrEnum):
    UI_EXTENSION = "ui_extension"
    OFFLINE_HOST = "offline_host"
