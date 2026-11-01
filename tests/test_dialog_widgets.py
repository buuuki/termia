import unittest

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from termia.choice_widgets import (
    append_choice,
    choice_id,
    choice_text,
    clear_choices,
    select_choice,
    text_choice,
)
from termia.dialog_window import DialogWindow


class DialogWidgetTests(unittest.TestCase):
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
