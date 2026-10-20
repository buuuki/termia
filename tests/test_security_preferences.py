import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from termia.config_io import CONNECTION_STORAGE_ENCRYPTED, InvalidMasterPasswordError
from termia.dialog_actions import add_dialog_action_button
from termia.i18n import translate_key
from termia.security_preferences import SecurityPreferencesMixin
from termia.stores import ReadOnlyStoreError, UnchangedMasterPasswordError


class SecurityPreferencesTests(unittest.TestCase):
    def response(
        self,
        result,
        *,
        current="old master",
        new="new master",
        confirm="new master",
        store_error=None,
    ):
        dialog = Mock()
        entries = [Mock() for _ in range(3)]
        for entry, value in zip(entries, (current, new, confirm)):
            entry.get_text.return_value = value
        error = Mock()
        store = Mock()
        store.change_master_password.side_effect = store_error
        toast = Mock()
        host = SimpleNamespace(
            store=store,
            toast_label=toast,
            t=lambda key: key,
        )

        SecurityPreferencesMixin.on_change_master_password_response(
            host, dialog, result, *entries, error,
        )
        return store, toast, dialog, entries, error

    def test_cancelling_password_change_does_not_call_store(self):
        store, _toast, dialog, entries, _error = self.response(Gtk.ResponseType.CANCEL)

        store.change_master_password.assert_not_called()
        dialog.destroy.assert_called_once()
        for entry in entries:
            entry.set_text.assert_called_once_with("")

    def test_wrong_current_password_is_reported_and_fields_are_cleared(self):
        store, _toast, dialog, entries, error = self.response(
            Gtk.ResponseType.OK, store_error=InvalidMasterPasswordError(),
        )

        error.set_label.assert_called_once_with("change_master_password_wrong_current")
        for entry in entries:
            entry.set_text.assert_called_with("")
        dialog.destroy.assert_not_called()

    def test_success_changes_password_and_closes_dialog(self):
        store, toast, dialog, _entries, _error = self.response(Gtk.ResponseType.OK)

        store.change_master_password.assert_called_once_with("old master", "new master")
        dialog.destroy.assert_called_once()
        toast.set_label.assert_called_once_with("security_settings_saved")

    def test_new_password_must_differ_from_current(self):
        store, _toast, dialog, entries, error = self.response(
            Gtk.ResponseType.OK, current="same password", new="same password",
            confirm="same password", store_error=UnchangedMasterPasswordError(),
        )

        error.set_label.assert_called_once_with("change_master_password_same")
        entries[0].set_text.assert_not_called()
        entries[1].set_text.assert_called_once_with("")
        entries[2].set_text.assert_called_once_with("")
        dialog.destroy.assert_not_called()

    def test_read_only_error_is_reported_and_dialog_closes(self):
        _store, toast, dialog, _entries, _error = self.response(
            Gtk.ResponseType.OK, store_error=ReadOnlyStoreError(),
        )

        toast.set_label.assert_called_once_with("read_only_mode_enabled")
        dialog.destroy.assert_called_once()


@unittest.skipUnless(
    (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check(),
    "GTK display unavailable",
)
class SecurityPreferencesUITests(unittest.TestCase):
    class Host(Gtk.Window, SecurityPreferencesMixin):
        def __init__(self, storage_mode):
            super().__init__()
            self.store = SimpleNamespace(
                read_only=False,
                encryption_locked=False,
                data=SimpleNamespace(app=SimpleNamespace(connection_storage_mode=storage_mode)),
            )
            self.toast_label = Gtk.Label()

        def t(self, key):
            return translate_key(key, "en")

        def ensure_writable(self):
            return True

        def add_dialog_action_buttons(self, dialog, save_label):
            add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL)
            add_dialog_action_button(dialog, save_label, Gtk.ResponseType.OK)

    def widgets(self, root):
        child = root.get_first_child()
        while child is not None:
            yield child
            yield from self.widgets(child)
            child = child.get_next_sibling()

    def security_dialog(self, host):
        host.on_security_settings(None)
        dialog = next(
            window for window in Gtk.Window.list_toplevels()
            if isinstance(window, Gtk.Dialog) and window.get_title() == host.t("security")
        )
        self.addCleanup(dialog.destroy)
        return dialog

    def test_encrypted_storage_offers_change_password_flow(self):
        host = self.Host(CONNECTION_STORAGE_ENCRYPTED)
        self.addCleanup(host.destroy)
        settings_dialog = self.security_dialog(host)
        button = next(
            widget for widget in self.widgets(settings_dialog)
            if isinstance(widget, Gtk.Button)
            and widget.get_label() == host.t("change_master_password")
        )

        button.emit("clicked")

        dialog = next(
            window for window in Gtk.Window.list_toplevels()
            if isinstance(window, Gtk.Dialog)
            and window.get_title() == host.t("change_master_password_title")
        )
        self.addCleanup(dialog.destroy)
        entries = [widget for widget in self.widgets(dialog) if isinstance(widget, Gtk.PasswordEntry)]
        self.assertEqual(len(entries), 3)

    def test_unencrypted_storage_does_not_offer_password_change(self):
        host = self.Host("plain")
        self.addCleanup(host.destroy)
        dialog = self.security_dialog(host)

        self.assertFalse(any(
            isinstance(widget, Gtk.Button)
            and widget.get_label() == host.t("change_master_password")
            for widget in self.widgets(dialog)
        ))
