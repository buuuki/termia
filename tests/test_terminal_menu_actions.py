import unittest

from termia.terminal_menu_actions import TerminalMenuActions


class TerminalMenuActionsTests(unittest.TestCase):
    def test_each_explicit_action_dispatches_to_its_callback(self) -> None:
        calls = []

        def action(name):
            return lambda *args: calls.append((name, args))

        actions = TerminalMenuActions(
            disconnect=action("disconnect"),
            show_status_bar=action("show_status_bar"),
            copy=action("copy"),
            paste=action("paste"),
            send_files=action("send_files"),
            configure=action("configure"),
            session_statistics=action("session_statistics"),
            split=action("split"),
            split_connection=action("split_connection"),
            rename_tab=action("rename_tab"),
            duplicate_tab=action("duplicate_tab"),
            new_tab=action("new_tab"),
            close_tab=action("close_tab"),
        )
        popover = object()
        session = object()
        terminal = object()
        server = object()

        actions.disconnect(popover, session, terminal)
        actions.show_status_bar(popover, session, terminal)
        actions.copy(popover, terminal)
        actions.paste(popover, terminal)
        actions.send_files(popover, server)
        actions.configure(popover)
        actions.session_statistics(popover, session, terminal)
        actions.split(popover, session, terminal, "left")
        actions.split_connection(popover, session, terminal)
        actions.rename_tab(popover, session)
        actions.duplicate_tab(popover, session)
        actions.new_tab(popover)
        actions.close_tab(popover, session)

        self.assertEqual(
            [name for name, _args in calls],
            [
                "disconnect",
                "show_status_bar",
                "copy",
                "paste",
                "send_files",
                "configure",
                "session_statistics",
                "split",
                "split_connection",
                "rename_tab",
                "duplicate_tab",
                "new_tab",
                "close_tab",
            ],
        )
