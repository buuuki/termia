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


class FakeTab:
    def __init__(self) -> None:
        self.next_sibling = None

    def get_next_sibling(self):
        return self.next_sibling


class FakeTabBar:
    def __init__(self, tabs) -> None:
        self.first_child = tabs[0] if tabs else None
        for current, following in zip(tabs, tabs[1:]):
            current.next_sibling = following

    def get_first_child(self):
        return self.first_child


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


class TabOverflowTests(unittest.TestCase):
    def test_overflow_order_matches_visual_tab_order_and_skips_detached_tabs(self) -> None:
        first_tab = FakeTab()
        second_tab = FakeTab()
        detached_tab = FakeTab()
        first = SimpleNamespace(id="first", tab_label=first_tab, detached_window=None)
        second = SimpleNamespace(id="second", tab_label=second_tab, detached_window=None)
        detached = SimpleNamespace(id="detached", tab_label=detached_tab, detached_window=object())

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([first, detached, second])
                self.session_tab_bar = FakeTabBar([second_tab, detached_tab, first_tab])

        self.assertEqual(Host().visible_sessions_in_tab_order(), [second, first])

    def test_overflow_item_activates_selected_session_after_closing_popover(self) -> None:
        class Host(TabsMixin):
            def __init__(self) -> None:
                self.activated = None

            def set_active_session(self, session_id: str) -> None:
                self.activated = session_id

        host = Host()
        popover = FakePopover()

        host.on_tab_overflow_item_clicked(None, "selected", popover)

        self.assertTrue(popover.closed)
        self.assertEqual(host.activated, "selected")

    def test_reveal_scrolls_right_until_active_tab_is_fully_visible(self) -> None:
        value = TabsMixin.tab_reveal_scroll_value(
            current=100,
            page_size=300,
            lower=0,
            upper=1000,
            tab_start=380,
            tab_end=498,
        )

        self.assertEqual(value, 198)

    def test_reveal_scrolls_left_to_active_tab_start(self) -> None:
        value = TabsMixin.tab_reveal_scroll_value(
            current=300,
            page_size=300,
            lower=0,
            upper=1000,
            tab_start=118,
            tab_end=236,
        )

        self.assertEqual(value, 118)

    def test_reveal_keeps_scroll_when_active_tab_is_visible(self) -> None:
        value = TabsMixin.tab_reveal_scroll_value(
            current=100,
            page_size=300,
            lower=0,
            upper=1000,
            tab_start=150,
            tab_end=268,
        )

        self.assertEqual(value, 100)

    def test_reveal_clamps_scroll_to_adjustment_upper_bound(self) -> None:
        value = TabsMixin.tab_reveal_scroll_value(
            current=600,
            page_size=300,
            lower=0,
            upper=800,
            tab_start=720,
            tab_end=838,
        )

        self.assertEqual(value, 500)
