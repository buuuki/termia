import gc
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import weakref
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gio, GLib, Gtk, Vte

from termia.file_transfer import FileTransferController
from termia.session_registry import SessionRegistry
from termia.tab_lifecycle_actions import TabLifecycleActions
from termia.tabs import TabsMixin
from termia.terminal_processes import process_start_time, spawn_terminal_process
from termia.terminal_sessions import TerminalSessionsMixin
from termia.ui_state import TerminalPane, TerminalSession

RESISTANT_CHILD_COMMAND = """
import os, signal, sys, time
from pathlib import Path
if os.fork() == 0:
    os.setpgrp()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    Path(sys.argv[1]).write_text(str(os.getpid()))
time.sleep(30)
"""


class CleanupHost(TerminalSessionsMixin, TabsMixin):
    """Real tab/process lifecycle with unrelated presentation services stubbed."""

    t = staticmethod(lambda key: key)

    def __init__(self, session, window):
        self.session_registry = SessionRegistry([session])
        self.store = SimpleNamespace(
            data=SimpleNamespace(app=SimpleNamespace(close_tab_on_disconnect=False)),
            record_history_end=Mock(),
        )
        self.session_observer = Mock()
        self.toast_label = Mock()
        self.file_transfer_controllers = set()
        self.orphaned_terminal_processes = set()
        self.shutdown_in_progress = False
        self.tab_lifecycle_actions = TabLifecycleActions(
            Mock(), self.disconnect_session, self.terminate_split_processes, Mock()
        )
        self.visible_sessions_in_tab_order = lambda: list(self.session_registry.sessions())
        self.remove_session_from_main_view = lambda _session: window.set_child(None)
        self.update_session_tab_bar_visibility = Mock()
        self.focus_available_session_after_close = Mock()
        self.sync_window_title_with_visible_session = Mock()
        self.update_session_tab_title = Mock()


