import unittest
from types import SimpleNamespace
from unittest.mock import patch

from termia.workspace_layout import (
    MAX_WORKSPACE_PANES,
    capture_workspace_tab,
    normalized_workspace_tabs,
    workspace_layout_is_valid,
    workspace_pane_count,
    workspace_root_pane,
    workspace_tab_layouts,
    workspace_total_pane_count,
)


class WorkspaceLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.layout = {
            "type": "split",
            "orientation": "horizontal",
            "position": 0.4,
            "start": {
                "type": "pane",
                "connection_type": "server",
                "connection_id": "web",
            },
            "end": {
                "type": "pane",
                "connection_type": "local",
                "connection_id": "shell",
            },
        }

    def test_layout_validation_keeps_only_connection_references(self) -> None:
        self.assertTrue(workspace_layout_is_valid(self.layout))
        self.assertFalse(
            workspace_layout_is_valid(
                {"type": "pane", "connection_type": "server", "connection_id": ""}
            )
        )

    def test_layout_helpers_find_root_and_pane_count(self) -> None:
        root = workspace_root_pane(self.layout)

        self.assertEqual(root["connection_id"], "web")
        self.assertEqual(workspace_pane_count(self.layout), 2)
        self.assertEqual(workspace_tab_layouts([{"layout": self.layout}, {"layout": {}}]), [self.layout])

    def test_total_pane_count_spans_all_workspace_tabs(self) -> None:
        tabs = [{"layout": self.layout} for _index in range(MAX_WORKSPACE_PANES // 2)]

        self.assertEqual(workspace_total_pane_count(tabs), MAX_WORKSPACE_PANES)

    def test_normalization_keeps_titles_and_only_local_absolute_directories(self) -> None:
        tabs = [
            {
                "title": "  Project shell  ",
                "layout": {
                    "type": "pane",
                    "connection_type": "local",
                    "connection_id": "shell",
                    "working_directory": "/srv/project",
                    "terminal_output": "private",
                },
            },
            {
                "layout": {
                    "type": "pane",
                    "connection_type": "server",
                    "connection_id": "web",
                    "working_directory": "/remote/private",
                }
            },
            {
                "layout": {
                    "type": "pane",
                    "connection_type": "local",
                    "connection_id": "",
                    "working_directory": "relative/path",
                }
            },
        ]

        normalized = normalized_workspace_tabs(tabs)

        self.assertEqual(normalized[0]["title"], "Project shell")
        self.assertEqual(normalized[0]["layout"]["working_directory"], "/srv/project")
        self.assertNotIn("terminal_output", normalized[0]["layout"])
        self.assertNotIn("working_directory", normalized[1]["layout"])
        self.assertNotIn("working_directory", normalized[2]["layout"])

    def test_capture_saves_locked_title_and_local_pane_cwd(self) -> None:
        container = object()
        pane = SimpleNamespace(
            container=container,
            server_id=None,
            local_profile_id="shell",
            child_pid=42,
        )
        session = SimpleNamespace(
            page=SimpleNamespace(get_first_child=lambda: container),
            panes={1: pane},
            title="Project shell",
            title_locked=True,
        )

        with patch("termia.workspace_layout.os.readlink", return_value="/srv/project"):
            tab = capture_workspace_tab(session)

        self.assertEqual(tab["title"], "Project shell")
        self.assertEqual(tab["layout"]["working_directory"], "/srv/project")

    def test_capture_does_not_save_remote_cwd_or_unlocked_title(self) -> None:
        container = object()
        pane = SimpleNamespace(
            container=container,
            server_id="web",
            local_profile_id=None,
            child_pid=42,
        )
        session = SimpleNamespace(
            page=SimpleNamespace(get_first_child=lambda: container),
            panes={1: pane},
            title="Web",
            title_locked=False,
        )

        tab = capture_workspace_tab(session)

        self.assertNotIn("title", tab)
        self.assertNotIn("working_directory", tab["layout"])

    def test_minimal_snapshot_capture_omits_local_context(self) -> None:
        container = object()
        pane = SimpleNamespace(
            container=container,
            server_id=None,
            local_profile_id="shell",
            child_pid=42,
        )
        session = SimpleNamespace(
            page=SimpleNamespace(get_first_child=lambda: container),
            panes={1: pane},
            title="Project shell",
            title_locked=True,
        )

        with patch("termia.workspace_layout.os.readlink", return_value="/srv/project"):
            tab = capture_workspace_tab(session, include_local_context=False)

        self.assertNotIn("title", tab)
        self.assertNotIn("working_directory", tab["layout"])
