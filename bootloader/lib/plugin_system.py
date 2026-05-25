"""
Plugin system for composable bootloader steps.

This module provides a flexible plugin architecture that allows the bootloader
to discover and execute hooks defined in separate Python modules.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BootloaderPlugin:
    """
    Represents a single bootloader plugin.

    A plugin is a Python module that defines one or more hook functions.
    Hook functions must start with the prefix 'hook_' and accept a context
    dictionary as their only parameter.

    Attributes:
        name: The plugin name (derived from the module filename).
        module_path: Path to the plugin Python file.
        hooks: Dictionary mapping hook names (without prefix) to callable functions.
    """

    def __init__(self, name: str, module_path: Path):
        """
        Initialize a BootloaderPlugin.

        Args:
            name: The plugin name.
            module_path: Path to the plugin Python file.
        """
        self.name = name
        self.module_path = module_path
        self.hooks: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._module = None

    def load(self) -> None:
        """
        Dynamically load the plugin module and discover hook functions.

        This method uses importlib.util to load the module from the specified
        path. It then scans the module for all callable attributes whose names
        start with 'hook_' and stores them in the hooks dictionary.

        Errors during import are logged but do not raise exceptions.

        Raises:
            ImportError: If the module cannot be imported (logged, not raised).
        """
        try:
            spec = importlib.util.spec_from_file_location(self.name, self.module_path)
            if spec is None or spec.loader is None:
                logger.error(f"Could not create spec for plugin {self.name} at {self.module_path}")
                return

            self._module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self._module)

            # Discover hook methods
            for attr_name in dir(self._module):
                if attr_name.startswith('hook_'):
                    attr = getattr(self._module, attr_name)
                    if callable(attr):
                        hook_name = attr_name[5:]  # Remove 'hook_' prefix
                        self.hooks[hook_name] = attr
                        logger.debug(f"Discovered hook '{hook_name}' in plugin '{self.name}'")

            logger.info(f"Loaded plugin '{self.name}' with {len(self.hooks)} hooks")

        except Exception as e:
            logger.error(f"Failed to load plugin '{self.name}' from {self.module_path}: {e}")
            self.hooks = {}  # Ensure hooks is empty on failure

    def execute_hook(self, hook_name: str, context: Dict[str, Any]) -> Optional[Any]:
        """
        Execute a specific hook in this plugin.

        Args:
            hook_name: Name of the hook to execute (without 'hook_' prefix).
            context: Dictionary containing execution context data.

        Returns:
            The result of the hook function, or None if the hook doesn't exist
            or raises an exception.
        """
        if hook_name not in self.hooks:
            logger.debug(f"Plugin '{self.name}' has no hook '{hook_name}'")
            return None

        try:
            result = self.hooks[hook_name](context)
            return result
        except Exception as e:
            logger.error(f"Error executing hook '{hook_name}' in plugin '{self.name}': {e}")
            if hook_name in ("check_prerequisites", "verify"):
                return False  # Prereq/verify failures should fail the check
            return None  # install/cleanup failures are logged but don't block


class PluginManager:
    """
    Manages discovery and execution of bootloader plugins.

    The PluginManager scans a directory for Python plugin files, creates
    BootloaderPlugin instances, and coordinates the execution of hooks
    across all loaded plugins.

    Attributes:
        plugins_dir: Directory containing plugin Python files.
        plugins: Ordered dictionary of plugin names to BootloaderPlugin instances.
    """

    def __init__(self, plugins_dir: Path):
        """
        Initialize the PluginManager.

        Args:
            plugins_dir: Path to the directory containing plugin files.
        """
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, BootloaderPlugin] = {}

    def discover_plugins(self) -> List[str]:
        """
        Scan the plugins directory and load all Python plugin modules.

        This method finds all .py files in the plugins directory that do not
        start with an underscore (skipping private modules). For each file,
        it creates a BootloaderPlugin instance, loads it, and stores it.

        Plugins are stored in insertion order (Python 3.7+ dict preserves order).

        Returns:
            List of plugin names that were successfully discovered and loaded.

        Raises:
            OSError: If the plugins directory cannot be accessed (logged, not raised).
        """
        discovered = []

        try:
            if not self.plugins_dir.exists():
                logger.warning(f"Plugins directory does not exist: {self.plugins_dir}")
                return []

            if not self.plugins_dir.is_dir():
                logger.warning(f"Plugins path is not a directory: {self.plugins_dir}")
                return []

            # Inject bootloader package path so plugins can import from bootloader.lib.platform
            bootloader_dir = self.plugins_dir.parent
            if str(bootloader_dir) not in sys.path:
                sys.path.insert(0, str(bootloader_dir))

            # Find all .py files, skipping those starting with underscore
            for py_file in sorted(self.plugins_dir.glob("*.py")):
                if py_file.name.startswith('_'):
                    logger.debug(f"Skipping private plugin file: {py_file.name}")
                    continue

                plugin_name = py_file.stem  # Filename without extension
                plugin = BootloaderPlugin(plugin_name, py_file)
                plugin.load()
                self.plugins[plugin_name] = plugin
                discovered.append(plugin_name)

            logger.info(f"Discovered {len(discovered)} plugins in {self.plugins_dir}")

        except Exception as e:
            logger.error(f"Error during plugin discovery: {e}")

        return discovered

    def execute_hook(self, hook_name: str, context: Dict[str, Any]) -> List[Any]:
        """
        Execute a specific hook across all loaded plugins.

        The hook is called on each plugin in the order they were discovered.
        Non-None results are collected and returned.

        Args:
            hook_name: Name of the hook to execute (without 'hook_' prefix).
            context: Dictionary containing execution context data.

        Returns:
            List of non-None results from plugins that have the hook.
        """
        results = []

        for plugin_name, plugin in self.plugins.items():
            result = plugin.execute_hook(hook_name, context)
            if result is not None:
                results.append(result)
                logger.debug(f"Plugin '{plugin_name}' returned: {result}")

        logger.info(f"Hook '{hook_name}' executed on {len(self.plugins)} plugins, {len(results)} returned non-None")
        return results


if __name__ == "__main__":
    import tempfile
    import sys

    # Configure logging for test output
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    logger.info("Starting plugin system test...")

    # Create a temporary directory for test plugins
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir)
        logger.info(f"Created temporary plugins directory: {plugins_dir}")

        # Create a test plugin file with multiple hooks
        plugin_content = '''
"""Sample test plugin with various hooks."""

def hook_check_prerequisites(context):
    """Check if prerequisites are met."""
    reqs = context.get('prerequisites', [])
    return all(reqs) if reqs else True

def hook_install(context):
    """Perform installation."""
    target = context.get('target', 'unknown')
    return {"installed": True, "target": target}

def hook_verify(context):
    """Verify installation."""
    return True

def hook_cleanup(context):
    """Cleanup after operations."""
    return {"cleaned": True}

def hook_custom_hook(context):
    """A custom hook for testing."""
    value = context.get('value', 0)
    return value * 2
'''

        plugin_file = plugins_dir / "test_plugin.py"
        plugin_file.write_text(plugin_content)
        logger.info(f"Created test plugin: {plugin_file}")

        # Create a second plugin with only some hooks
        plugin2_content = '''
"""Second test plugin."""

def hook_install(context):
    return {"plugin": "second", "status": "installed"}

def hook_verify(context):
    return False  # This will show in results
'''

        plugin2_file = plugins_dir / "another_plugin.py"
        plugin2_file.write_text(plugin2_content)
        logger.info(f"Created second test plugin: {plugin2_file}")

        # Create a plugin with no hooks
        plugin3_content = '''
"""Plugin with no hooks."""
# This plugin defines no hook_ functions
'''
        plugin3_file = plugins_dir / "no_hooks_plugin.py"
        plugin3_file.write_text(plugin3_content)
        logger.info(f"Created no-hooks plugin: {plugin3_file}")

        # Create a private plugin (should be skipped)
        plugin_private_content = '''
"""Private plugin - should be skipped."""
def hook_install(context):
    return {"should": "not run"}
'''
        plugin_private_file = plugins_dir / "_private_plugin.py"
        plugin_private_file.write_text(plugin_private_content)
        logger.info(f"Created private plugin (should be skipped): {plugin_private_file}")

        # Create invalid plugin (syntax error) to test error handling
        plugin_invalid_content = '''
"""Invalid plugin with syntax error."""
def hook_bad(
    # Missing closing paren on purpose to cause SyntaxError
'''
        plugin_invalid_file = plugins_dir / "invalid_syntax.py"
        plugin_invalid_file.write_text(plugin_invalid_content)
        logger.info(f"Created invalid plugin (should log error): {plugin_invalid_file}")

        # Instantiate PluginManager and discover plugins
        manager = PluginManager(plugins_dir)
        discovered = manager.discover_plugins()

        print("\n" + "="*60)
        print("DISCOVERY RESULTS:")
        print("="*60)
        print(f"Plugins directory: {plugins_dir}")
        print(f"Discovered plugins: {discovered}")
        print(f"Total loaded: {len(manager.plugins)}")
        print(f"Plugins in manager:")
        for name in manager.plugins:
            hooks = list(manager.plugins[name].hooks.keys())
            print(f"  - {name}: {len(hooks)} hooks ({hooks})")

        # Execute various hooks and print results
        print("\n" + "="*60)
        print("HOOK EXECUTION TESTS:")
        print("="*60)

        test_context = {
            "prerequisites": [True, True, True],
            "target": "/opt/myapp",
            "value": 21
        }

        # Test hook_check_prerequisites
        print("\n Executing 'check_prerequisites' hook:")
        results = manager.execute_hook("check_prerequisites", test_context)
        print(f"  Results: {results}")

        # Test hook_install
        print("\n Executing 'install' hook:")
        results = manager.execute_hook("install", test_context)
        print(f"  Results: {results}")

        # Test hook_verify
        print("\n Executing 'verify' hook:")
        results = manager.execute_hook("verify", test_context)
        print(f"  Results: {results}")

        # Test hook_cleanup
        print("\n Executing 'cleanup' hook:")
        results = manager.execute_hook("cleanup", test_context)
        print(f"  Results: {results}")

        # Test hook_custom_hook
        print("\n Executing 'custom_hook' hook:")
        results = manager.execute_hook("custom_hook", test_context)
        print(f"  Results: {results}")

        # Test non-existent hook
        print("\n Executing non-existent 'does_not_exist' hook:")
        results = manager.execute_hook("does_not_exist", test_context)
        print(f"  Results: {results}")

        print("\n" + "="*60)
        print("TEST COMPLETED SUCCESSFULLY")
        print("="*60)
