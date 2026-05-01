import io
import sys
import unittest
from unittest.mock import patch

from renderdoc_mcp import cli


class CliTests(unittest.TestCase):
    @patch("renderdoc_mcp.cli.OfflineBootstrapAdapter")
    def test_main_returns_zero_for_success_dict_response(self, adapter_cls):
        adapter_cls.return_value.get_capture_status.return_value = {"ok": True}

        with patch.object(sys, "argv", ["renderdoc-mcp", "get-capture-status"]):
            with patch("sys.stdout", new=io.StringIO()):
                exit_code = cli.main()

        self.assertEqual(exit_code, 0)
