"""
Bootloader Test Suite

Discovers and runs all plugin test files.
Can be run with: python3 -m pytest bootloader/tests/test_plugins.py -v
or: python3 -m pytest bootloader/tests/ -v
"""
import unittest

# Import all individual plugin test modules so pytest/discovery finds them
from bootloader.tests import test_pnpm
from bootloader.tests import test_openclaw
from bootloader.tests import test_openclaw_config
from bootloader.tests import test_open_design
from bootloader.tests import test_mempalace
from bootloader.tests import test_systemd_services
from bootloader.tests import test_security_hardening
from bootloader.tests import test_maintenance_scripts

# Make them discoverable by unittest
loader = unittest.TestLoader()
suite = unittest.TestSuite()

for module in [
    test_pnpm,
    test_openclaw,
    test_openclaw_config,
    test_open_design,
    test_mempalace,
    test_systemd_services,
    test_security_hardening,
    test_maintenance_scripts,
]:
    suite.addTests(loader.loadTestsFromModule(module))

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)