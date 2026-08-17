import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from termia.models import LocalTerminalProfile, Server, Workspace
from termia.sidebar import SidebarMixin
from termia.session_registry import SessionRegistry
from termia.terminal_sessions import TerminalSessionsMixin
from termia.workspace_layout import MAX_WORKSPACE_PANES


def pane(connection_type: str, connection_id: str) -> dict[str, str]:
    return {"type": "pane", "connection_type": connection_type, "connection_id": connection_id}


def workspace_tabs(count: int) -> list[dict[str, dict[str, str]]]:
    return [{"layout": pane("server", "web")} for _index in range(count)]


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
                self.session_registry = SessionRegistry()
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

    def test_opening_thirty_two_panes_does_not_require_confirmation(self) -> None:
        workspace = Workspace(
            id="regular",
            name="Regular",
            tabs=workspace_tabs(MAX_WORKSPACE_PANES),
        )
        host = SimpleNamespace(
            opened_workspace=None,
            can_open_terminal_tabs=lambda _count: True,
        )
        host.open_workspace_tabs = lambda selected: setattr(
            host,
            "opened_workspace",
            selected.id,
        )

        TerminalSessionsMixin.open_workspace(host, workspace)

        self.assertEqual(host.opened_workspace, "regular")

    def test_opening_more_than_thirty_two_panes_is_rejected(self) -> None:
        workspace = Workspace(
            id="oversized",
            name="Oversized",
            tabs=workspace_tabs(MAX_WORKSPACE_PANES + 1),
        )
        host = SimpleNamespace(
            toast=None,
            toast_label=SimpleNamespace(set_warning=lambda message: setattr(host, "toast", message)),
            t=lambda key: {
                "workspace_pane_limit_exceeded": "Limit {limit}; found {count}",
            }[key],
            open_workspace_tabs=lambda *_args: self.fail(
                "oversized workspace must not start processes"
            ),
        )

        TerminalSessionsMixin.open_workspace(host, workspace)

        self.assertEqual(host.toast, "Limit 32; found 33")

    def test_saving_more_than_thirty_two_panes_is_rejected(self) -> None:
        host = SimpleNamespace(
            toast=None,
            toast_label=SimpleNamespace(set_label=lambda message: setattr(host, "toast", message)),
            t=lambda key: {
                "workspace_pane_limit_exceeded": "Limit {limit}; found {count}",
            }[key],
        )

        accepted = SidebarMixin.workspace_tabs_within_pane_limit(
            host,
            workspace_tabs(MAX_WORKSPACE_PANES + 1),
        )

        self.assertFalse(accepted)
        self.assertEqual(host.toast, "Limit 32; found 33")

    def test_local_workspace_root_uses_saved_available_directory(self) -> None:
        profile = LocalTerminalProfile(id="shell", name="Shell")
        host = SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(local_terminals=[profile])),
            opened=None,
            available_workspace_working_directory=(
                TerminalSessionsMixin.available_workspace_working_directory
            ),
        )

        def open_local(selected, **kwargs):
            host.opened = (selected, kwargs)
            return "session"

        host.open_local_terminal_profile = open_local
        with tempfile.TemporaryDirectory() as directory:
            session = TerminalSessionsMixin.open_workspace_root(
                host,
                {
                    "type": "pane",
                    "connection_type": "local",
                    "connection_id": "shell",
                    "working_directory": directory,
                },
            )

        self.assertEqual(session, "session")
        self.assertIs(host.opened[0], profile)
        self.assertEqual(host.opened[1]["working_directory_override"], directory)

    def test_missing_workspace_directory_falls_back_to_profile_default(self) -> None:
        profile = LocalTerminalProfile(id="shell", name="Shell")
        host = SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(local_terminals=[profile])),
            opened=None,
            available_workspace_working_directory=(
                TerminalSessionsMixin.available_workspace_working_directory
            ),
        )

        def open_local(selected, **kwargs):
            host.opened = (selected, kwargs)
            return "session"

        host.open_local_terminal_profile = open_local
        missing = str(Path(tempfile.gettempdir()) / "termia-missing-workspace-directory")
        TerminalSessionsMixin.open_workspace_root(
            host,
            {
                "type": "pane",
                "connection_type": "local",
                "connection_id": "shell",
                "working_directory": missing,
            },
        )

        self.assertEqual(host.opened[1], {"split_layout": "none"})

    def test_local_split_uses_its_own_saved_directory(self) -> None:
        profile = LocalTerminalProfile(id="shell", name="Shell")
        host = SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(local_terminals=[profile])),
            started=None,
            available_workspace_working_directory=(
                TerminalSessionsMixin.available_workspace_working_directory
            ),
        )

        def start_local(session, terminal, source_terminal, **kwargs):
            host.started = (session, terminal, source_terminal, kwargs)

        host.start_local_split_terminal = start_local
        with tempfile.TemporaryDirectory() as directory:
            started = TerminalSessionsMixin.start_workspace_pane(
                host,
                "session",
                "terminal",
                "source",
                {
                    "type": "pane",
                    "connection_type": "local",
                    "connection_id": "shell",
                    "working_directory": directory,
                },
            )

        self.assertTrue(started)
        self.assertEqual(host.started[3]["working_directory_override"], directory)

    def test_restores_saved_custom_tab_title(self) -> None:
        pane_state = SimpleNamespace(title="Shell")
        session = SimpleNamespace(
            title="Shell",
            title_locked=False,
            terminal=object(),
            pane_for_terminal=lambda _terminal: pane_state,
        )
        host = SimpleNamespace(
            updated=None,
            synced=False,
            update_session_tab_title=lambda current, title: setattr(
                host, "updated", (current, title)
            ),
            sync_window_title_with_visible_session=lambda: setattr(host, "synced", True),
        )

        TerminalSessionsMixin.restore_workspace_tab_title(host, session, " Project shell ")

        self.assertEqual(session.title, "Project shell")
        self.assertTrue(session.title_locked)
        self.assertEqual(pane_state.title, "Project shell")
        self.assertEqual(host.updated, (session, "Project shell"))
        self.assertTrue(host.synced)
