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

    def test_closed_menu_resets_visible_submenu(self) -> None:
        popover = self.host.build_main_menu(self.actions, write_allowed=True)

        def find_stack(widget):
            if isinstance(widget, Gtk.Stack):
                return widget
            child = widget.get_first_child()
            while child is not None:
                found = find_stack(child)
                if found is not None:
                    return found
                child = child.get_next_sibling()
            return None

        stack = find_stack(popover)
        self.assertIsNotNone(stack)
        pages = stack.get_pages()
        submenu = next(
            pages.get_item(i).get_name() for i in range(pages.get_n_items())
            if pages.get_item(i).get_name() != "main"
        )
        popover.set_property("visible-submenu", submenu)
        self.assertEqual(popover.get_property("visible-submenu"), submenu)
        popover.emit("closed")
        self.assertEqual(popover.get_property("visible-submenu"), "main")
