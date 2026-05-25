import os
import tempfile
import unittest

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from unittest.mock import patch


class TestOpenClawConfig(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}
        self.config_path = os.path.join(self.user_home, ".openclaw", "config.yaml")

    def test_prereq_always_true(self):
        """Prereq always returns True — install handles skip/idempotency."""
        with patch("os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.openclaw_config as occ_module
            importlib.reload(occ_module)
            result = occ_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_prereq_true_when_config_exists(self):
        os.makedirs(os.path.join(self.user_home, ".openclaw"), exist_ok=True)
        with open(self.config_path, "w") as f:
            f.write("telegram:\n  allowed_users: []\nserver:\n  port: 18789\n")
        with patch("os.path.isfile", return_value=True):
            import importlib
            import bootloader.plugins.openclaw_config as occ_module
            importlib.reload(occ_module)
            result = occ_module.hook_check_prerequisites(self.context)
            self.assertTrue(result)

    def test_install_creates_valid_yaml(self):
        import importlib
        import bootloader.plugins.openclaw_config as occ_module
        importlib.reload(occ_module)
        occ_module.hook_install(self.context)
        self.assertTrue(os.path.isfile(self.config_path))
        if HAS_YAML:
            with open(self.config_path) as f:
                cfg = yaml.safe_load(f)
            self.assertIn("allowed_users", cfg.get("telegram", {}))

    def test_install_preserves_existing_allowed_users(self):
        os.makedirs(os.path.join(self.user_home, ".openclaw"), exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump({"telegram": {"allowed_users": ["999999"]}}, f)

        import importlib
        import bootloader.plugins.openclaw_config as occ_module
        importlib.reload(occ_module)
        occ_module.hook_install(self.context)

        with open(self.config_path) as f:
            cfg = yaml.safe_load(f)
        self.assertIn("999999", cfg["telegram"]["allowed_users"])

    def test_verify_passes_with_valid_yaml(self):
        os.makedirs(os.path.join(self.user_home, ".openclaw"), exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump({"telegram": {"allowed_users": ["6878695078"]}, "server": {"port": 18789}}, f)

        import importlib
        import bootloader.plugins.openclaw_config as occ_module
        importlib.reload(occ_module)
        self.assertTrue(occ_module.hook_verify(self.context))

    def test_verify_fails_when_missing(self):
        with patch("os.path.isfile", return_value=False):
            import importlib
            import bootloader.plugins.openclaw_config as occ_module
            importlib.reload(occ_module)
            with self.assertRaises(RuntimeError):
                occ_module.hook_verify(self.context)