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
    render_snippet,
    snippet_variables,
)
from termia.stores import ConnectionStore


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


class SnippetStoreTests(unittest.TestCase):
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
