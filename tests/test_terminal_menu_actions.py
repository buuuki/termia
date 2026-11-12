import unittest
from types import SimpleNamespace

from termia.terminal_menu_actions import (
    TerminalMenuActions,
    can_reopen_terminal,
    status_bar_action_label_key,
)


class TerminalMenuActionsTests(unittest.TestCase):
    def test_reopen_requires_finished_manual_disconnect_in_only_live_pane(self):
        pane = SimpleNamespace(retired=False, connected=False,
                               disconnect_requested=True, child_process=None)
        session = SimpleNamespace(panes={1: pane})
        self.assertTrue(can_reopen_terminal(session, pane))
        for attribute, value in (("retired", True), ("connected", True),
                                 ("disconnect_requested", False), ("child_process", object())):
            previous = getattr(pane, attribute)
            setattr(pane, attribute, value)
            self.assertFalse(can_reopen_terminal(session, pane), attribute)
            setattr(pane, attribute, previous)
        session.panes[2] = object()
        self.assertFalse(can_reopen_terminal(session, pane))

    def test_status_bar_action_label_matches_selected_pane_visibility(self) -> None:
        self.assertEqual(
            status_bar_action_label_key(False),
            "show_session_status_bar",
        )
        self.assertEqual(
            status_bar_action_label_key(True),
            "hide_session_status_bar",
        )

    def test_each_explicit_action_dispatches_to_its_callback(self) -> None:
        calls = []

        def action(name):
            return lambda *args: calls.append((name, args))

        actions = TerminalMenuActions(
            disconnect=action("disconnect"),
            toggle_status_bar=action("toggle_status_bar"),
            copy=action("copy"),
            paste=action("paste"),
            send_files=action("send_files"),
            configure=action("configure"),
            session_statistics=action("session_statistics"),
            split=action("split"),
            split_connection=action("split_connection"),
            rename_tab=action("rename_tab"),
            reattach_tab=action("reattach_tab"),
            duplicate_tab=action("duplicate_tab"),
            new_tab=action("new_tab"),
            close_tab=action("close_tab"),
            run_snippet=action("run_snippet"),
        )
        popover = object()
        session = object()
        terminal = object()
        server = object()

        actions.disconnect(popover, session, terminal)
        actions.toggle_status_bar(popover, session, terminal)
        actions.copy(popover, terminal)
        actions.paste(popover, terminal)
        actions.send_files(popover, session, server)
        actions.configure(popover, session)
        actions.session_statistics(popover, session, terminal)
        actions.split(popover, session, terminal, "left")
        actions.split_connection(popover, session, terminal)
        actions.rename_tab(popover, session)
        actions.reattach_tab(popover, session)
        actions.duplicate_tab(popover, session)
        actions.new_tab(popover)
        actions.close_tab(popover, session)
        actions.run_snippet(popover, session, terminal)

        self.assertEqual(
            [name for name, _args in calls],
            [
                "disconnect",
                "toggle_status_bar",
                "copy",
                "paste",
                "send_files",
                "configure",
                "session_statistics",
                "split",
                "split_connection",
                "rename_tab",
                "reattach_tab",
                "duplicate_tab",
                "new_tab",
                "close_tab",
                "run_snippet",
            ],
        )
        self.assertEqual(calls[4], ("send_files", (popover, session, server)))
        self.assertEqual(calls[5], ("configure", (popover, session)))
