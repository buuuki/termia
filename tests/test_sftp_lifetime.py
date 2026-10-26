"""Regressions for closed SFTP UI and first-import lifetime ownership."""
import gc
import os
import subprocess
import sys
import textwrap
import time
import unittest
from threading import Event
from unittest.mock import Mock

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk

from termia.sftp_service import Endpoint
from termia.sftp_view import SFTPWindow
from termia.ui_state import SignalConnections


class SFTPImportLifetimeTests(unittest.TestCase):
    def test_first_backend_import_does_not_retain_its_caller(self):
        script = textwrap.dedent('''
            import gc
            import importlib.abc
            import sys
            import weakref

            class MissingInvoke(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname == 'invoke':
                        raise ModuleNotFoundError("No module named 'invoke'", name='invoke')

            sys.meta_path.insert(0, MissingInvoke())

            class Marker:
                pass

            def first_import():
                marker = Marker()
                reference = weakref.ref(marker)
                from termia import sftp_backend
                return reference

            reference = first_import()
            gc.collect()
            assert reference() is None, 'First backend import retains caller locals'
            import paramiko.config
            error = getattr(paramiko.config, 'invoke_import_error', None)
            if error is not None:
                assert isinstance(error, ImportError)
                assert 'invoke' in str(error)
        ''')
        result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_backend_import_accepts_optional_error_attribute_variants(self):
        script = textwrap.dedent("""
            import sys
            import paramiko
            variant = sys.argv[1]
            if variant == 'import-error':
                try:
                    raise ModuleNotFoundError("No module named 'invoke'", name='invoke')
                except ImportError as error:
                    original = error
            else:
                original = RuntimeError('Synthetic unrelated error') if variant == 'unrelated' else None
            if variant == 'absent':
                if hasattr(paramiko.config, 'invoke_import_error'):
                    del paramiko.config.invoke_import_error
            else:
                paramiko.config.invoke_import_error = original
            import termia.sftp_backend
            if variant == 'absent':
                assert not hasattr(paramiko.config, 'invoke_import_error')
            else:
                assert paramiko.config.invoke_import_error is original
                if variant == 'import-error':
                    assert original.__traceback__ is None
                    assert original.name == 'invoke'
                    assert str(original) == "No module named 'invoke'"
        """)
        for variant in ('absent', 'none', 'unrelated', 'import-error'):
            with self.subTest(variant=variant):
                result = subprocess.run([sys.executable, '-c', script, variant],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"),
                     "GTK display unavailable")
class SFTPLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.parent = Gtk.Window()
        self.references = []
        self.closed = []

    def tearDown(self):
        for ref in self.references:
            window = ref()
            if window is not None:
                window.close_requested()
                window.destroy()
        self.parent.destroy()

    def wait_for(self, predicate, message):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            context = GLib.MainContext.default()
            for _ in range(100):
                if not context.pending():
                    break
                context.iteration(False)
            gc.collect()
            if predicate():
                return
            time.sleep(.01)
        self.fail(message)

    def window(self):
        backend = Mock()
        backend.connect.return_value = '/synthetic'
        backend.list_directory.return_value = []
        window = SFTPWindow(
            self.parent, Endpoint('example.test', 22, 'test'), 'Synthetic',
            lambda key: key, lambda current: self.closed.append(hash(current)),
            backend_factory=lambda _endpoint: backend,
        )
        self.references.append(window.weak_ref())
        self.wait_for(lambda: window.connection_ready and not window.service.busy,
                      'Synthetic SFTP connection did not settle')
        return window

    def test_repeated_closed_windows_and_controls_are_released(self):
        retired = []
        def exercise_case(cycle):
            window = self.window()
            retired.extend(widget.weak_ref() for widget in
                           (window, window.location, window.rows, window.disconnect_button))
            window.close_requested()
            self.wait_for(lambda: len(self.closed) == cycle + 1,
                          'Closed explorer was not unregistered')
            self.assertTrue(window.service.stopped)
            window.close_requested()
            self.assertEqual(len(self.closed), cycle + 1)
            del window
            self.wait_for(lambda: all(ref() is None for ref in retired),
                          'Closed native SFTP window or control remains alive')

        for cycle in range(3):
            exercise_case(cycle)

    def test_close_keeps_ui_ownership_until_worker_cleanup_finishes(self):
        window = self.window()
        started, release = Event(), Event()

        def close_backend():
            started.set()
            release.wait(3)

        window.service.backend.close.side_effect = close_backend
        reference = window.weak_ref()
        try:
            window.close_requested()
            self.assertTrue(started.wait(1))
            self.assertFalse(window.service.stopped)
            self.assertFalse(window.ui_released)
            self.assertTrue(window.ui_signals.handlers)
            self.assertFalse(self.closed)
        finally:
            release.set()
        self.wait_for(lambda: bool(self.closed), 'Stopped explorer was not unregistered')
        self.assertTrue(window.ui_released)
        self.assertFalse(window.ui_signals.handlers)
        del window
        self.wait_for(lambda: reference() is None, 'Stopped explorer remains alive')

    def test_closed_dialog_does_not_retain_its_explorer(self):
        window = self.window()
        window.confirm('Synthetic confirmation', lambda: None)
        dialog = next(iter(window.dialogs))
        dialog_ref = dialog.weak_ref()
        dialog.response(Gtk.ResponseType.CANCEL)
        del dialog
        self.assertFalse(window.dialogs)
        window_ref = window.weak_ref()
        window.close_requested()
        self.wait_for(lambda: bool(self.closed), 'Explorer did not close')
        del window
        self.wait_for(lambda: window_ref() is None and dialog_ref() is None,
                      'Completed dialog retains native UI objects')

    def test_open_dialog_is_released_when_explorer_closes(self):
        window = self.window()
        window.prompt('Synthetic password', lambda _value: None, secret=True)
        dialog = next(iter(window.dialogs))
        dialog_ref, window_ref = dialog.weak_ref(), window.weak_ref()
        del dialog
        window.close_requested()
        self.wait_for(lambda: bool(self.closed), 'Explorer did not close')
        del window
        self.wait_for(lambda: window_ref() is None and dialog_ref() is None,
                      'Closing an explorer retains its prompt or native window')

    def test_signal_owner_uses_native_disconnect_for_overriding_widgets(self):
        class ActionBox(Gtk.Box):
            def disconnect(self):
                raise AssertionError('Application action must not disconnect a signal')

        box = ActionBox()
        owner = SignalConnections()
        handler = owner.connect(box, 'notify::visible', lambda *_args: None)
        owner.disconnect()
        self.assertFalse(box.handler_is_connected(handler))


if __name__ == '__main__':
    unittest.main()
