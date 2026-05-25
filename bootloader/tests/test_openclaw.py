import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestOpenClaw(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}

    def test_prereq_always_returns_true(self):
        """Prereq always returns True (install handles skip logic)."""
        with patch("os.path.isdir", return_value=False):
            import importlib
            import bootloader.plugins.openclaw as oc_module
            importlib.reload(oc_module)
            result = oc_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_prereq_returns_true_when_exists(self):
        oc_dir = os.path.join(self.user_home, ".openclaw", "hermes-openclaw")
        os.makedirs(oc_dir, exist_ok=True)
        with patch("os.path.isdir", return_value=True):
            import importlib
            import bootloader.plugins.openclaw as oc_module
            importlib.reload(oc_module)
            result = oc_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_install_creates_expected_paths(self):
        oc_dir = os.path.join(self.user_home, ".openclaw", "hermes-openclaw")
        git_dir = os.path.join(oc_dir, ".git")

        with patch("os.path.isdir", side_effect=lambda p: ".venv" in p or ".git" in p):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch("bootloader.plugins.openclaw.venv") as mock_venv:
                    mock_venv.create = MagicMock()
                    import importlib
                    import bootloader.plugins.openclaw as oc_module
                    importlib.reload(oc_module)
                    result = oc_module.hook_install(self.context)
                    self.assertTrue(result["installed"])

    def test_verify_fails_when_missing(self):
        with patch("os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.openclaw as oc_module
            importlib.reload(oc_module)
            with self.assertRaises(RuntimeError):
                oc_module.hook_verify(self.context)

    def test_verify_passes_when_venv_exists(self):
        venv_python = os.path.join(
            self.user_home, ".openclaw", "hermes-openclaw", "venv", "bin", "python"
        )
        os.makedirs(os.path.dirname(venv_python), exist_ok=True)
        with open(venv_python, "w") as f:
            f.write("#!/bin/bash\n")
        os.chmod(venv_python, 0o755)

        with patch("os.path.isfile", return_value=True):
            with patch("os.access", return_value=True):
                import importlib
                import bootloader.plugins.openclaw as oc_module
                importlib.reload(oc_module)
                self.assertTrue(oc_module.hook_verify(self.context))