import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestMemPalace(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}

    def test_prereq_always_true(self):
        """Prereq always returns True — install handles skip/idempotency."""
        with patch("os.path.isdir", return_value=False):
            import importlib
            import bootloader.plugins.mempalace as mp_module
            importlib.reload(mp_module)
            result = mp_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_prereq_true_when_exists(self):
        mp_dir = os.path.join(self.user_home, ".mempalace")
        os.makedirs(mp_dir, exist_ok=True)
        with patch("os.path.isdir", return_value=True):
            import importlib
            import bootloader.plugins.mempalace as mp_module
            importlib.reload(mp_module)
            result = mp_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_install_idempotent(self):
        """Test that install can be called multiple times without error."""
        mp_dir = os.path.join(self.user_home, ".mempalace")
        venv_dir = os.path.join(mp_dir, "venv")
        venv_bin = os.path.join(venv_dir, "bin")
        venv_lib = os.path.join(venv_dir, "lib")

        # Pre-create the directory structure that would exist after first run
        os.makedirs(venv_bin, exist_ok=True)
        os.makedirs(venv_lib, exist_ok=True)

        def mock_run(*args, **kwargs):
            # Create venv bin/lib dirs if pip install is called
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and any("pip" in str(a) for a in cmd):
                os.makedirs(venv_bin, exist_ok=True)
                os.makedirs(venv_lib, exist_ok=True)
            return MagicMock(returncode=0)

        with patch("os.path.isdir", return_value=True):
            with patch("subprocess.run", side_effect=mock_run):
                with patch("venv.create"):
                    import importlib
                    import bootloader.plugins.mempalace as mp_module
                    importlib.reload(mp_module)
                    # First call should succeed
                    r1 = mp_module.hook_install(self.context)
                    self.assertTrue(r1["installed"])
                    self.assertFalse(r1.get("skipped", False))
                    # Second call should also succeed (idempotent)
                    r2 = mp_module.hook_install(self.context)
                    self.assertTrue(r2["installed"])

    def test_verify_fails_when_venv_missing(self):
        with patch("os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.mempalace as mp_module
            importlib.reload(mp_module)
            with self.assertRaises(RuntimeError):
                mp_module.hook_verify(self.context)