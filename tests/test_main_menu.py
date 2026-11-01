import os
import unittest
from dataclasses import fields
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from termia.main_menu import MainMenuMixin
from termia.main_menu_actions import MainMenuActions


class FakePopover:
    def __init__(self) -> None:
        self.properties = {}

    def set_property(self, name, value) -> None:
        self.properties[name] = value


class FakeActionArea:
    def __init__(self) -> None:
        self.layout = {}

    def set_spacing(self, value: int) -> None:
        self.layout["spacing"] = value

    def set_margin_top(self, value: int) -> None:
        self.layout["top"] = value

    def set_margin_bottom(self, value: int) -> None:
        self.layout["bottom"] = value

    def set_margin_start(self, value: int) -> None:
        self.layout["start"] = value

    def set_margin_end(self, value: int) -> None:
        self.layout["end"] = value


class FakeButton:
    def __init__(self, action_area: FakeActionArea) -> None:
        self.action_area = action_area

    def get_parent(self) -> FakeActionArea:
        return self.action_area


class FakeDialog:
    def __init__(self) -> None:
        self.action_area = FakeActionArea()
        self.button = FakeButton(self.action_area)

    def add_button(self, _label: str, _response: int) -> FakeButton:
        return self.button


class MainMenuResetTests(unittest.TestCase):
    def test_about_is_independent_of_main_window(self) -> None:
        host = MainMenuMixin()
        host.t = lambda key: key
        with (
            patch("termia.main_menu.Gtk.AboutDialog") as about,
            patch("termia.main_menu.ABOUT_IMAGE") as image,
            patch("termia.update_view.attach_updates"),
        ):
            image.exists.return_value = False
            host.on_about(None)

        about.assert_called_once_with(modal=False)
        about.return_value.set_destroy_with_parent.assert_not_called()
        about.return_value.present.assert_called_once_with()

    def test_reset_main_menu_returns_to_top_level_without_replacing_content(self) -> None:
        popover = FakePopover()
        MainMenuMixin().reset_main_menu(popover)
        self.assertEqual(popover.properties, {"visible-submenu": "main"})

    def test_callback_waits_until_after_popover_closes(self) -> None:
        popover, callback = Mock(), Mock()
        with patch("termia.main_menu.GLib.timeout_add") as schedule:
            MainMenuMixin().run_action_after_popover_closed(popover, callback)
            popover.popdown.assert_called_once_with()
            callback.assert_not_called()
            delay, deferred = schedule.call_args.args
            self.assertEqual(delay, MainMenuMixin.POPOVER_CALLBACK_DELAY_MS)
            self.assertEqual(deferred(), GLib.SOURCE_REMOVE)
        callback.assert_called_once_with()

    def test_dialog_action_buttons_configure_the_shared_action_area(self) -> None:
        host = MainMenuMixin()
        dialog = FakeDialog()

        with patch("termia.dialog_actions.Gtk") as gtk:
            gtk.Box = FakeActionArea
            host.add_dialog_action_button(dialog, "Cancel", -6)

        self.assertEqual(
            dialog.action_area.layout,
            {"spacing": 8, "top": 16, "bottom": 16, "start": 16, "end": 16},
        )


