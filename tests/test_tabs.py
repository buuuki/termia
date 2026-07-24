import unittest
from types import SimpleNamespace
from unittest.mock import patch

from termia.tabs import TabsMixin


class FakePopover:
    def __init__(self) -> None:
        self.closed = False

    def popdown(self) -> None:
        self.closed = True


class FakeWindow:
    def __init__(self, **_kwargs) -> None:
        self.child = None
        self.presented = False

    def set_handle_menubar_accel(self, _enabled: bool) -> None:
        pass

    def set_default_size(self, _width: int, _height: int) -> None:
        pass

    def set_child(self, child) -> None:
        self.child = child

    def connect(self, *_args) -> None:
        pass

    def present(self) -> None:
        self.presented = True


class DetachTabTests(unittest.TestCase):
    def test_detach_tab_keeps_previous_order_for_focus_selection(self) -> None:
        session = SimpleNamespace(
            id="detached",
            title="Detached",
            page=object(),
            detached_window=None,
        )
        previous_session = SimpleNamespace(
            id="previous",
            detached_window=None,
        )

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.open_tabs = {session.id: session, previous_session.id: previous_session}
                self.focused = None
                self.removed = None
                self.visible_sessions = [previous_session, session]

            def visible_sessions_in_tab_order(self):
                return self.visible_sessions

            def remove_session_from_main_view(self, current_session) -> None:
                self.removed = current_session

            def focus_available_session_after_close(self, closed_id, previous_order) -> None:
                self.focused = (closed_id, previous_order)

            def update_session_tab_bar_visibility(self) -> None:
                pass

            def sync_window_title_with_visible_session(self) -> None:
                pass

        host = Host()
        popover = FakePopover()
        with patch("termia.tabs.Gtk.Window", FakeWindow):
            host.detach_tab(popover, session)

        self.assertTrue(popover.closed)
        self.assertIs(host.removed, session)
        self.assertEqual(host.focused, (session.id, [previous_session, session]))
        self.assertIsInstance(session.detached_window, FakeWindow)
        self.assertTrue(session.detached_window.presented)
