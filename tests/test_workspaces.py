import unittest
from types import SimpleNamespace

from termia.models import LocalTerminalProfile, Server, Workspace
from termia.terminal_sessions import TerminalSessionsMixin


def pane(connection_type: str, connection_id: str) -> dict[str, str]:
    return {"type": "pane", "connection_type": connection_type, "connection_id": connection_id}


class WorkspaceOpeningTests(unittest.TestCase):
    def test_opens_valid_tabs_and_skips_missing_connections(self) -> None:
        workspace = Workspace(
            id="production",
            name="Production",
            tabs=[
                {"layout": pane("server", "web")},
                {"layout": pane("local", "shell")},
                {"layout": pane("server", "missing")},
            ],
        )

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.store = SimpleNamespace(
                    data=SimpleNamespace(
                        servers=[Server(id="web", name="Web", host="web.test", user="admin")],
                        local_terminals=[LocalTerminalProfile(id="shell", name="Shell")],
                    )
                )
                self.toast_label = SimpleNamespace(set_label=lambda message: setattr(self, "toast", message))
                self.opened: list[tuple[str, str]] = []

            def open_terminal_tab(self, server, *, split_layout):
                self.opened.append(("server", server.id))
                return SimpleNamespace(terminal=object())

            def open_local_terminal_profile(self, profile, *, split_layout):
                self.opened.append(("local", profile.id if profile else ""))
                return SimpleNamespace(terminal=object())

            def restore_workspace_node(self, session, terminal, layout):
                self.opened.append(("layout", layout["connection_id"]))

            def t(self, key):
                return {
                    "workspace_opened": "Workspace opened: {name} ({count} tabs)",
                    "workspace_no_available_tabs": "No available tabs to open in workspace: {name}",
                    "workspace_opened_with_skipped_tabs": "Workspace opened: {name} ({count} tabs; {skipped} skipped)",
                }[key]

        host = Host()
        host.open_workspace(workspace)

        self.assertEqual(
            host.opened,
            [("server", "web"), ("layout", "web"), ("local", "shell"), ("layout", "shell")],
        )
        self.assertEqual(host.toast, "Workspace opened: Production (2 tabs; 1 skipped)")
