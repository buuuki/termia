import unittest

from termia.workspace_layout import (
    MAX_WORKSPACE_PANES,
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
