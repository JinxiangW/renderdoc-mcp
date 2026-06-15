"""RenderDoc MCP bridge extension."""

from .request_handler import RequestHandler
from .server import BridgeServer

try:
    from .acat_dxbc_processor import install_acat_dxbc_processor
    _acat_import_error = None
except Exception as exc:
    install_acat_dxbc_processor = None
    _acat_import_error = exc

_ctx = None
_server = None


def register(version, ctx):
    """RenderDoc extension entrypoint."""
    global _ctx, _server
    _ctx = ctx
    if install_acat_dxbc_processor is not None:
        try:
            install_acat_dxbc_processor(ctx)
        except Exception as exc:
            print("[renderdoc_mcp_bridge] failed to register ACat DXBC shader processor: {}".format(exc))
    elif _acat_import_error is not None:
        print("[renderdoc_mcp_bridge] failed to import ACat DXBC processor installer: {}".format(_acat_import_error))
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
