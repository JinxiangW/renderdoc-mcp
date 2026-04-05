"""Bridge abstraction for communication with a RenderDoc integration host."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass(slots=True)
class BridgeRequest:
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(slots=True)
class BridgeResponse:
    ok: bool
    result: Any = None
    error: dict[str, Any] | None = None


class RenderDocBridge:
    """Abstract bridge interface."""

    def call(self, request: BridgeRequest) -> BridgeResponse:
        raise NotImplementedError("Bridge transport is not implemented yet")
