# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import tempfile
import unittest
from pathlib import Path

from termia.models import CommandSnippet, Group, Server
from termia.snippet_presenter import SnippetPresenter
from termia.snippets import (
    SnippetError,
    available_snippets,
    normalize_snippet,
    normalized_categories,
    render_snippet,
    snippet_variables,
)
from termia.stores import ConnectionStore, ReadOnlyStoreError


class SnippetDomainTests(unittest.TestCase):
    def test_variables_are_unique_and_rendered_without_shell_interpretation(self):
        content = "systemctl restart {{service}} --path {{path}} {{service}}"
        self.assertEqual(snippet_variables(content), ["service", "path"])
        self.assertEqual(
            render_snippet(content, {"service": "nginx", "path": "/srv/a b"}),
            "systemctl restart nginx --path '/srv/a b' nginx",
        )
        with self.assertRaises(SnippetError):
            render_snippet(content, {"service": "nginx", "path": ""})

    def test_variable_values_are_shell_quoted(self):
        self.assertEqual(
            render_snippet("printf '%s\\n' {{value}}", {"value": "$(touch /tmp/no); value"}),
            "printf '%s\\n' '$(touch /tmp/no); value'",
        )

    def test_invalid_scope_is_rejected_instead_of_becoming_global(self):
        with self.assertRaises(SnippetError):
            normalize_snippet("id", "Unsafe", "true", scope="unexpected")

    def test_scope_and_search_select_only_the_active_server(self):
        server = Server("server", "Production", "host", "user", group_id="group")
        snippets = [
            CommandSnippet("global", "Disk usage", "df -h", "System"),
            CommandSnippet("group", "Restart", "systemctl restart {{service}}", "System", "group", "group"),
            CommandSnippet("server", "Deploy", "deploy", "Release", "server", "server"),
            CommandSnippet("other", "Hidden", "false", "System", "server", "other"),
        ]
        self.assertEqual([item.id for item in available_snippets(snippets, server)], ["server", "global", "group"])
        self.assertEqual([item.id for item in available_snippets(snippets, server, "restart")], ["group"])

    def test_parent_group_snippet_applies_to_nested_server(self):
        groups = [Group("parent", "Parent"), Group("child", "Child", "parent")]
        server = Server("server", "Nested", "host", "user", group_id="child")
        snippet = CommandSnippet("group", "Restart", "true", scope="group", target_id="parent")

        self.assertEqual(available_snippets([snippet], server, groups=groups), [snippet])

    def test_presenter_uses_group_paths_and_filters_by_server(self):
        groups = [Group("parent", "Parent"), Group("child", "Child", "parent")]
        servers = [Server("server", "Nested", "host", "user", group_id="child")]
        snippets = [CommandSnippet("group", "Restart", "true", scope="group", target_id="parent")]
        presenter = SnippetPresenter(lambda: snippets, lambda: groups, lambda: servers)

        self.assertEqual(presenter.targets("group")[1].label, "Parent / Child")
        self.assertEqual([item.id for item in presenter.run_items("server", "")], ["group"])

    def test_presenter_projects_categories_with_counts_and_uncategorized_last(self):
        snippets = [
            CommandSnippet("one", "Deploy", "deploy", "Release"),
            CommandSnippet("two", "Restart", "restart", "Operations"),
            CommandSnippet("three", "Status", "status", "Operations"),
            CommandSnippet("four", "Notes", "cat notes"),
        ]
        presenter = SnippetPresenter(lambda: snippets, lambda: [], lambda: [])

        self.assertEqual(
            [(item.key, item.count) for item in presenter.categories()],
            [("Operations", 2), ("Release", 1), ("", 1)],
        )
        self.assertEqual(presenter.categories()[-1].icon_name, "folder-open-symbolic")

    def test_empty_saved_categories_are_visible(self):
        snippets = [CommandSnippet("one", "Deploy", "deploy", "Release")]
        categories = ["Empty"]
        presenter = SnippetPresenter(
            lambda: snippets, lambda: [], lambda: [], lambda: categories,
        )

        self.assertEqual(
            [(item.key, item.count) for item in presenter.categories()],
            [("Empty", 0), ("Release", 1)],
        )
        self.assertEqual(normalized_categories([" Empty ", "Empty"], snippets), ["Empty", "Release"])

    def test_presenter_manager_search_is_global_and_category_filter_is_independent(self):
        snippets = [
            CommandSnippet("one", "Deploy", "release deploy", "Release"),
            CommandSnippet("two", "Restart", "restart service", "Operations"),
            CommandSnippet("three", "Status", "status", "Operations"),
        ]
        presenter = SnippetPresenter(lambda: snippets, lambda: [], lambda: [])

        self.assertEqual(
            [item.id for item in presenter.manager_items(query="service")],
            ["two"],
        )
        self.assertEqual(
            [item.label for item in presenter.manager_items(query="service")],
            ["Operations · Restart"],
        )
        self.assertEqual(
            [item.id for item in presenter.manager_items(category="Operations")],
            ["two", "three"],
        )
        self.assertEqual(
            [item.label for item in presenter.manager_items(category="Operations")],
            ["Restart", "Status"],
        )
        self.assertEqual(
            [item.label for item in presenter.run_items(None, "restart")],
            ["Operations · Restart"],
        )

    def test_presenter_can_list_uncategorized_snippets(self):
        snippets = [
            CommandSnippet("one", "Notes", "cat notes"),
            CommandSnippet("two", "Deploy", "deploy", "Release"),
        ]
        presenter = SnippetPresenter(lambda: snippets, lambda: [], lambda: [])

        self.assertEqual([item.id for item in presenter.manager_items(category="")], ["one"])
        self.assertEqual([item.label for item in presenter.manager_items(category="")], ["Notes"])


