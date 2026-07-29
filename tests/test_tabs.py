import unittest
from types import SimpleNamespace
from unittest.mock import patch

from termia.session_registry import SessionRegistry
from termia.tab_lifecycle_actions import TabLifecycleActions
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
                self.session_registry = SessionRegistry([session, previous_session])
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


class DuplicateTabTests(unittest.TestCase):
    def test_duplicate_tab_closes_popover_and_dispatches_lifecycle_action(self) -> None:
        session = SimpleNamespace(id="duplicate")
        duplicated = []

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.tab_lifecycle_actions = TabLifecycleActions(
                    duplicate_session=duplicated.append,
                    disconnect_session=lambda _session: None,
                    terminate_split_processes=lambda _session: None,
                    confirm_session_action=lambda *_args: None,
                )

        host = Host()
        popover = FakePopover()
        host.duplicate_tab(popover, session)

        self.assertTrue(popover.closed)
        self.assertEqual(duplicated, [session])


class CloseTabTests(unittest.TestCase):
    def test_close_tab_removes_only_the_closed_session_from_registry(self) -> None:
        page = object()
        session = SimpleNamespace(
            id="closed",
            page=page,
            connected=True,
            detached_window=None,
        )
        remaining_session = SimpleNamespace(
            id="remaining",
            detached_window=None,
        )

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session, remaining_session])
                self.removed = None
                self.focused = None
                self.terminated = None
                self.disconnected = None
                self.tab_lifecycle_actions = TabLifecycleActions(
                    duplicate_session=lambda _session: None,
                    disconnect_session=self.disconnect_session,
                    terminate_split_processes=self.terminate_split_processes,
                    confirm_session_action=lambda *_args: None,
                )

            def visible_sessions_in_tab_order(self):
                return [session, remaining_session]

            def terminate_split_processes(self, current_session) -> None:
                self.terminated = current_session

            def disconnect_session(self, current_session) -> None:
                self.disconnected = current_session
                current_session.connected = False

            def remove_session_from_main_view(self, current_session) -> None:
                self.removed = current_session

            def update_session_tab_bar_visibility(self) -> None:
                pass

            def focus_available_session_after_close(self, closed_id, previous_order) -> None:
                self.focused = (closed_id, previous_order)

            def sync_window_title_with_visible_session(self) -> None:
                pass

        host = Host()
        host.close_tab(session.id, page, disconnect=True)

        self.assertIs(host.disconnected, session)
        self.assertIs(host.removed, session)
        self.assertIs(host.terminated, session)
        self.assertIsNone(host.session_registry.get(session.id))
        self.assertIs(host.session_registry.get(remaining_session.id), remaining_session)
        self.assertEqual(host.focused, (session.id, [session, remaining_session]))


class MiddleClickTabTests(unittest.TestCase):
    def test_middle_click_requests_tab_close(self) -> None:
        page = object()

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.closed = None

            def request_close_tab(self, session_id, clicked_page) -> None:
                self.closed = (session_id, clicked_page)

        host = Host()
        host.on_tab_middle_press(None, 1, 0.0, 0.0, "session", page)

        self.assertEqual(host.closed, ("session", page))