@unittest.skipUnless(
    (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check(),
    "GTK display unavailable",
)
class TerminalCleanupIntegrationTests(unittest.TestCase):
    def test_closed_sessions_and_native_widgets_are_released(self):
        from termia.app import TermiaApp, TermiaWindow
        from termia.stores import ConnectionStore
        app = TermiaApp()
        app.set_application_id('local.termia.cleanup')
        app.register(None)
        for enabled in (False, True):
            with self.subTest(optional_tools=enabled), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = ConnectionStore(root/'connections.json', root/'settings.json',
                                        root/'statistics.json', root/'lock', root/'history')
                store.data.app.open_local_terminal_on_startup = False
                store.data.app.confirm_disconnect = False
                store.data.app.sftp_enabled = enabled
                store.data.app.statistics_enabled = enabled
                with patch('termia.app.ConnectionStore', return_value=store):
                    window = TermiaWindow(app)
                window.present()
                try:
                    def open_and_close():
                        session_refs, widget_refs, panes, accounting = [], [], [], []
                        for index in range(2):
                            session = window.open_process_terminal_tab('Synthetic', ['/bin/sh'], None)
                            terminal = window.split_terminal_pane(session, session.terminal, 'horizontal')
                            window.start_split_child_terminal(session, terminal, session.terminal, None, announce=False)
                            session_refs.append(weakref.ref(session))
                            widget_refs.extend(widget.weak_ref() for widget in
                                               (session.page, session.tab_label, session.terminal, terminal))
                            panes.extend(session.panes.values())
                            accounting.extend((session, session.pane_for_terminal(terminal)))
                            if index == 0:
                                window.disconnect_pane(session, terminal)
                                self.wait_until(lambda: session.pane_for_terminal(terminal) is None)
                                self.assertTrue(accounting[-1].retired)
                                self.assertIsNone(accounting[-1].exit_handler_id)
                                self.assertTrue(session.connected)
                            window.close_tab(session.id, session.page, disconnect=True)
                        return session_refs, widget_refs, panes, accounting
                    session_refs, widget_refs, panes, accounting = open_and_close()
                    self.wait_until(lambda panes=panes: all(pane.child_process is None for pane in panes))
                    self.assertTrue(all(item.history_end_recorded for item in accounting))
                    del panes, accounting
                    def released():
                        gc.collect()
                        return all(ref() is None for ref in session_refs + widget_refs)
                    self.wait_until(released, timeout=5)
                finally:
                    window.shutdown_in_progress = True
                    window.prepare_terminal_sessions_for_shutdown()
                    window.terminate_open_terminal_processes(force=True)
                    window.snippet_dialogs.shutdown()
                    window.notes_dialogs.shutdown()
                    window.destroy()
                    store.close()

    def wait_until(self, predicate, timeout=3, *, dispatch=True):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if dispatch:
                GLib.MainContext.default().iteration(False)
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for terminal cleanup")

    @staticmethod
    def running(pid):
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()
        except FileNotFoundError:
            return False
        return bool(fields) and fields[0] != "Z"

    @staticmethod
    def kill_owned_process(pid, start_time):
        if start_time is not None and process_start_time(pid) == start_time:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_closing_tab_kills_resistant_child_after_vte_leader_exits(self):
        with tempfile.TemporaryDirectory(prefix="termia-cleanup-") as temporary:
            ready = Path(temporary) / "ready"
            terminal = Vte.Terminal()
            page = Gtk.Box()
            page.append(terminal)
            window = Gtk.Window()
            window.set_child(page)
            self.addCleanup(window.destroy)
            window.present()
            process = spawn_terminal_process(
                terminal, temporary,
                [sys.executable, "-c", RESISTANT_CHILD_COMMAND, str(ready)], [],
            )
            self.addCleanup(self.kill_owned_process, process.pid, process.start_time)
            self.wait_until(lambda: ready.exists() and bool(ready.read_text()))
            child = int(ready.read_text())
            self.addCleanup(self.kill_owned_process, child, process_start_time(child))

            # An independent session must survive the tab's process-group cleanup.
            unrelated = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                start_new_session=True,
            )
            self.addCleanup(unrelated.wait)
            self.addCleanup(unrelated.kill)

            label = Gtk.Label()
            button = Gtk.Button()
            session = TerminalSession(
                "cleanup", None, "Cleanup", terminal, page, Gtk.Label(), label,
                Gtk.Label(), button, Gtk.Box(), time.monotonic(),
                child_pid=process.pid, child_process=process,
            )
            pane = TerminalPane(
                "cleanup", terminal, page, label, session.timer_label, button,
                session.status_bar, "Cleanup", session.started_at,
                child_pid=process.pid, child_process=process,
            )
            session.panes[id(terminal)] = pane
            session.active_terminal_ids.add(id(terminal))
            host = CleanupHost(session, window)
            terminal.connect("child-exited", host.on_process_terminal_exited, session)

            host.close_tab(session.id, page, disconnect=True)

            self.assertIsNone(host.session_registry.get(session.id))
            self.wait_until(lambda: session.child_process is None)
            self.wait_until(lambda: not self.running(child))
            host.prepare_terminal_sessions_for_shutdown()
            self.wait_until(lambda: not host.pending_shutdown_terminal_processes())
            self.assertIsNone(unrelated.poll())

    def test_scp_controller_observes_real_children_after_refresh_and_cancellation(self):
        with tempfile.TemporaryDirectory(prefix="termia-scp-cleanup-") as temporary:
            ready = Path(temporary) / "ready"
            controller = FileTransferController(Mock(), lambda key: key, Mock(), Mock(), Mock())
            state = {
                "cancellable": Gio.Cancellable(), "phase": "copy",
                "cancel": Mock(), "status": Mock(), "progress": Mock(),
                "dialog": Mock(),
            }
            controller.active_state = state
            controller.run_command(
                [sys.executable, "-c", RESISTANT_CHILD_COMMAND, str(ready)],
                "", state, Mock(),
            )
            identity = state["process_identity"]
            self.addCleanup(self.kill_owned_process, identity.pid, identity.start_time)
            self.wait_until(lambda: ready.exists() and bool(ready.read_text()))
            child = int(ready.read_text())
            self.addCleanup(self.kill_owned_process, child, process_start_time(child))
            # Reproduce an initial capture that preceded setsid establishing isolation.
            state["process_identity"] = replace(identity, process_group_id=None, session_id=None)

            controller.cancel_active_transfer(close_dialog=True)

            refreshed = state["process_identity"]
            self.assertIsNotNone(refreshed.session_id)
            self.assertEqual(controller.shutdown_processes, {refreshed})
            self.assertEqual(controller.shutdown_cleanup_state(), "pending")
            # Hold the UI timer until the leader has exited, regardless of load.
            self.wait_until(lambda: not self.running(identity.pid), dispatch=False)
            self.assertTrue(self.running(child))
            self.assertEqual(controller.shutdown_cleanup_state(), "pending")
            self.wait_until(lambda: controller.shutdown_cleanup_state() == "stopped")
            self.assertFalse(self.running(child))


if __name__ == "__main__":
    unittest.main()