class SnippetStoreTests(unittest.TestCase):
    def test_category_management_preserves_and_copies_snippets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(
                root / "connections.json", root / "settings.json", root / "statistics.json",
                root / "lock", root / "history",
            )
            try:
                store.add_snippet_category("Empty")
                self.assertEqual(store.data.snippet_categories, ["Empty"])
                with self.assertRaises(SnippetError):
                    store.add_snippet_category(" empty ")
                with self.assertRaises(SnippetError):
                    store.duplicate_snippet_category("Missing", "Copy")
                store.rename_snippet_category("Empty", "Operations")
                original = store.add_snippet("Restart", "true", "Operations")
                store.duplicate_snippet_category("Operations", "Operations copy")
                with self.assertRaises(SnippetError):
                    store.rename_snippet_category("Operations", "operations COPY")
                copy = next(item for item in store.data.snippets if item.category == "Operations copy")
                self.assertNotEqual(copy.id, original.id)
                self.assertEqual((copy.name, copy.content), (original.name, original.content))
                store.delete_snippet_category("Operations")
                self.assertEqual(store.data.snippets[0].category, "")
                self.assertEqual(store.data.snippets[0].id, original.id)
                self.assertEqual(store.data.snippet_categories, ["Operations copy"])
            finally:
                store.close()

            restored = ConnectionStore(
                root / "connections.json", root / "settings.json", root / "statistics.json",
                root / "second-lock", root / "history",
            )
            try:
                self.assertEqual(restored.data.snippet_categories, ["Operations copy"])
                self.assertEqual(len(restored.data.snippets), 2)
            finally:
                restored.close()

    def test_empty_category_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = (
                root / "connections.json", root / "settings.json",
                root / "statistics.json", root / "lock", root / "history",
            )
            store = ConnectionStore(*args)
            try:
                store.add_snippet_category("Empty")
            finally:
                store.close()
            restored = ConnectionStore(*args)
            try:
                self.assertEqual(restored.data.snippet_categories, ["Empty"])
                self.assertEqual(restored.data.snippets, [])
            finally:
                restored.close()

    def test_category_management_respects_read_only_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = ConnectionStore(
                root / "connections.json", root / "settings.json", root / "statistics.json",
                root / "lock", root / "history",
            )
            second = ConnectionStore(
                root / "connections.json", root / "settings.json", root / "statistics.json",
                root / "lock", root / "history",
            )
            try:
                self.assertTrue(second.read_only)
                with self.assertRaises(ReadOnlyStoreError):
                    second.add_snippet_category("Blocked")
            finally:
                second.close()
                first.close()

    def test_store_rejects_missing_scope_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(
                root / "connections.json",
                root / "settings.json",
                root / "statistics.json",
                root / "lock",
                root / "history",
            )
            try:
                with self.assertRaises(SnippetError):
                    store.add_snippet(
                        "Missing server",
                        "true",
                        scope="server",
                        target_id="missing",
                    )
            finally:
                store.close()

    def test_snippets_round_trip_in_connection_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(root / "connections.json", root / "settings.json", root / "statistics.json", root / "lock", root / "history")
            try:
                snippet = store.add_snippet("Restart", "systemctl restart {{service}}", "System")
                store.update_snippet(snippet.id, "Restart service", "systemctl restart {{service}}", "Operations")
            finally:
                store.close()
            payload = json.loads((root / "connections.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["snippets"][0]["name"], "Restart service")
            restored = ConnectionStore(root / "connections.json", root / "settings.json", root / "statistics.json", root / "second-lock", root / "history")
            try:
                self.assertEqual(restored.data.snippets[0].category, "Operations")
                self.assertEqual(restored.data.snippets[0].content, "systemctl restart {{service}}")
            finally:
                restored.close()

    def test_deleting_targets_removes_scoped_snippets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(root / "connections.json", root / "settings.json", root / "statistics.json", root / "lock", root / "history")
            try:
                group = store.add_group("Production")
                server = store.add_server("Web", "host", "user", 22, group.id)
                store.add_snippet("Group", "true", scope="group", target_id=group.id)
                store.add_snippet("Server", "true", scope="server", target_id=server.id)

                store.delete_group(group.id)

                self.assertEqual(store.data.snippets, [])
            finally:
                store.close()
