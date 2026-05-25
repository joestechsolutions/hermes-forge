import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestMaintenanceScripts(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}

    def test_prereq_false_when_source_missing(self):
        """Prereq returns False only if hermes-sync.sh source doesn't exist."""
        with patch("bootloader.plugins.maintenance_scripts.os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.maintenance_scripts as ms_module
            importlib.reload(ms_module)
            result = ms_module.hook_check_prerequisites(self.context)
            self.assertFalse(result)

    def test_prereq_true_always_when_source_exists(self):
        """Prereq returns True if source exists, regardless of install state."""
        with patch("bootloader.plugins.maintenance_scripts.os.path.isfile", return_value=True):
            with patch("os.access", return_value=False):
                import importlib
                import bootloader.plugins.maintenance_scripts as ms_module
                importlib.reload(ms_module)
                result = ms_module.hook_check_prerequisites(self.context)
                self.assertTrue(result)

    def test_prereq_true_when_fully_installed(self):
        """Prereq returns True when script + cron both present."""
        with patch("bootloader.plugins.maintenance_scripts.os.path.isfile", return_value=True):
            with patch("os.access", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0, stdout="cron entry here")
                    import importlib
                    import bootloader.plugins.maintenance_scripts as ms_module
                    # Patch HERMES_SYNC_PATH in the module
                    importlib.reload(ms_module)
                    ms_module.HERMES_SYNC_PATH = "/fake/sync.sh"
                    result = ms_module.hook_check_prerequisites(self.context)
                    self.assertTrue(result)

    def test_install_creates_backup_script(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=""),  # crontab -l
                MagicMock(returncode=0),  # crontab -
            ]
            with patch("os.path.isfile", return_value=False):
                import importlib
                import bootloader.plugins.maintenance_scripts as ms_module
                importlib.reload(ms_module)
                result = ms_module.hook_install(self.context)
                self.assertTrue(result["installed"])

    def test_verify_fails_when_script_missing(self):
        with patch("os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.maintenance_scripts as ms_module
            importlib.reload(ms_module)
            with self.assertRaises(RuntimeError):
                ms_module.hook_verify(self.context)

    def test_verify_fails_when_no_cron(self):
        scripts_dir = os.path.join(self.user_home, ".hermes", "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        backup_path = os.path.join(scripts_dir, "hermes-backup.sh")
        with open(backup_path, "w") as f:
            f.write("#!/bin/bash\n")
        os.chmod(backup_path, 0o755)

        with patch("os.path.isfile", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="")
                import importlib
                import bootloader.plugins.maintenance_scripts as ms_module
                importlib.reload(ms_module)
                with self.assertRaises(RuntimeError):
                    ms_module.hook_verify(self.context)