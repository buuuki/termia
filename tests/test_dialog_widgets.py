import gc
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from termia.app import TermiaApp
from termia.choice_widgets import (
    append_choice,
    choice_id,
    choice_text,
    clear_choices,
    select_choice,
    text_choice,
)
from termia.connection_dialogs import ConnectionDialogsMixin
from termia.dialog_window import DialogWindow
from termia.models import Server


class DialogWidgetTests(unittest.TestCase):
    def test_connection_key_picker_selection_cancel_remote_and_closed_form(self):
        parent = DialogWindow()
        entry = Gtk.Entry(text="/synthetic/previous-key")
        parent.get_content_area().append(entry)
        parent.present()
        self.addCleanup(parent.destroy)
        host = SimpleNamespace(t=lambda key: key)
        picker = Mock()
        with patch("termia.connection_dialogs.Gtk.FileDialog", return_value=picker):
            ConnectionDialogsMixin.select_private_ssh_key(host, parent, entry)
        self.assertEqual(picker.set_initial_file.call_args.args[0].get_path(), "/synthetic/previous-key")
        self.assertIs(picker.open.call_args.args[0], parent)
        selected = picker.open.call_args.args[2]
        picker.open_finish.side_effect = GLib.Error("Cancelled")
        selected(picker, None)
        self.assertEqual(entry.get_text(), "/synthetic/previous-key")
        picker.open_finish.side_effect = None
        picker.open_finish.return_value = Gio.File.new_for_uri("sftp://example.invalid/key")
        selected(picker, None)
        self.assertEqual(entry.get_text(), "/synthetic/previous-key")
        picker.open_finish.return_value = Gio.File.new_for_path("/synthetic/key with spaces")
        selected(picker, None)
        self.assertEqual(entry.get_text(), "/synthetic/key with spaces")
        parent.destroy()
        picker.open_finish.return_value = Gio.File.new_for_path("/synthetic/late-key")
        selected(picker, None)
        self.assertEqual(entry.get_text(), "/synthetic/key with spaces")

    def test_connection_forms_preserve_manual_key_and_wire_picker_for_create_and_edit(self):
        class Host(ConnectionDialogsMixin, Gtk.Window):
            def __init__(self):
                super().__init__()
                self.store = Mock()
                self.store.data.groups = []
                self.toast_label = Mock()
                self.refresh_list = Mock()
                self.select_private_ssh_key = Mock()

            def t(self, key):
                return key

            def ensure_writable(self):
                return True

            def add_dialog_action_buttons(self, dialog, label):
                dialog.add_button(label, Gtk.ResponseType.OK)

        host = Host()
        self.addCleanup(host.destroy)
        server = Server("test", "Example", "example.invalid", "tester", public_key="/synthetic/key")
        for existing in (None, server):
            with self.subTest(edit=existing is not None):
                dialog = DialogWindow(transient_for=host)
                self.addCleanup(dialog.destroy)
                with patch("termia.connection_dialogs.DialogWindow", return_value=dialog):
                    host.show_server_dialog(existing)
                self.assertTrue(dialog.get_child().has_css_class("termia-dialog-panel"))
                save = dialog.get_widget_for_response(Gtk.ResponseType.OK)
                self.assertIs(save.get_parent().get_parent(), dialog.get_child())
                grid = dialog.get_content_area().get_first_child()
                field = grid.get_child_at(1, 6)
                entry = field.get_first_child()
                self.assertEqual(entry.get_text(), existing.public_key if existing else "")
                field.get_last_child().emit("clicked")
                host.select_private_ssh_key.assert_called_with(dialog, entry)
                for row, text in ((0, "Example"), (1, "example.invalid"), (2, "tester")):
                    grid.get_child_at(1, row).set_text(text)
                entry.set_text("/synthetic/manual-key")
                dialog.response(Gtk.ResponseType.OK)
                if existing:
                    self.assertEqual(host.store.update_server.call_args.args[8], "/synthetic/manual-key")
                else:
                    self.assertEqual(host.store.add_server.call_args.args[7], "/synthetic/manual-key")

    def test_application_keeps_label_focus_without_automatic_selection(self):
        settings = Gtk.Settings.get_default()
        previous = settings.get_property("gtk-label-select-on-focus")
        self.addCleanup(settings.set_property, "gtk-label-select-on-focus", previous)
        settings.set_property("gtk-label-select-on-focus", True)
        app = TermiaApp()
        app.set_application_id("local.termia.LabelSelectionTest")
        self.assertTrue(app.register(None))
        self.addCleanup(app.quit)
        self.assertFalse(settings.get_property("gtk-label-select-on-focus"))
        window = Gtk.ApplicationWindow(application=app)
        self.addCleanup(window.destroy)
        label = Gtk.Label(label="/synthetic/settings.json", selectable=True)
        window.set_child(label)
        window.present()
        loop = GLib.MainLoop()
        GLib.timeout_add(100, lambda: (loop.quit(), False)[1])
        loop.run()
        self.assertIs(window.get_focus(), label)
        self.assertFalse(label.get_selection_bounds()[0])
        self.assertTrue(label.grab_focus())
        label.select_region(0, -1)
        self.assertTrue(label.get_selection_bounds()[0])

    def test_buttons_and_escape_survive_release_of_python_window_reference(self):
        responses = []

        def present_window():
            dialog = DialogWindow()
            dialog.connect("response", lambda _window, result: responses.append(result))
            button = dialog.add_button("Save", Gtk.ResponseType.OK)
            controllers = dialog.observe_controllers()
            keys = next(controllers.get_item(index) for index in range(controllers.get_n_items())
                        if isinstance(controllers.get_item(index), Gtk.EventControllerKey))
            dialog.present()
            return button, keys

        button, keys = present_window()
        gc.collect()
        self.addCleanup(button.get_root().destroy)
        button.emit("clicked")
        self.assertEqual(responses, [Gtk.ResponseType.OK])
        self.assertFalse(keys.emit("key-pressed", Gdk.KEY_a, 0, Gdk.ModifierType(0)))
        self.assertTrue(keys.emit("key-pressed", Gdk.KEY_Escape, 0, Gdk.ModifierType(0)))
        self.assertEqual(responses, [Gtk.ResponseType.OK, Gtk.ResponseType.CANCEL])

    def test_response_buttons_default_and_disabled_action(self):
        parent = Gtk.Window()
        dialog = DialogWindow(transient_for=parent, modal=True)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialog.destroy)
        responses = []
        dialog.connect("response", lambda _window, result: responses.append(result))
        button = dialog.add_button("Save", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        self.assertIs(dialog.get_default_widget(), button)
        self.assertIs(dialog.get_transient_for(), parent)
        self.assertTrue(dialog.get_modal())
        button.emit("clicked")
        self.assertEqual(responses, [Gtk.ResponseType.OK])
        dialog.set_response_sensitive(Gtk.ResponseType.OK, False)
        self.assertFalse(button.get_sensitive())
        self.assertIsNone(dialog.get_widget_for_response(Gtk.ResponseType.APPLY))

    def test_escape_and_window_close_have_distinct_responses(self):
        dialog = DialogWindow()
        self.addCleanup(dialog.destroy)
        responses = []
        dialog.connect("response", lambda _window, result: responses.append(result))
        self.assertFalse(dialog._on_key_pressed(None, Gdk.KEY_a, 0, 0))
        self.assertTrue(dialog._on_key_pressed(None, Gdk.KEY_Escape, 0, 0))
        self.assertFalse(dialog._on_close_request(dialog))
        self.assertEqual(responses, [Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT])

    def test_choice_ids_survive_labels_rebuild_and_empty_model(self):
        widget = text_choice()
        self.assertIsInstance(widget, Gtk.DropDown)
        append_choice(widget, "one", "Traducido")
        append_choice(widget, "two", "Traducido")
        self.assertTrue(select_choice(widget, "two"))
        self.assertEqual(choice_id(widget), "two")
        self.assertEqual(choice_text(widget), "Traducido")
        self.assertFalse(select_choice(widget, "missing"))
        self.assertEqual(choice_id(widget), "two")
        clear_choices(widget)
        self.assertIsNone(choice_id(widget))
        self.assertIsNone(choice_text(widget))
        append_choice(widget, "two", "Rebuilt")
        self.assertTrue(select_choice(widget, "two"))
        self.assertEqual(choice_text(widget), "Rebuilt")
