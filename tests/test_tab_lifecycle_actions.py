import unittest
from types import SimpleNamespace

from termia.tab_lifecycle_actions import TabLifecycleActions
from termia.terminal_sessions import TerminalSessionsMixin


class TabLifecycleActionsTests(unittest.TestCase):
    def test_each_explicit_action_dispatches_to_its_callback(self) -> None:
        calls = []

        def action(name):
            return lambda *args: calls.append((name, args))

        actions = TabLifecycleActions(
            duplicate_session=action("duplicate_session"),
            disconnect_session=action("disconnect_session"),
            terminate_split_processes=action("terminate_split_processes"),
            confirm_session_action=action("confirm_session_action"),
        )
        session = object()
        confirmed_action = lambda: None

        actions.duplicate_session(session)
        actions.disconnect_session(session)
        actions.terminate_split_processes(session)
        actions.confirm_session_action(session, "title", "detail", "confirm", confirmed_action)

        self.assertEqual(
            calls,
            [
                ("duplicate_session", (session,)),
                ("disconnect_session", (session,)),
                ("terminate_split_processes", (session,)),
                (
                    "confirm_session_action",
                    (session, "title", "detail", "confirm", confirmed_action),
                ),
            ],
        )


class DuplicateSessionTests(unittest.TestCase):
    def test_duplicate_session_preserves_ssh_and_local_startup_paths(self) -> None:
        server = SimpleNamespace(id="server")

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.store = SimpleNamespace(data=SimpleNamespace(servers=[server]))
                self.opened_server = None
                self.opened_local = False

            def open_terminal_tab(self, selected_server) -> None:
                self.opened_server = selected_server

            def on_open_local_terminal(self, _button) -> None:
                self.opened_local = True

        host = Host()

        host.duplicate_session(SimpleNamespace(server_id=server.id))
        self.assertIs(host.opened_server, server)

        host.duplicate_session(SimpleNamespace(server_id=None))
        self.assertTrue(host.opened_local)

        host.opened_server = None
        host.opened_local = False
        host.duplicate_session(SimpleNamespace(server_id="missing"))
        self.assertIsNone(host.opened_server)
        self.assertFalse(host.opened_local)
