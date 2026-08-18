import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.models import Server
from termia.sidebar import SidebarMixin
from termia.sidebar_projection import SidebarRow


class FakeWidget:
    def __init__(self) -> None:
        self.focused = False
        self.classes: set[str] = set()

    def add_css_class(self, name: str) -> None:
        self.classes.add(name)

    def remove_css_class(self, name: str) -> None:
        self.classes.discard(name)

    def grab_focus(self) -> None:
        self.focused = True


class SidebarNavigationTests(unittest.TestCase):
    def build_host(self, rows: list[SidebarRow]):
        server = Server(id="current", name="Current", host="current.test", user="user")

        class Host(SidebarMixin):
            def __init__(self) -> None:
                self.visible_tree_rows = rows
                self.tree_widgets = {
                    (row.kind, row.item_id): FakeWidget() for row in rows
                }
                self.selected = None
                self.selected_tree_widget = None
                self.store = SimpleNamespace(data=SimpleNamespace(servers=[server]))
                self.opened = None

            def cancel_sidebar_scroll_restore(self) -> None:
                pass

            def select_tree_row(self, row, widget, preserve_scroll=True) -> None:
                self.selected = row
                self.selected_tree_widget = widget
                widget.add_css_class("selected")

            def open_terminal_tab(self, selected_server) -> None:
                self.opened = selected_server

        return Host(), server

    def test_enter_replaces_stale_selection_with_first_visible_result(self) -> None:
        current = SidebarRow("server", "current", "Current")
        host, server = self.build_host([current])
        host.selected = SidebarRow("server", "previous", "Previous")

        activated = host.activate_selected_tree_row()

        self.assertTrue(activated)
        self.assertEqual(host.selected, current)
        self.assertIs(host.opened, server)

    def test_enter_with_no_results_does_not_activate_stale_selection(self) -> None:
        host, _server = self.build_host([])
        host.selected = SidebarRow("server", "previous", "Previous")

        activated = host.activate_selected_tree_row()

        self.assertFalse(activated)
        self.assertIsNone(host.opened)

    def test_activation_rejects_selection_removed_during_result_resolution(self) -> None:
        current = SidebarRow("server", "current", "Current")
        host, _server = self.build_host([current])
        host.selected = current
        host.get_visible_tree_row_index = lambda _row: None
        host.select_visible_tree_row = lambda _index: False

        activated = host.activate_selected_tree_row()

        self.assertFalse(activated)
        self.assertIsNone(host.opened)

    def test_server_scp_action_uses_no_session_context(self) -> None:
        host, server = self.build_host([])
        popover = Mock()
        host.on_send_files_to_server = Mock()

        host.on_server_context_send_files(None, popover, server.id)

        host.on_send_files_to_server.assert_called_once_with(popover, None, server)
