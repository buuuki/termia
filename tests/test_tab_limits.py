import unittest
from types import SimpleNamespace

from termia.models import Server, Workspace
from termia.session_registry import SessionRegistry
from termia.sidebar import SidebarMixin
from termia.terminal_sessions import MAX_OPEN_TABS, TerminalSessionsMixin


def sessions(count: int, *, detached: bool = False) -> SessionRegistry:
    return SessionRegistry(
        SimpleNamespace(id=str(index), detached_window=object() if detached else None)
        for index in range(count)
    )


def pane(connection_id: str) -> dict[str, str]:
    return {"type": "pane", "connection_type": "server", "connection_id": connection_id}


class LimitHost(TerminalSessionsMixin):
    def __init__(self, open_tabs: int, *, detached: bool = False) -> None:
        self.session_registry = sessions(open_tabs, detached=detached)
        self.toast = None
        self.toast_label = SimpleNamespace(set_label=lambda message: setattr(self, "toast", message))

    def t(self, key: str) -> str:
        return {
            "global_tab_limit_exceeded": "Open {open}; requested {requested}; limit {limit}",
        }[key]


class GlobalTabLimitTests(unittest.TestCase):
    def test_capacity_counts_detached_tabs_and_closing_restores_a_slot(self) -> None:
        host = LimitHost(MAX_OPEN_TABS, detached=True)

        self.assertFalse(host.can_open_terminal_tabs())
        self.assertEqual(host.toast, "Open 40; requested 1; limit 40")

        host.session_registry.remove("0")

        self.assertTrue(host.can_open_terminal_tabs())

    def test_individual_local_and_ssh_tabs_are_rejected_before_session_creation(self) -> None:
        host = LimitHost(MAX_OPEN_TABS)
        host.create_terminal_session = lambda *_args, **_kwargs: self.fail(
            "the tab limit must be checked before creating a terminal session"
        )

        local = host.open_process_terminal_tab("Local", ["/bin/sh"], None)
        ssh = host.open_terminal_tab(Server(id="web", name="Web", host="web.test", user="admin"))

        self.assertIsNone(local)
        self.assertIsNone(ssh)

    def test_workspace_is_rejected_atomically_when_its_tabs_do_not_fit(self) -> None:
        host = LimitHost(MAX_OPEN_TABS - 1)
        host.open_workspace_root = lambda *_args: self.fail(
            "an oversized workspace must not start a terminal"
        )
        workspace = Workspace(
            id="production",
            name="Production",
            tabs=[{"layout": pane("web")}, {"layout": pane("database")}],
        )

        host.open_workspace(workspace)

        self.assertEqual(host.toast, "Open 39; requested 2; limit 40")

    def test_server_group_is_rejected_atomically_when_its_tabs_do_not_fit(self) -> None:
        class GroupHost(SidebarMixin, LimitHost):
            pass

        host = GroupHost(MAX_OPEN_TABS - 1)
        host.open_terminal_tab = lambda *_args: self.fail(
            "an oversized group must not start a terminal"
        )

        host.start_group_servers(
            [
                Server(id="web", name="Web", host="web.test", user="admin"),
                Server(id="database", name="Database", host="database.test", user="admin"),
            ]
        )

        self.assertEqual(host.toast, "Open 39; requested 2; limit 40")


if __name__ == "__main__":
    unittest.main()
