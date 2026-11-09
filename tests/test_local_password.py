# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from termia.config_io import load_store_data_from_json, write_connections_file
from termia.connection_dialogs import ConnectionDialogsMixin
from termia.dialog_window import DialogWindow
from termia.migrations import (
    CURRENT_CONNECTIONS_SCHEMA_VERSION,
    migrate_connections_payload,
)
from termia.models import LocalTerminalProfile, Server, StoreData
from termia.sidebar import SidebarMixin
from termia.stores import ConnectionStore
from termia.terminal_sessions import TerminalSessionsMixin
from tests.test_terminal_panes import FakeTerminal, make_pane, make_session


class LocalPasswordTests(unittest.TestCase):
    def test_legacy_profiles_receive_empty_password_and_future_schema_is_rejected(self):
        for version in (0, 1, 2, 3):
            with self.subTest(version=version):
                migrated, changed = migrate_connections_payload({
                    "schema_version": version,
                    "local_terminals": [{"id": "local", "name": "Shell"}],
                })
                self.assertTrue(changed)
                self.assertEqual(migrated["schema_version"], CURRENT_CONNECTIONS_SCHEMA_VERSION)
                self.assertEqual(migrated["local_terminals"][0]["password"], "")
                self.assertEqual(migrate_connections_payload(migrated), (migrated, False))
        with self.assertRaises(ValueError):
            migrate_connections_payload({"schema_version": CURRENT_CONNECTIONS_SCHEMA_VERSION + 1})

    def test_password_round_trip_with_each_storage_protection_mode(self):
        password = "  synthetic-ñ-password  "
        for mode in ("plain", "obfuscated", "encrypted"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "connections.json"
                master = "synthetic-master" if mode == "encrypted" else None
                write_connections_file(path, [], [], [
                    LocalTerminalProfile("local", "Shell", password=password),
                ], mode, master)
                imported = load_store_data_from_json(path, StoreData(), master)
                self.assertEqual(imported.local_terminals[0].password, password)
                if mode != "plain":
                    self.assertNotIn("synthetic-ñ-password", path.read_text())

    def test_store_create_update_reload_and_clear_preserve_exact_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(*(root / name for name in (
                "connections.json", "settings.json", "statistics.json", "instance.lock", "history.jsonl",
            )))
            self.addCleanup(store.close)
            profile = store.add_local_terminal("Shell", "", "/bin/sh", "", "", "", password=" first ")
            store.load()
            self.assertEqual(store.data.local_terminals[0].password, " first ")
            for password in (" second ", ""):
                store.update_local_terminal(profile.id, "Shell", "", "/bin/sh", "", "", "", password=password)
                store.load()
                self.assertEqual(store.data.local_terminals[0].password, password)

    def test_read_only_legacy_load_does_not_rewrite_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "connections.json"
            original = json.dumps({"schema_version": 3, "local_terminals": [{"id": "local", "name": "Shell"}]})
            path.write_text(original)
            with patch("termia.stores.InstanceWriteLock") as lock:
                lock.return_value.read_only = True
                store = ConnectionStore(path, root / "settings.json", root / "statistics.json",
                                        root / "instance.lock", root / "history.jsonl")
            self.addCleanup(store.close)
            self.assertEqual(store.data.local_terminals[0].password, "")
            self.assertEqual(path.read_text(), original)

    def test_active_pane_password_and_unavailable_cases(self):
        root_terminal, target = FakeTerminal(), FakeTerminal()
        root = make_pane(root_terminal, "root", server_id="ssh")
        pane = make_pane(target, "split")
        pane.local_profile_id = "local"
        session = make_session(root_terminal, root)
        session.panes[id(target)] = pane
        host = TerminalSessionsMixin()
        profile = LocalTerminalProfile("local", "Shell", password=" synthetic-ñ ")
        host.store = SimpleNamespace(data=SimpleNamespace(
            servers=[Server("ssh", "SSH", "example.invalid", "tester", password="ssh-secret")],
            local_terminals=[profile], app=SimpleNamespace(send_password_enter=False),
        ))
        host.toast_label = Mock()
        host.t = lambda key: key
        for enter in (False, True):
            target.output = b""
            host.store.data.app.send_password_enter = enter
            host.send_saved_password(session, target)
            self.assertEqual(target.output, profile.password.encode() + (b"\r" if enter else b""))
            self.assertEqual(root_terminal.output, b"")
        pane.server_id = "ssh"
        target.output = b""
        host.send_saved_password(session, target)
        self.assertEqual(target.output, b"ssh-secret\r")
        pane.server_id = None
        for case in ("unsaved", "deleted", "empty", "exited", "missing-ssh"):
            with self.subTest(case=case):
                pane.connected = case != "exited"
                pane.local_profile_id = {"unsaved": None, "deleted": "deleted"}.get(case, "local")
                profile.password = "" if case == "empty" else "synthetic"
                pane.server_id = "missing" if case == "missing-ssh" else None
                target.output = b""
                host.send_saved_password(session, target)
                self.assertEqual(target.output, b"")
                host.toast_label.set_warning.assert_called_with("send_credential_unavailable")

    def test_profile_clone_preserves_password(self):
        profile = LocalTerminalProfile("local", "Shell", password=" synthetic ")
        host = SimpleNamespace(
            store=Mock(), ensure_writable=lambda: True, t=lambda key: key,
            toast_label=Mock(), refresh_list=Mock(), render_detail=Mock(),
        )
        host.store.data.local_terminals = [profile]
        host.store.add_local_terminal.return_value = LocalTerminalProfile("clone", "Copy")
        SidebarMixin.on_local_terminal_context_clone(host, Mock(), profile.id)
        self.assertEqual(host.store.add_local_terminal.call_args.kwargs["password"], profile.password)

    def test_local_password_form_create_edit_clear_and_cancel(self):
        class Host(ConnectionDialogsMixin, Gtk.Window):
            def __init__(self):
                super().__init__()
                self.store = Mock()
                self.toast_label = Mock()
                self.refresh_list = Mock()

            def t(self, key):
                return key

            def ensure_writable(self):
                return True

            def default_local_terminal_shell(self):
                return "/bin/sh"

            def add_dialog_action_buttons(self, dialog, label):
                dialog.add_button(label, Gtk.ResponseType.OK)

        host = Host()
        self.addCleanup(host.destroy)
        profile = LocalTerminalProfile("local", "Shell", shell="/bin/sh", password=" synthetic ")
        for existing, response, password in (
            (None, Gtk.ResponseType.OK, " new "),
            (profile, Gtk.ResponseType.OK, " changed "),
            (profile, Gtk.ResponseType.OK, ""),
            (profile, Gtk.ResponseType.CANCEL, " discarded "),
        ):
            with self.subTest(edit=existing is not None, response=response, password=password):
                host.store.reset_mock()
                dialog = DialogWindow(transient_for=host)
                self.addCleanup(dialog.destroy)
                with patch("termia.connection_dialogs.DialogWindow", return_value=dialog):
                    host.show_local_terminal_dialog(existing)
                grid = dialog.get_content_area().get_first_child()
                entry = grid.get_child_at(1, 7)
                self.assertIsInstance(entry, Gtk.PasswordEntry)
                self.assertTrue(entry.get_show_peek_icon())
                self.assertEqual(entry.get_text(), existing.password if existing else "")
                grid.get_child_at(1, 0).set_text("Shell")
                entry.set_text(password)
                dialog.response(response)
                if response == Gtk.ResponseType.CANCEL:
                    host.store.add_local_terminal.assert_not_called()
                    host.store.update_local_terminal.assert_not_called()
                else:
                    method = host.store.update_local_terminal if existing else host.store.add_local_terminal
                    self.assertEqual(method.call_args.kwargs["password"], password)
