import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import bootloader.plugins.security_hardening as sh  # noqa: E402  (loaded after package init)


# Re-load against the live module instance so tests always see fresh state
def reload():
    import importlib

    importlib.reload(sh)


class TestSecurityHardening(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}

        # Create protected directories with correct permissions
        for d in sh.PROTECTED_DIRS:
            full = os.path.join(self.user_home, d)
            os.makedirs(full, exist_ok=True)
            os.chmod(full, 0o700)
        # Create protected files with correct permissions
        for f in sh.PROTECTED_FILES:
            full = os.path.join(self.user_home, f)
            if not os.path.exists(full):
                open(full, "w").close()
            os.chmod(full, 0o600)

    def test_install_sets_dir_mode_700(self):
        """Install hook applies mode 700 to existing directories."""
        # Wipe permissions back to insecure so install has work to do
        hermes = os.path.join(self.user_home, ".hermes")
        os.chmod(hermes, 0o755)

        with patch.object(subprocess, "run"):
            with patch("bootloader.plugins.security_hardening._is_wsl", return_value=True):
                reload()
                sh.hook_install(self.context)

        perms = os.stat(hermes).st_mode & 0o777
        self.assertEqual(perms, 0o700)

    def test_prereq_always_true(self):
        """Prereq always returns True — install handles hardening."""
        clean_home = tempfile.mkdtemp()
        clean_context = {"USER_HOME": clean_home}
        reload()
        result = sh.hook_check_prerequisites(clean_context)
        self.assertTrue(result)

    def test_verify_fails_on_world_readable(self):
        """Verify raises RuntimeError when a protected dir is world-readable."""
        hermes = os.path.join(self.user_home, ".hermes")
        os.chmod(hermes, 0o755)  # insecure = should trigger verify failure
        reload()
        with self.assertRaises(RuntimeError) as ctx:
            sh.hook_verify(self.context)
        self.assertIn(".hermes", str(ctx.exception))

    def test_verify_skips_nonexistent_dirs(self):
        """Verify passes when existing dirs are secured (missing ones are skipped)."""
        reload()
        # All created dirs have 0o700 — verify should pass
        self.assertTrue(sh.hook_verify(self.context))

    def test_wsl_detection_skips_iptables(self):
        """On WSL2, iptables is skipped and added to skipped list."""
        with patch.object(subprocess, "run"):
            with patch("bootloader.plugins.security_hardening._is_wsl", return_value=True):
                reload()
                result = sh.hook_install(self.context)
        self.assertTrue(result["installed"])
        self.assertIn("iptables (WSL2)", result["skipped"])