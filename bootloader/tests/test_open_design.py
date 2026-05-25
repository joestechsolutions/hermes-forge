import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestOpenDesign(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}

    def test_prereq_always_true(self):
        """Prereq always returns True — install handles idempotency."""
        with patch("bootloader.plugins.open_design.os.path.isdir", return_value=False):
            import importlib
            import bootloader.plugins.open_design as od_module
            importlib.reload(od_module)
            result = od_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_prereq_true_when_exists(self):
        with patch("bootloader.plugins.open_design.os.path.isdir", return_value=True):
            import importlib
            import bootloader.plugins.open_design as od_module
            importlib.reload(od_module)
            result = od_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_install_idempotent_when_dir_already_exists(self):
        """When /srv/ai-stack/open-design exists, hook_install should git pull (skip clone)."""
        # Make isdir return True for the install dir → triggers git pull path (not makedirs)
        with patch("bootloader.plugins.open_design.os.path.isdir", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                import importlib
                import bootloader.plugins.open_design as od_module
                importlib.reload(od_module)
                result = od_module.hook_install(self.context)
                self.assertTrue(result["installed"])
                # Verify git pull was called (not makedirs/clone)
                git_pull_calls = [
                    c for c in mock_run.call_args_list
                    if c.args and "pull" in c.args[0]
                ]
                self.assertGreater(len(git_pull_calls), 0)

    def test_install_creates_when_dir_missing(self):
        """When /srv/ai-stack/open-design doesn't exist, hook_install should clone."""
        with patch("bootloader.plugins.open_design.os.path.isdir", return_value=False):
            with patch("bootloader.plugins.open_design.os.makedirs"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    import importlib
                    import bootloader.plugins.open_design as od_module
                    importlib.reload(od_module)
                    result = od_module.hook_install(self.context)
                    self.assertTrue(result["installed"])

    def test_verify_fails_when_node_modules_missing(self):
        with patch("bootloader.plugins.open_design.os.path.isdir", return_value=False):
            import importlib
            import bootloader.plugins.open_design as od_module
            importlib.reload(od_module)
            with self.assertRaises(RuntimeError):
                od_module.hook_verify(self.context)

    def test_verify_passes_when_node_modules_exists(self):
        with patch("bootloader.plugins.open_design.os.path.isdir", return_value=True):
            import importlib
            import bootloader.plugins.open_design as od_module
            importlib.reload(od_module)
            self.assertTrue(od_module.hook_verify(self.context))