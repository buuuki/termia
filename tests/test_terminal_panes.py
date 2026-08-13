import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.models import Server
from termia.terminal_processes import TerminalProcess
from termia.terminal_sessions import MAX_TERMINAL_PANES, TerminalSessionsMixin
from termia.ui_state import TerminalPane, TerminalSession


class FakeTerminal:
    def __init__(self) -> None:
        self.output = b""
        self.focused = False

    def feed(self, payload: bytes) -> None:
        self.output += payload

    def feed_child(self, payload: bytes) -> None:
        self.output += payload

    def grab_focus(self) -> None:
        self.focused = True


class FakeControl:
    def __init__(self) -> None:
        self.label = ""
        self.sensitive = False
        self.visible = False

    def set_label(self, label: str) -> None:
        self.label = label

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def get_visible(self) -> bool:
        return self.visible


def make_pane(
    terminal,
    pane_id: str,
    *,
    server_id: str | None = None,
    process: TerminalProcess | None = None,
) -> TerminalPane:
    label = FakeControl()
    button = FakeControl()
    return TerminalPane(
        id=pane_id,
        terminal=terminal,
        container=object(),
        status_label=label,
        timer_label=label,
        disconnect_button=button,
        status_bar=FakeControl(),
        title=pane_id,
        started_at=1.0,
        server_id=server_id,
        child_pid=process.pid if process is not None else None,
        child_process=process,
    )


def make_session(root_terminal, root_pane: TerminalPane) -> TerminalSession:
    session = TerminalSession(
        id="tab",
        server_id=root_pane.server_id,
        title="Tab",
        terminal=root_terminal,
        page=object(),
        tab_label=object(),
        status_label=root_pane.status_label,
        timer_label=root_pane.timer_label,
        disconnect_button=root_pane.disconnect_button,
        status_bar=root_pane.status_bar,
        started_at=1.0,
    )
    session.panes[id(root_terminal)] = root_pane
    session.active_terminal_ids.add(id(root_terminal))
    return session


