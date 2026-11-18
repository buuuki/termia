import json
import sys
import tempfile
import unittest
from pathlib import Path

from termia.plugin_runtime import PluginRuntime

CODE = """API_VERSION = 2
class Controller:
    def __init__(self):
        self.opened = False
        self.closed = False
        self.fail_open = False
        self.fail_close = False
    def show(self, language):
        if self.fail_open: raise RuntimeError("synthetic opening failure")
        self.opened = True
    def close(self):
        if self.fail_close: raise RuntimeError("synthetic closing failure")
        self.closed = True

def create(**capabilities):
    return Controller()
"""


class PluginRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="termia-plugin-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "plugins"
        self.profile = Path(self.temp.name) / "profile"
        self.package = self.root / "sample/src/sample"
        self.package.mkdir(parents=True)
        self.entry = self.package / "__init__.py"
        self.entry.write_text(CODE)
        self.manifest = self.root / "sample/plugin.json"
        self.data = {
            "id": "sample",
            "name": {"en": "Sample"},
            "version": "0.1",
            "icon": "computer-symbolic",
            "module": "sample",
            "capabilities": [],
            "api_version": 2,
        }
        self.save_manifest()
        self.state = self.profile / "sample-addon.disabled"

    def tearDown(self):
        for key in tuple(sys.modules):
            if key == "termia_plugin_sample" or key.startswith("termia_plugin_sample."):
                del sys.modules[key]

    def save_manifest(self):
        self.manifest.write_text(json.dumps(self.data))

    def runtime(self, **kw):
        return PluginRuntime(self.root, self.profile, {}, **kw)

    def saved(self, value):
        self.profile.mkdir(exist_ok=True)
        self.state.write_text(value)

    def test_new_plugin_is_disabled(self):
        runtime = self.runtime()
        self.assertFalse(runtime.options("en")[0][3])
        self.assertNotIn("termia_plugin_sample", sys.modules)
        self.assertFalse(self.profile.exists())

    def test_activation_and_disable_persist(self):
        runtime = self.runtime()
        runtime.set_enabled("sample", True)
        instance = runtime.plugins["sample"].instance
        runtime.show("sample", "es")
        self.assertTrue(instance.opened)
        self.assertEqual(self.state.read_text().strip(), "enabled")
        runtime.set_enabled("sample", False)
        self.assertTrue(instance.closed)
        self.assertEqual(self.state.read_text().strip(), "disabled")
        self.assertFalse(runtime.options("en")[0][3])

    def test_saved_activation_loaded(self):
        self.saved("enabled")
        runtime = self.runtime()
        self.addCleanup(runtime.close)
        self.assertIsNotNone(runtime.plugins["sample"].instance)

    def test_legacy_disabled_marker_preserved(self):
        self.data["default_enabled"] = True
        self.save_manifest()
        self.saved("")
        self.assertFalse(self.runtime().options("en")[0][3])

    def test_blocked_launch_preserves_choice_without_import(self):
        self.saved("enabled")
        option = self.runtime(blocked=True).options("en")[0]
        self.assertEqual(option[2], "addon_launch_disabled")
        self.assertTrue(option[3])
        self.assertFalse(option[4])
        self.assertNotIn("termia_plugin_sample", sys.modules)

    def test_incompatible_manifest_can_be_disabled(self):
        self.data["api_version"] = 999
        self.save_manifest()
        self.saved("enabled")
        runtime = self.runtime()
        self.assertEqual(runtime.options("en")[0][2], "addon_incompatible")
        self.assertTrue(runtime.options("en")[0][4])
        runtime.set_enabled("sample", False)
        self.assertEqual(self.state.read_text().strip(), "disabled")

    def test_missing_code_can_be_disabled(self):
        self.entry.unlink()
        self.saved("enabled")
        runtime = self.runtime()
        self.assertEqual(runtime.options("en")[0][2], "addon_missing")
        runtime.set_enabled("sample", False)
        self.assertFalse(runtime.options("en")[0][3])

    def test_missing_manifest_retains_saved_choice(self):
        self.manifest.unlink()
        self.saved("enabled")
        runtime = self.runtime()
        self.assertEqual(runtime.options("en")[0][2], "addon_missing")
        runtime.set_enabled("sample", False)
        self.assertEqual(self.state.read_text().strip(), "disabled")

    def test_malformed_metadata_does_not_abort_host(self):
        self.manifest.write_text("not-json")
        self.saved("enabled")
        runtime = self.runtime()
        self.assertEqual(runtime.options("en")[0][2], "addon_metadata_failed")
        runtime.set_enabled("sample", False)

    def test_module_api_rejected(self):
        self.entry.write_text(CODE.replace("API_VERSION = 2", "API_VERSION = 999"))
        self.saved("enabled")
        runtime = self.runtime()
        self.assertEqual(runtime.options("en")[0][2], "addon_incompatible")
        self.assertNotIn("termia_plugin_sample", sys.modules)

    def test_unsupported_capability_rejected_before_import(self):
        self.data["capabilities"] = ["unknown"]
        self.save_manifest()
        runtime = self.runtime()
        self.assertEqual(runtime.options("en")[0][2], "addon_incompatible")
        self.assertNotIn("termia_plugin_sample", sys.modules)

    def test_import_failure_can_be_disabled(self):
        self.entry.write_text('raise RuntimeError("synthetic import failure")')
        self.saved("enabled")
        runtime = self.runtime()
        self.assertEqual(runtime.options("en")[0][2], "addon_load_failed")
        runtime.set_enabled("sample", False)
        self.assertEqual(self.state.read_text().strip(), "disabled")

    def test_close_failure_keeps_disabled_preference(self):
        runtime = self.runtime()
        runtime.set_enabled("sample", True)
        instance = runtime.plugins["sample"].instance
        instance.fail_close = True
        with self.assertRaises(RuntimeError):
            runtime.set_enabled("sample", False)
        self.assertEqual(self.state.read_text().strip(), "disabled")
        option = runtime.options("en")[0]
        self.assertFalse(option[3])
        self.assertEqual(option[2], "addon_cleanup_pending")
        self.assertIs(runtime.plugins["sample"].instance, instance)
        instance.fail_close = False
        runtime.close()

    def test_open_failure_does_not_abort_host(self):
        runtime = self.runtime()
        runtime.set_enabled("sample", True)
        instance = runtime.plugins["sample"].instance
        instance.fail_open = True
        runtime.show("sample", "en")
        self.assertTrue(instance.closed)
        self.assertEqual(runtime.options("en")[0][2], "addon_open_failed")
        runtime.set_enabled("sample", False)

    def test_failed_persistence_does_not_enable(self):
        runtime = self.runtime()
        self.profile.write_text("synthetic obstruction")
        with self.assertRaises(OSError):
            runtime.set_enabled("sample", True)
        self.assertIsNone(runtime.plugins["sample"].instance)
        self.assertFalse(runtime.plugins["sample"].requested_enabled)

    def test_shutdown_closes_active_plugin(self):
        runtime = self.runtime()
        runtime.set_enabled("sample", True)
        instance = runtime.plugins["sample"].instance
        runtime.close()
        self.assertTrue(instance.closed)
        self.assertIsNone(runtime.plugins["sample"].instance)


if __name__ == "__main__":
    unittest.main(verbosity=2)
