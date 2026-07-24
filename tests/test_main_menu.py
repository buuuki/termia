import unittest
from types import SimpleNamespace

from termia.main_menu import MainMenuMixin


class FakePopover:
    def __init__(self) -> None:
        self.child = None

    def set_child(self, child) -> None:
        self.child = child


class MainMenuResetTests(unittest.TestCase):
    def test_reset_main_menu_replaces_submenu_with_top_level_content(self) -> None:
        actions = SimpleNamespace()
        popover = FakePopover()

        class Host(MainMenuMixin):
            def build_main_menu_content(self, current_popover, current_actions):
                return (current_popover, current_actions)

        MainMenuMixin.reset_main_menu(Host(), popover, actions)

        self.assertEqual(popover.child, (popover, actions))
