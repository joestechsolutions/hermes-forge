import subprocess
import unittest
from unittest.mock import patch, MagicMock


class TestPnpm(unittest.TestCase):
    def test_prereq_pass_when_pnpm_exists(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            import importlib
            import bootloader.plugins.pnpm as pnpm_module
            importlib.reload(pnpm_module)
            result = pnpm_module.hook_check_prerequisites({})
            self.assertTrue(result)

    def test_prereq_fail_when_pnpm_missing(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "which")
            import importlib
            import bootloader.plugins.pnpm as pnpm_module
            importlib.reload(pnpm_module)
            result = pnpm_module.hook_check_prerequisites({})
            self.assertFalse(result)

    def test_install_idempotent(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            import importlib
            import bootloader.plugins.pnpm as pnpm_module
            importlib.reload(pnpm_module)
            r1 = pnpm_module.hook_install({})
            r2 = pnpm_module.hook_install({})
            self.assertTrue(r1.get("installed"))
            self.assertTrue(r2.get("skipped", False))

    def test_verify_passes(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"9.0.0\n")
            import importlib
            import bootloader.plugins.pnpm as pnpm_module
            importlib.reload(pnpm_module)
            self.assertTrue(pnpm_module.hook_verify({}))