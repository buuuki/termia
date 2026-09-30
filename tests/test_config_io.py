import json
import tempfile
import unittest
from pathlib import Path

from termia.config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    CONNECTION_STORAGE_OBFUSCATED,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
    load_store_data_from_json,
    read_connections_payload,
    workspaces_from_payload,
    write_connections_file,
)
from termia.models import CommandSnippet, Group, LocalTerminalProfile, Server, StoreData, Workspace


class ConfigIOTests(unittest.TestCase):
    def setUp(self) -> None:
        self.groups = [Group(id="group-1", name="Production")]
        self.servers = [Server(id="server-1", name="web", host="example.test", user="admin")]
        self.terminals = [LocalTerminalProfile(id="local-1", name="Shell")]
        self.workspaces = [
            Workspace(
                id="workspace-1",
                name="Production",
                tabs=[
                    {
                        "layout": {
                            "type": "pane",
                            "connection_type": "server",
                            "connection_id": "server-1",
                        }
                    }
                ],
            )
        ]

    def test_plain_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            write_connections_file(
                path,
                self.groups,
                self.servers,
                self.terminals,
                "plain",
                workspaces=self.workspaces,
                snippets=[CommandSnippet("snippet-1", "Restart", "systemctl restart {{service}}")],
                snippet_categories=["Empty"],
            )

            payload = read_connections_payload(path)

        self.assertEqual(payload["groups"][0]["name"], "Production")
        self.assertEqual(payload["servers"][0]["host"], "example.test")
        self.assertEqual(payload["local_terminals"][0]["name"], "Shell")
        self.assertEqual(payload["workspaces"][0]["name"], "Production")
        self.assertEqual(payload["snippets"][0]["name"], "Restart")
        self.assertEqual(payload["snippet_categories"], ["Empty"])
        self.assertNotIn("password", payload["workspaces"][0])

    def test_import_retains_empty_and_snippet_categories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            write_connections_file(
                path, self.groups, self.servers, self.terminals, "plain",
                snippets=[CommandSnippet("snippet-1", "Deploy", "true", "Release")],
                snippet_categories=["Empty"],
            )
            imported = load_store_data_from_json(path, StoreData())

        self.assertEqual(imported.snippet_categories, ["Empty", "Release"])
        self.assertEqual(imported.snippets[0].category, "Release")

    def test_obfuscated_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            write_connections_file(
                path,
                self.groups,
                self.servers,
                self.terminals,
                CONNECTION_STORAGE_OBFUSCATED,
                snippets=[CommandSnippet("snippet-1", "Restart", "true")],
                snippet_categories=["Empty"],
            )

            payload = read_connections_payload(path)

        self.assertEqual(payload["servers"][0]["id"], "server-1")
        self.assertEqual(payload["snippets"][0]["id"], "snippet-1")
        self.assertEqual(payload["snippet_categories"], ["Empty"])

    def test_encrypted_round_trip_and_password_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            write_connections_file(
                path,
                self.groups,
                self.servers,
                self.terminals,
                CONNECTION_STORAGE_ENCRYPTED,
                "correct horse",
                snippets=[CommandSnippet("snippet-1", "Restart", "true")],
                snippet_categories=["Empty"],
            )

            with self.assertRaises(MissingMasterPasswordError):
                read_connections_payload(path)
            with self.assertRaises(InvalidMasterPasswordError):
                read_connections_payload(path, "wrong horse")
            payload = read_connections_payload(path, "correct horse")

        self.assertEqual(payload["servers"][0]["user"], "admin")
        self.assertEqual(payload["snippets"][0]["id"], "snippet-1")
        self.assertEqual(payload["snippet_categories"], ["Empty"])

    def test_invalid_json_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaises(ValueError):
                read_connections_payload(path)

    def test_workspace_import_keeps_safe_local_context_and_discards_private_data(self) -> None:
        workspaces = workspaces_from_payload(
            [
                {
                    "id": "workspace-1",
                    "name": "Production",
                    "tabs": [
                        {
                            "title": "Project shell",
                            "layout": {
                                "type": "pane",
                                "connection_type": "local",
                                "connection_id": "local-1",
                                "working_directory": "/srv/project",
                                "password": "must-not-be-persisted",
                            }
                        }
                    ],
                }
            ]
        )

        self.assertEqual(workspaces[0].tabs[0], {
            "title": "Project shell",
            "layout": {
                "type": "pane",
                "connection_type": "local",
                "connection_id": "local-1",
                "working_directory": "/srv/project",
            },
        })
