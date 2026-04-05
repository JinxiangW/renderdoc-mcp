"""RenderDoc MCP bridge extension."""

from .request_handler import RequestHandler
from .server import BridgeServer

_ctx = None
_server = None


def register(version, ctx):
    """RenderDoc extension entrypoint."""
    global _ctx, _server
    _ctx = ctx
    handler = RequestHandler(ctx)
    _server = BridgeServer(handler)
    _server.start()
    print("[renderdoc_mcp_bridge] loaded for RenderDoc {}".format(version))


def unregister():
    """RenderDoc extension unload hook."""
    global _server
    if _server is not None:
        _server.stop()
        _server = None
    print("[renderdoc_mcp_bridge] unloaded")
