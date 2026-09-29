import importlib.util
from pathlib import Path
import sys
import types
import unittest


_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "bridge_extension"
    / "renderdoc_mcp_bridge"
    / "domains"
    / "texture.py"
)
_PACKAGE = "texture_selection_test_domains"
_NAMES = ("renderdoc", _PACKAGE, _PACKAGE + ".inventory")
_SAVED = {name: sys.modules.get(name) for name in _NAMES}
sys.modules["renderdoc"] = types.ModuleType("renderdoc")
sys.modules[_PACKAGE] = types.ModuleType(_PACKAGE)
sys.modules[_PACKAGE].__path__ = [str(_MODULE_PATH.parent)]
try:
    _SPEC = importlib.util.spec_from_file_location(_PACKAGE + ".texture", _MODULE_PATH)
    _MODULE = importlib.util.module_from_spec(_SPEC)
    assert _SPEC is not None and _SPEC.loader is not None
    _SPEC.loader.exec_module(_MODULE)
finally:
    for name, previous in _SAVED.items():
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
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