class TerminalPaneStateTests(unittest.TestCase):
    def test_split_focus_grabs_selected_neighbor(self) -> None:
        root_terminal = FakeTerminal()
        split_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root")
        split = make_pane(split_terminal, "split")
        root.container = SimpleNamespace(
            compute_bounds=lambda _page: (
                True,
                SimpleNamespace(
                    get_x=lambda: 0,
                    get_y=lambda: 0,
                    get_width=lambda: 100,
                    get_height=lambda: 100,
                ),
            )
        )
        split.container = SimpleNamespace(
            compute_bounds=lambda _page: (
                True,
                SimpleNamespace(
                    get_x=lambda: 100,
                    get_y=lambda: 0,
                    get_width=lambda: 100,
                    get_height=lambda: 100,
                ),
            )
        )
        session = make_session(root_terminal, root)
        session.page = object()
        session.panes[id(split_terminal)] = split
        session.active_terminal_ids.add(id(split_terminal))

        moved = TerminalSessionsMixin.move_split_pane_focus(
            TerminalSessionsMixin(), session, root_terminal, "right"
        )

        self.assertTrue(moved)
        self.assertTrue(split_terminal.focused)

    def test_split_search_enter_without_a_match_keeps_dialog_open(self) -> None:
        host = TerminalSessionsMixin()
        dialog = Mock()
        connection_list = Mock()
        connection_list.get_selected_row.return_value = None

        host.on_split_connection_search_activated(
            Mock(),
            dialog,
            connection_list,
            {"visible_choices": []},
        )

        dialog.response.assert_not_called()

    def test_split_search_enter_with_a_selection_opens_connection(self) -> None:
        from gi.repository import Gtk

        host = TerminalSessionsMixin()
        dialog = Mock()
        connection_list = Mock()
        connection_list.get_selected_row.return_value = SimpleNamespace(get_index=lambda: 0)

        host.on_split_connection_search_activated(
            Mock(),
            dialog,
            connection_list,
            {"visible_choices": [SimpleNamespace(connection_id="server:example")]},
        )

        dialog.response.assert_called_once_with(Gtk.ResponseType.OK)

    def test_context_menu_toggles_only_the_selected_pane_status_bar(self) -> None:
        root_terminal = FakeTerminal()
        split_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root")
        split = make_pane(split_terminal, "split")
        session = make_session(root_terminal, root)
        session.panes[id(split_terminal)] = split
        session.active_terminal_ids.add(id(split_terminal))
        root.status_bar.set_visible(True)
        split.status_bar.set_visible(False)

        class Popover:
            def __init__(self) -> None:
                self.closed = False

            def popdown(self) -> None:
                self.closed = True

        popover = Popover()
        TerminalSessionsMixin().toggle_session_status_bar_from_menu(
            popover,
            session,
            split_terminal,
        )

        self.assertTrue(popover.closed)
        self.assertTrue(split.status_bar.visible)
        self.assertTrue(root.status_bar.visible)
        self.assertTrue(split_terminal.focused)

        TerminalSessionsMixin().toggle_session_status_bar_from_menu(
            Popover(),
            session,
            split_terminal,
        )

        self.assertFalse(split.status_bar.visible)
        self.assertTrue(root.status_bar.visible)

    def test_hiding_status_bar_uses_the_same_selected_pane_path(self) -> None:
        root_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root")
        session = make_session(root_terminal, root)
        root.status_bar.set_visible(True)

        TerminalSessionsMixin().on_hide_pane_status_bar(None, session, root_terminal)

        self.assertFalse(root.status_bar.visible)
        self.assertTrue(root_terminal.focused)

    def test_session_resolves_each_terminal_to_its_independent_pane(self) -> None:
        root_terminal = FakeTerminal()
        split_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root", server_id="server-a")
        split = make_pane(split_terminal, "split", server_id="server-b")
        session = make_session(root_terminal, root)
        session.panes[id(split_terminal)] = split
        session.active_terminal_ids.add(id(split_terminal))

        self.assertIs(session.pane_for_terminal(root_terminal), root)
        self.assertIs(session.pane_for_terminal(split_terminal), split)
        self.assertEqual(session.active_panes(), (root, split))

    def test_disconnecting_one_pane_signals_only_its_process(self) -> None:
        root_terminal = FakeTerminal()
        split_terminal = FakeTerminal()
        root_process = TerminalProcess(10, 100, 1000, "10")
        split_process = TerminalProcess(20, 200, 2000, "20")
        root = make_pane(root_terminal, "root", process=root_process)
        split = make_pane(split_terminal, "split", process=split_process)
        session = make_session(root_terminal, root)
        session.panes[id(split_terminal)] = split
        session.active_terminal_ids.add(id(split_terminal))

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.terminated = []
                self.toast_label = SimpleNamespace(set_label=lambda _label: None)

            def terminate_terminal_process(self, process, *, force=False):
                self.terminated.append((process, force))
                return True

            def t(self, key):
                return {
                    "session_disconnected_status": "{title} disconnected",
                    "session_disconnected_terminal": "Disconnected",
                    "session_disconnected_toast": "{title} disconnected",
                }[key]

        host = Host()
        host.disconnect_pane(session, split_terminal)

        self.assertEqual(host.terminated, [(split_process, False)])
        self.assertFalse(root.disconnect_requested)
        self.assertTrue(split.disconnect_requested)

    def test_failed_split_can_be_closed_instead_of_forcing_reconnect(self) -> None:
        root_terminal = FakeTerminal()
        split_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root")
        split = make_pane(split_terminal, "split", server_id="server-b")
        split.connected = False
        split.pending_reconnect = True
        session = make_session(root_terminal, root)
        session.panes[id(split_terminal)] = split
        session.active_terminal_ids.add(id(split_terminal))

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.discarded = None

            def discard_unstarted_split_pane(self, current_session, terminal):
                self.discarded = (current_session, terminal)

        host = Host()
        host.on_request_disconnect_pane(None, session, split_terminal)

        self.assertEqual(host.discarded, (session, split_terminal))

    def test_failed_pane_shows_close_action_while_waiting_for_reconnect(self) -> None:
        root_terminal = FakeTerminal()
        split_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root")
        split = make_pane(split_terminal, "split", server_id="server-b")
        session = make_session(root_terminal, root)
        session.panes[id(split_terminal)] = split
        session.active_terminal_ids.add(id(split_terminal))

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.toast_label = FakeControl()

            def t(self, key):
                return {
                    "close": "Close",
                    "reconnect_prompt": "Press Enter to reconnect",
                }[key]

        Host().mark_pane_for_reconnect(session, split, "Connection failed")

        self.assertTrue(split.pending_reconnect)
        self.assertTrue(split.status_bar.visible)
        self.assertEqual(split.disconnect_button.label, "Close")
        self.assertTrue(split.disconnect_button.sensitive)

    def test_close_action_closes_tab_when_failed_pane_is_the_only_pane(self) -> None:
        root_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root", server_id="server-a")
        root.connected = False
        root.pending_reconnect = True
        session = make_session(root_terminal, root)

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.closed = None

            def close_tab(self, session_id, page, *, disconnect):
                self.closed = (session_id, page, disconnect)

        host = Host()
        host.on_request_disconnect_pane(None, session, root_terminal)

        self.assertEqual(host.closed, (session.id, session.page, False))

    def test_same_connection_split_uses_the_selected_pane_identity(self) -> None:
        root_terminal = FakeTerminal()
        source_terminal = FakeTerminal()
        target_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root", server_id="server-a")
        source = make_pane(source_terminal, "source", server_id="server-b")
        session = make_session(root_terminal, root)
        session.panes[id(source_terminal)] = source
        server_a = Server("server-a", "A", "a.example", "user")
        server_b = Server("server-b", "B", "b.example", "user")

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.store = SimpleNamespace(data=SimpleNamespace(servers=[server_a, server_b]))
                self.started = None

            def start_ssh_split_terminal(self, current_session, terminal, server, *, announce):
                self.started = (current_session, terminal, server, announce)

        host = Host()
        host.start_split_child_terminal(
            session,
            target_terminal,
            source_terminal,
            None,
            announce=True,
        )

        self.assertEqual(host.started, (session, target_terminal, server_b, True))

    def test_saved_password_uses_the_selected_pane_server(self) -> None:
        root_terminal = FakeTerminal()
        split_terminal = FakeTerminal()
        root = make_pane(root_terminal, "root", server_id="server-a")
        split = make_pane(split_terminal, "split", server_id="server-b")
        session = make_session(root_terminal, root)
        session.panes[id(split_terminal)] = split
        server_a = Server("server-a", "A", "a.example", "user", password="first")
        server_b = Server("server-b", "B", "b.example", "user", password="second")

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.store = SimpleNamespace(
                    data=SimpleNamespace(
                        servers=[server_a, server_b],
                        app=SimpleNamespace(send_password_enter=False),
                    )
                )
                self.toast_label = SimpleNamespace(set_label=lambda _label: None)

            def t(self, key):
                return {"send_password_unavailable": "Unavailable", "send_password_sent": "Sent"}[key]

        Host().send_saved_password(session, split_terminal)

        self.assertEqual(split_terminal.output, b"second")
        self.assertEqual(root_terminal.output, b"")

    def test_split_limit_is_enforced_before_creating_a_widget(self) -> None:
        toast = SimpleNamespace(value="", set_label=lambda value: setattr(toast, "value", value))

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.toast_label = toast

            def t(self, key):
                if key != "split_pane_limit":
                    raise AssertionError(key)
                return "Maximum {limit}"

        session = SimpleNamespace(
            active_terminal_ids=set(range(MAX_TERMINAL_PANES)),
            panes={index: object() for index in range(MAX_TERMINAL_PANES)},
        )
        result = Host().split_terminal_pane(session, object(), "right")

        self.assertIsNone(result)
        self.assertEqual(toast.value, f"Maximum {MAX_TERMINAL_PANES}")


if __name__ == "__main__":
    unittest.main()
