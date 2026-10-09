# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from termia.models import CommandSnippet, Group, Server
from termia.sidebar import SidebarMixin
from termia.snippets import available_snippets
from termia.stores import ConnectionStore, ReadOnlyStoreError


class ServerGroupMoveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.paths = (
            root / "connections.json", root / "settings.json",
            root / "statistics.json", root / "lock", root / "history",
        )
        self.store = ConnectionStore(*self.paths)
        self.first = self.store.add_group("First")
        self.child = self.store.add_group("Child", self.first.id)
        self.second = self.store.add_group("Second")
        self.server = self.store.add_server(
            "Web", "web.example.test", "admin", 2222, self.first.id,
            favorite=True, password="synthetic-password", public_key="synthetic-key",
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temporary.cleanup()

    def test_move_changes_only_group_and_persists_nested_and_ungrouped_targets(self) -> None:
        original_fields = (
            self.server.id, self.server.name, self.server.host, self.server.user,
            self.server.port, self.server.favorite, self.server.password,
            self.server.public_key, self.server.split_layout,
        )

        self.assertTrue(self.store.move_server_to_group(self.server.id, self.child.id))
        self.assertEqual(self.server.group_id, self.child.id)
        self.assertTrue(self.store.move_server_to_group(self.server.id, None))
        self.assertIsNone(self.server.group_id)
        self.assertEqual(
            (
                self.server.id, self.server.name, self.server.host, self.server.user,
                self.server.port, self.server.favorite, self.server.password,
                self.server.public_key, self.server.split_layout,
            ),
            original_fields,
        )

        self.store.close()
        restored = ConnectionStore(*self.paths)
        try:
            self.assertIsNone(restored.data.servers[0].group_id)
            self.assertEqual(restored.data.servers[0].id, self.server.id)
        finally:
            restored.close()

    def test_invalid_or_unchanged_move_never_saves(self) -> None:
        with patch.object(self.store, "save_connections") as save:
            self.assertFalse(self.store.move_server_to_group(self.server.id, self.first.id))
            self.assertFalse(self.store.move_server_to_group(self.server.id, "missing"))
            self.assertFalse(self.store.move_server_to_group("missing", self.second.id))
            save.assert_not_called()
        self.assertEqual(self.server.group_id, self.first.id)

    def test_read_only_and_locked_stores_reject_move(self) -> None:
        for state in ("read_only", "encryption_locked"):
            with self.subTest(state=state):
                setattr(self.store, state, True)
                try:
                    self.assertFalse(self.store.can_move_server_to_group(self.server.id, self.second.id))
                    with self.assertRaises(ReadOnlyStoreError):
                        self.store.move_server_to_group(self.server.id, self.second.id)
                    self.assertEqual(self.server.group_id, self.first.id)
                finally:
                    setattr(self.store, state, False)

    def test_failed_save_restores_the_original_group(self) -> None:
        with patch.object(self.store, "save_connections", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.move_server_to_group(self.server.id, self.second.id)
        self.assertEqual(self.server.group_id, self.first.id)

    def test_move_updates_group_scoped_snippet_availability(self) -> None:
        snippets = [
            CommandSnippet("first", "First group", "true", scope="group", target_id=self.first.id),
            CommandSnippet("second", "Second group", "true", scope="group", target_id=self.second.id),
        ]
        visible = lambda: [
            snippet.id for snippet in available_snippets(
                snippets, self.server, groups=self.store.data.groups,
            )
        ]

        self.assertEqual(visible(), ["first"])
        self.store.move_server_to_group(self.server.id, self.child.id)
        self.assertEqual(visible(), ["first"])
        self.store.move_server_to_group(self.server.id, self.second.id)
        self.assertEqual(visible(), ["second"])
        self.store.move_server_to_group(self.server.id, None)
        self.assertEqual(visible(), [])

    def test_drop_accepts_only_this_windows_active_server_drag(self) -> None:
        label = SimpleNamespace(classes=set())
        label.add_css_class = label.classes.add
        label.remove_css_class = label.classes.discard
        host = SimpleNamespace(
            sidebar_drag_server_id=self.server.id,
            store=self.store,
            get_sidebar_scroll_values=Mock(return_value=(12.0, 0.0)),
            refresh_list=Mock(),
            render_detail=Mock(),
            preserve_sidebar_scroll=Mock(),
        )

        self.assertEqual(
            SidebarMixin.on_server_group_drop_motion(host, None, 0, 0, self.second.id, label),
            Gdk.DragAction.MOVE,
        )
        self.assertIn("drop-target", label.classes)
        self.assertEqual(
            SidebarMixin.on_server_group_drop_motion(host, None, 0, 0, self.first.id, label),
            Gdk.DragAction(0),
        )
        self.assertNotIn("drop-target", label.classes)
        self.assertFalse(
            SidebarMixin.on_server_group_drop(host, None, "external", 0, 0, self.second.id, label),
        )
        host.refresh_list.assert_not_called()
        self.assertTrue(
            SidebarMixin.on_server_group_drop(host, None, self.server.id, 0, 0, self.second.id, label),
        )
        self.assertEqual(self.server.group_id, self.second.id)
        self.assertIsNone(host.sidebar_drag_server_id)
        self.assertNotIn("drop-target", label.classes)
        host.refresh_list.assert_called_once_with()
        host.render_detail.assert_called_once_with()
        host.preserve_sidebar_scroll.assert_called_once_with(12.0, 0.0)


@unittest.skipUnless(
    (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check(),
    "GTK display unavailable",
)
class ServerGroupWidgetTests(unittest.TestCase):
    def setUp(self) -> None:
        class Host(SidebarMixin):
            def __init__(self) -> None:
                self.group_expanders = []
                self.group_expanded_state = {}
                self.collapse_groups_on_startup = False
                self.selected = None
                self.tree_widgets = {}

            def t(self, key: str) -> str:
                return key

        self.host = Host()

    def test_empty_ungrouped_heading_has_drop_target(self) -> None:
        expander = self.host.build_ungrouped_widget([], "")
        label = expander.get_label_widget()
        controllers = label.observe_controllers()

        self.assertEqual(label.get_last_child().get_text(), "no_group (0)")
        self.assertTrue(any(
            isinstance(controllers.get_item(index), Gtk.DropTarget)
            for index in range(controllers.get_n_items())
        ))

    def test_regular_group_heading_has_drop_target(self) -> None:
        group = Group("group", "Group")
        expander = self.host.build_group_widget(group, {}, {}, "")
        label = expander.get_label_widget()
        controllers = label.observe_controllers()

        self.assertTrue(any(
            isinstance(controllers.get_item(index), Gtk.DropTarget)
            for index in range(controllers.get_n_items())
        ))

    def test_only_regular_server_rows_are_drag_sources(self) -> None:
        server = Server("server", "Web", "web.example.test", "admin")

        for kind, expected in (("server", True), ("favorite", False), ("recent", False)):
            with self.subTest(kind=kind):
                row = self.host.build_server_widget(server, row_kind=kind)
                controllers = row.observe_controllers()
                has_drag_source = any(
                    isinstance(controllers.get_item(index), Gtk.DragSource)
                    for index in range(controllers.get_n_items())
                )
                self.assertEqual(has_drag_source, expected)


if __name__ == "__main__":
    unittest.main()
