"""Observe-layer composition for the live bridge."""

from .domains.base import BridgeService
from .domains.capture import CaptureStatusService
from .domains.export import ExportServiceMixin
from .domains.mesh import MeshServiceMixin
from .domains.packets import PacketServiceMixin
from .domains.pipeline import PipelineStateServiceMixin
from .domains.resource_support import ResourceSupportMixin
from .domains.search import EventSearchMixin
from .domains.shader import ShaderServiceMixin
from .domains.texture import TextureServiceMixin


class ObserveService(
    EventSearchMixin,
    PacketServiceMixin,
    PipelineStateServiceMixin,
    ShaderServiceMixin,
    TextureServiceMixin,
    ExportServiceMixin,
    MeshServiceMixin,
    ResourceSupportMixin,
    BridgeService,
):
    """Compose observe-only live bridge services from domain mixins."""
