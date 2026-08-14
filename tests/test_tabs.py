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
    def __init__(self, **kwargs) -> None:
        self.properties = kwargs
        self.child = None
        self.presented = False
        self.titlebar = None
        self.title = kwargs.get("title", "")
        self.destroyed = False

    def set_handle_menubar_accel(self, _enabled: bool) -> None:
        pass

    def set_default_size(self, _width: int, _height: int) -> None:
        pass

    def set_titlebar(self, titlebar) -> None:
        self.titlebar = titlebar

    def get_titlebar(self):
        return self.titlebar

    def set_title(self, title: str) -> None:
        self.title = title

    def set_child(self, child) -> None:
        self.child = child

    def connect(self, *_args) -> None:
        pass

    def present(self) -> None:
        self.presented = True

    def destroy(self) -> None:
        self.destroyed = True


class FakeHeaderBar:
    def __init__(self) -> None:
        self.title_widget = None

    def set_title_widget(self, widget) -> None:
        self.title_widget = widget

    def get_title_widget(self):
        return self.title_widget


class FakeLabel:
    def __init__(self, *, label: str) -> None:
        self.label = label

    def set_label(self, label: str) -> None:
        self.label = label


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
    def test_closing_detached_window_defers_session_close_until_after_signal(self) -> None:
        window = FakeWindow()
        session = SimpleNamespace(id="detached", page=object(), detached_window=window)

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session])
                self.requested = None

            def request_close_tab(self, session_id, page) -> None:
                self.requested = (session_id, page)

        host = Host()
        with patch("termia.tabs.GLib.idle_add") as idle_add:
            handled = host.on_detached_window_close(window, session)

        self.assertTrue(handled)
        self.assertIsNone(host.requested)
        idle_add.assert_called_once_with(host.finish_detached_window_close, window, session)
        self.assertIs(session.detached_window, window)
        self.assertIs(window.child, None)

        result = host.finish_detached_window_close(window, session)

        self.assertEqual(host.requested, (session.id, session.page))
        from gi.repository import GLib

        self.assertEqual(result, GLib.SOURCE_REMOVE)

    def test_deferred_close_ignores_session_reattached_before_callback(self) -> None:
        window = FakeWindow()
        session = SimpleNamespace(id="detached", page=object(), detached_window=window)

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session])
                self.requested = False

            def request_close_tab(self, _session_id, _page) -> None:
                self.requested = True

        host = Host()
        session.detached_window = None

        host.finish_detached_window_close(window, session)

        self.assertFalse(host.requested)

    def test_explicit_reattach_preserves_session_and_destroys_only_window(self) -> None:
        page = object()
        window = FakeWindow()
        window.set_child(page)
        session = SimpleNamespace(id="detached", page=page, detached_window=window)

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session])
                self.attached = None

            def add_session_to_main_view(self, current_session) -> None:
                self.attached = current_session

        host = Host()
        popover = FakePopover()

        host.reattach_tab(popover, session)

        self.assertTrue(popover.closed)
        self.assertIsNone(session.detached_window)
        self.assertIsNone(window.child)
        self.assertTrue(window.destroyed)
        self.assertIs(host.attached, session)
        self.assertTrue(host.session_registry.contains(session.id))

    def test_dialog_owner_uses_detached_window_when_available(self) -> None:
        detached_window = object()
        session = SimpleNamespace(detached_window=detached_window)
        host = TabsMixin()

        self.assertIs(host.window_for_session(session), detached_window)

    def test_dialog_owner_uses_main_window_for_attached_session(self) -> None:
        session = SimpleNamespace(detached_window=None)
        host = TabsMixin()

        self.assertIs(host.window_for_session(session), host)

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
                self.application = object()
                self.session_registry = SessionRegistry([session, previous_session])
                self.focused = None
                self.removed = None
                self.visible_sessions = [previous_session, session]

            def visible_sessions_in_tab_order(self):
                return self.visible_sessions

            def get_application(self):
                return self.application

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
        with (
            patch("termia.tabs.Gtk.Window", FakeWindow),
            patch("termia.tabs.Gtk.HeaderBar", FakeHeaderBar),
            patch("termia.tabs.Gtk.Label", FakeLabel),
        ):
            host.detach_tab(popover, session)

        self.assertTrue(popover.closed)
        self.assertIs(host.removed, session)
        self.assertEqual(host.focused, (session.id, [previous_session, session]))
        self.assertIsInstance(session.detached_window, FakeWindow)
        self.assertIs(session.detached_window.properties["application"], host.application)
        self.assertNotIn("transient_for", session.detached_window.properties)
        self.assertIsInstance(session.detached_window.titlebar, FakeHeaderBar)
        self.assertEqual(session.detached_window.titlebar.title_widget.label, session.title)
        self.assertTrue(session.detached_window.presented)

    def test_renaming_detached_tab_updates_window_and_header_titles(self) -> None:
        window = FakeWindow(title="Old title")
        header = FakeHeaderBar()
        header.set_title_widget(FakeLabel(label="Old title"))
        window.set_titlebar(header)
        session = SimpleNamespace(
            title="Old title",
            title_locked=False,
            detached_window=window,
        )
        dialog = SimpleNamespace(destroy=lambda: setattr(dialog, "destroyed", True))
        entry = SimpleNamespace(get_text=lambda: "New title")

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.updated = None
                self.synced = False

            def update_session_tab_title(self, current_session, title) -> None:
                self.updated = (current_session, title)

            def sync_window_title_with_visible_session(self) -> None:
                self.synced = True

        from gi.repository import Gtk

        host = Host()
        with (
            patch("termia.tabs.Gtk.HeaderBar", FakeHeaderBar),
            patch("termia.tabs.Gtk.Label", FakeLabel),
        ):
            host.on_rename_tab_response(dialog, Gtk.ResponseType.OK, entry, session)

        self.assertEqual(session.title, "New title")
        self.assertTrue(session.title_locked)
        self.assertEqual(host.updated, (session, "New title"))
        self.assertEqual(window.title, "New title")
        self.assertEqual(header.title_widget.label, "New title")
        self.assertTrue(host.synced)
        self.assertTrue(dialog.destroyed)


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
    def test_tab_strip_overflow_requires_content_wider_than_viewport(self) -> None:
        self.assertFalse(
            TabsMixin.tab_strip_has_overflow(page_size=300, lower=0, upper=300)
        )
        self.assertTrue(
            TabsMixin.tab_strip_has_overflow(page_size=300, lower=0, upper=301.1)
        )

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
