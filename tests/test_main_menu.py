import unittest
from types import SimpleNamespace
from unittest.mock import patch

from termia.main_menu import MainMenuMixin


class FakePopover:
    def __init__(self) -> None:
        self.child = None

    def set_child(self, child) -> None:
        self.child = child


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
    def test_reset_main_menu_replaces_submenu_with_top_level_content(self) -> None:
        actions = SimpleNamespace()
        popover = FakePopover()

        class Host(MainMenuMixin):
            def build_main_menu_content(self, current_popover, current_actions):
                return (current_popover, current_actions)

        MainMenuMixin.reset_main_menu(Host(), popover, actions)

        self.assertEqual(popover.child, (popover, actions))

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
