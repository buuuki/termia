import gc
import os
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from termia.plugin_runtime import PluginRuntime


@unittest.skipUnless(
    (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check(),
    "GTK display unavailable",
)
class ExternalDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="termia-external-diagnostics-")
        cls.addClassCleanup(temporary.cleanup)
        cls.context = Mock(return_value={
            "sessions": 1, "terminals": 2, "ssh_clients": 1, "local_terminals": 1,
            "processes": [{"pid": 123, "start_time": "synthetic", "kind": "shell",
                           "possible_orphan": False}],
        })
        cls.attach = Mock()
        cls.style = Mock()
        root = Path(__file__).resolve().parents[1] / "tools/addon-lab/termia-plugins"
        cls.runtime = PluginRuntime(root, temporary.name, {
            "diagnostics_context": cls.context, "attach_window": cls.attach, "apply_style": cls.style,
        })
        cls.addClassCleanup(cls.runtime.close)
        cls.plugin = cls.runtime.plugins["diagnostics"]
        if cls.plugin.problem:
            raise AssertionError(cls.plugin.problem)
        cls.code = sys.modules[cls.plugin.loaded_module.__name__ + ".diagnostics"]

    def setUp(self):
        self.runtime.set_enabled("diagnostics", True)
        self.context.reset_mock()
        self.attach.reset_mock()
        self.style.reset_mock()
        self.windows = []
        self.attach.side_effect = self.windows.append
        sampling = patch.object(self.code.LocalProcessSampler, "sample", side_effect=(
            lambda context, cancelled: self.code.ResourceSnapshot(0, None, (), context, True)
        ))
        self.sample = sampling.start()
        self.addCleanup(sampling.stop)

    def tearDown(self):
        self.runtime.close()
        for window in self.windows:
            window._executor.shutdown(wait=True, cancel_futures=True)
        self.attach.reset_mock()
        self.attach.side_effect = None
        self.style.reset_mock()
        self.windows.clear()
        gc.collect()

    def open_window(self, language="en"):
        self.runtime.show("diagnostics", language)
        self.assertEqual(self.plugin.problem, "")
        self.assertIsNotNone(self.plugin.instance.window)
        return self.plugin.instance.window

    def assert_stopped(self, window):
        self.assertTrue(window.closed)
        self.assertTrue(window.cancelled.is_set())
        self.assertIsNone(window._timer)
        self.assertIsNone(window._poll)
        self.assertIsNone(window._future)

    def test_host_keeps_legacy_context_alias_and_returns_fresh_snapshots(self):
        from termia.app import TermiaApp
        from termia.diagnostics_contract import DiagnosticContext

        with patch("termia.app.PluginRuntime") as runtime_factory:
            app = TermiaApp()
        capabilities = runtime_factory.call_args.args[2]
        self.assertIs(capabilities["context"], capabilities["diagnostics_context"])
        with patch.object(app, "diagnostic_context", return_value=DiagnosticContext(sessions=2)):
            legacy = capabilities["context"]()
            legacy["sessions"] = 99
            current = capabilities["diagnostics_context"]()
        self.assertEqual(current["sessions"], 2)
        self.assertIsNot(legacy, current)

    def test_real_factory_converts_context_without_starting_monitoring(self):
        self.assertEqual(self.plugin.loaded_module.API_VERSION, 2)
        entry = Path(self.plugin.loaded_module.__file__)
        self.assertEqual(entry.resolve(), (
            self.plugin.directory / "src/termia_diagnostics/__init__.py"
        ).resolve())
        context = self.plugin.instance.context()
        self.assertEqual((context.sessions, context.terminals, context.ssh_clients,
                          context.local_terminals), (1, 2, 1, 1))
        self.assertEqual(context.processes[0].pid, 123)
        self.assertEqual(context.processes[0].start_time, "synthetic")
        self.assertIsInstance(context, self.code.DiagnosticContext)
        self.assertIsInstance(context.processes[0], self.code.ManagedProcess)
        self.attach.assert_not_called()
        self.sample.assert_not_called()

    def test_single_window_uses_host_callbacks_and_own_translations(self):
        titles = {"en": "Termia diagnostics", "es": "Diagnóstico de Termia",
                  "ca": "Diagnòstic de Termia"}
        for language, title in titles.items():
            with self.subTest(language=language):
                self.attach.reset_mock()
                window = self.open_window(language)
                self.assertIs(self.open_window(language), window)
                self.attach.assert_called_once_with(window)
                self.assertEqual(window.get_title(), title)
                self.assertFalse(window.get_modal())
                self.assertIsNone(window.get_transient_for())
                roles = {call.args[1] for call in self.style.call_args_list}
                self.assertEqual(roles, {"panel", "content", "text_frame"})
                self.plugin.instance.close()
                self.assert_stopped(window)

    def test_disable_closes_window_and_reactivation_creates_new_controller(self):
        controller = self.plugin.instance
        window = self.open_window()
        self.runtime.set_enabled("diagnostics", False)
        self.assert_stopped(window)
        self.assertIsNone(self.plugin.instance)
        self.assertFalse(self.runtime.options("en")[0][3])
        state = Path(self.runtime.profile) / "diagnostics-addon.disabled"
        self.assertEqual(state.read_text().strip(), "disabled")
        self.runtime.set_enabled("diagnostics", True)
        self.assertIsNot(self.plugin.instance, controller)
        self.assertIsNot(self.open_window(), window)
        self.assertEqual(state.read_text().strip(), "enabled")

    def test_user_close_allows_reopening(self):
        window = self.open_window()
        window.close()
        self.assert_stopped(window)
        replacement = self.open_window()
        self.assertIsNot(replacement, window)
        self.assertFalse(replacement.closed)

    def test_shutdown_cancels_inflight_sampling(self):
        started, finished = Event(), Event()

        def sample(context, cancelled):
            started.set()
            cancelled.wait(2)
            finished.set()
            return self.code.ResourceSnapshot(0, None, (), context, True)

        self.sample.side_effect = sample
        window = self.open_window()
        self.assertTrue(started.wait(1))
        self.runtime.close()
        self.assertTrue(finished.wait(1))
        self.assert_stopped(window)
        self.assertIsNone(self.plugin.instance)


if __name__ == "__main__":
    unittest.main()
