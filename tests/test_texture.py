import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "bridge_extension"
    / "renderdoc_mcp_bridge"
    / "domains"
    / "texture.py"
)
_SPEC = importlib.util.spec_from_file_location("renderdoc_mcp_bridge_texture", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)
TextureServiceMixin = _MODULE.TextureServiceMixin


class _FakeTexture:
    def __init__(self, resource_id):
        self.resourceId = resource_id


class _FakeController:
    def __init__(self, textures, names):
        self._textures = textures
        self._names = names

    def GetTextures(self):
        return self._textures

    def GetResourceName(self, rid):
        return self._names.get(rid, "")


class TextureSelectionTests(unittest.TestCase):
    def test_select_texture_matches_resource_name_filter(self):
        tex = _FakeTexture("ResourceId::123")
        controller = _FakeController([tex], {"ResourceId::123": "GBuffer_Albedo"})

        selected = TextureServiceMixin._select_texture(controller, None, "albedo")

        self.assertIs(selected, tex)
