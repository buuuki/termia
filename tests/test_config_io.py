import json
import tempfile
import unittest
from pathlib import Path

from termia.config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    CONNECTION_STORAGE_OBFUSCATED,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
    read_connections_payload,
    workspaces_from_payload,
    write_connections_file,
)
from termia.models import Group, LocalTerminalProfile, Server, Workspace


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
            write_connections_file(path, self.groups, self.servers, self.terminals, "plain", workspaces=self.workspaces)

            payload = read_connections_payload(path)

        self.assertEqual(payload["groups"][0]["name"], "Production")
        self.assertEqual(payload["servers"][0]["host"], "example.test")
        self.assertEqual(payload["local_terminals"][0]["name"], "Shell")
        self.assertEqual(payload["workspaces"][0]["name"], "Production")
        self.assertNotIn("password", payload["workspaces"][0])

    def test_obfuscated_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            write_connections_file(path, self.groups, self.servers, self.terminals, CONNECTION_STORAGE_OBFUSCATED)

            payload = read_connections_payload(path)

        self.assertEqual(payload["servers"][0]["id"], "server-1")

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
            )

            with self.assertRaises(MissingMasterPasswordError):
                read_connections_payload(path)
            with self.assertRaises(InvalidMasterPasswordError):
                read_connections_payload(path, "wrong horse")
            payload = read_connections_payload(path, "correct horse")

        self.assertEqual(payload["servers"][0]["user"], "admin")

    def test_invalid_json_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaises(ValueError):
                read_connections_payload(path)

    def test_workspace_import_discards_non_layout_data(self) -> None:
        workspaces = workspaces_from_payload(
            [
                {
                    "id": "workspace-1",
                    "name": "Production",
                    "tabs": [
                        {
                            "layout": {
                                "type": "pane",
                                "connection_type": "server",
                                "connection_id": "server-1",
                                "password": "must-not-be-persisted",
                            }
                        }
                    ],
                }
            ]
        )

        self.assertEqual(workspaces[0].tabs[0]["layout"], {
            "type": "pane",
            "connection_type": "server",
            "connection_id": "server-1",
        })
