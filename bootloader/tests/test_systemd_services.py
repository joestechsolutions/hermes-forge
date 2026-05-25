import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


# Import once for reference
import bootloader.plugins.systemd_services as ss_module


class TestSystemdServices(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}
        self.unit_dir = os.path.join(self.user_home, ".config", "systemd", "user")

    def test_prereq_always_true(self):
        """Prereq always returns True — install handles unit creation."""
        with patch("os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.systemd_services as m
            importlib.reload(m)
            result = m.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_prereq_true_when_all_units_exist(self):
        os.makedirs(self.unit_dir, exist_ok=True)
        for name in ss_module.UNIT_FILES:
            with open(os.path.join(self.unit_dir, name), "w") as f:
                f.write("[Unit]\n")
        import importlib
        import bootloader.plugins.systemd_services as m
        importlib.reload(m)
        result = m.hook_check_prerequisites(self.context)
        self.assertTrue(result)

    def test_install_creates_unit_files(self):
        # Pre-create actual directory structure
        os.makedirs(self.unit_dir, exist_ok=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Only patch isfile for paths that DON'T exist yet (service file check)
            # but allow existing directory to be found
            original_isfile = os.path.isfile
            with patch("os.path.isfile", side_effect=lambda p: p.endswith(".service") and original_isfile(p)):
                import importlib
                import bootloader.plugins.systemd_services as m
                importlib.reload(m)
                result = m.hook_install(self.context)
                self.assertTrue(result["installed"])
                self.assertEqual(len(result["units"]), 3)

    def test_verify_fails_when_unit_missing(self):
        with patch("os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.systemd_services as m
            importlib.reload(m)
            with self.assertRaises(RuntimeError):
                m.hook_verify(self.context)