@unittest.skipUnless(
    (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check(),
    "GTK display unavailable",
)
class MainMenuUITests(unittest.TestCase):
    def setUp(self) -> None:
        class Host(MainMenuMixin):
            t = staticmethod(lambda key: key)

        self.host = Host()
        self.actions = MainMenuActions(**{
            field.name: Mock() for field in fields(MainMenuActions)
        })

    def test_about_preserves_manual_selection_without_initial_highlight(self) -> None:
        settings = Gtk.Settings.get_default()
        previous = settings.get_property("gtk-label-select-on-focus")
        self.addCleanup(settings.set_property, "gtk-label-select-on-focus", previous)
        settings.set_property("gtk-label-select-on-focus", False)
        existing = Gtk.Window.list_toplevels()
        with patch("termia.update_view.attach_updates"):
            self.host.on_about(None)
        dialog = next(window for window in Gtk.Window.list_toplevels()
                      if isinstance(window, Gtk.AboutDialog) and window not in existing)
        self.addCleanup(dialog.destroy)
        self.assertIsNotNone(dialog.get_logo())
        loop = GLib.MainLoop()
        GLib.timeout_add(150, lambda: (loop.quit(), False)[1])
        loop.run()

        def labels(widget):
            if isinstance(widget, Gtk.Label):
                yield widget
            child = widget.get_first_child()
            while child is not None:
                yield from labels(child)
                child = child.get_next_sibling()

        selectable = [label for label in labels(dialog) if label.get_selectable() and label.get_mapped()]
        self.assertTrue(selectable)
        self.assertTrue(all(not label.get_selection_bounds()[0] for label in selectable))
        selectable[0].select_region(0, -1)
        self.assertTrue(selectable[0].get_selection_bounds()[0])

    def test_every_command_dispatches_only_its_injected_callback(self) -> None:
        popover = self.host.build_main_menu(self.actions, write_allowed=True)
        self.assertIsInstance(popover, Gtk.PopoverMenu)
        with patch.object(self.host, "run_action_after_popover_closed") as dispatch:
            for field in fields(MainMenuActions):
                with self.subTest(action=field.name):
                    self.assertTrue(popover.activate_action(f"main-menu.{field.name}", None))
                    dispatch.assert_called_once_with(popover, getattr(self.actions, field.name))
                    dispatch.reset_mock()

    def test_blocked_menu_disables_writes_but_keeps_read_commands_available(self) -> None:
        blocked = {
            "general_preferences", "terminal_settings", "keybinding_settings",
            "security_settings", "manage_snippets", "import_config",
            "import_asbru_config", "clear_config",
        }
        for write_allowed in (False, True):
            popover = self.host.build_main_menu(self.actions, write_allowed=write_allowed)
            with patch.object(self.host, "run_action_after_popover_closed") as dispatch:
                for field in fields(MainMenuActions):
                    with self.subTest(write_allowed=write_allowed, action=field.name):
                        popover.activate_action(f"main-menu.{field.name}", None)
                        self.assertEqual(
                            dispatch.call_count,
                            int(write_allowed or field.name not in blocked),
                        )
                        dispatch.reset_mock()

    def test_sections_order_and_connection_submenu_preserve_commands(self) -> None:
        popover = self.host.build_main_menu(self.actions, write_allowed=True)
        model = popover.get_menu_model()
        self.assertEqual(model.get_n_items(), 4)
        sections = [model.get_item_link(i, Gio.MENU_LINK_SECTION) for i in range(4)]

        def labels(menu):
            return [menu.get_item_attribute_value(i, "label", None).unpack()
                    for i in range(menu.get_n_items())]

        self.assertEqual(labels(sections[0]), [
            "general", "terminal", "keybindings", "security", "optional_tools",
        ])
        self.assertEqual(labels(sections[1]), [
            "manage_snippets", "manage_notes", "statistics", "connection_history",
        ])
        self.assertEqual(labels(sections[2]), ["data_locations", "connections_file"])
        self.assertEqual(labels(sections[3]), ["help", "about"])
        connections = sections[2].get_item_link(1, Gio.MENU_LINK_SUBMENU)
        self.assertEqual(labels(connections), [
            "export_config", "import_config", "import_asbru", "clear_config",
        ])

    def test_connection_submenu_opens_beside_main_menu_and_resets_on_close(self) -> None:
        popover = self.host.build_main_menu(self.actions, write_allowed=True)
        self.assertTrue(popover.get_flags() & Gtk.PopoverMenuFlags.NESTED)
        window = Gtk.Window()
        self.addCleanup(window.destroy)
        button = Gtk.MenuButton(label="Menu")
        button.set_popover(popover)
        window.set_child(button)
        window.present()
        popover.popup()

        def settle():
            loop = GLib.MainLoop()
            GLib.timeout_add(100, lambda: (loop.quit(), False)[1])
            loop.run()

        def descendants(widget):
            yield widget
            child = widget.get_first_child()
            while child is not None:
                yield from descendants(child)
                child = child.get_next_sibling()

        settle()
        label = next(item for item in descendants(popover)
                     if isinstance(item, Gtk.Label) and item.get_label() == "connections_file")
        row = label.get_parent()
        while row is not None and row.get_css_name() != "modelbutton":
            row = row.get_parent()
        self.assertIsNotNone(row)
        self.assertTrue(row.activate())
        settle()
        submenu = next(item for item in descendants(popover)
                       if isinstance(item, Gtk.Popover) and item is not popover and item.get_visible())
        self.assertTrue(popover.get_visible())
        self.assertTrue(popover.get_autohide())
        self.assertFalse(submenu.get_autohide())
        self.assertTrue(submenu.get_has_arrow())
        self.assertTrue(window.get_focus().is_ancestor(submenu))
        submenu.popdown()
        settle()
        self.assertTrue(popover.get_visible())
        self.assertIs(window.get_focus(), row)
        self.assertTrue(row.activate())
        settle()
        self.assertTrue(submenu.get_visible())
        popover.popdown()
        settle()
        popover.popup()
        settle()
        self.assertFalse(submenu.get_visible())
        self.assertEqual(popover.get_property("visible-submenu"), "main")
