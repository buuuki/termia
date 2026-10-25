import base64
import json
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from termia import config_io
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
from termia.models import (
    CommandSnippet,
    Group,
    LocalTerminalProfile,
    Note,
    Server,
    StoreData,
    Workspace,
)


class ConfigIOTests(unittest.TestCase):
    def test_kdf_budget_is_checked_before_derivation(self) -> None:
        with patch.object(config_io, "PBKDF2HMAC") as kdf:
            with self.assertRaises(config_io.StorageLimitError):
                config_io.derive_connections_key("synthetic", b"0" * 16, config_io.MAX_KDF_ITERATIONS + 1)
            kdf.assert_not_called()
            for invalid in (True, None, 99_999, "390000"):
                with self.subTest(iterations=invalid), self.assertRaises(ValueError):
                    config_io.validate_iterations(invalid)
            config_io.validate_iterations(config_io.MAX_KDF_ITERATIONS)

    def test_decompression_budget_and_incomplete_streams(self) -> None:
        with patch.object(config_io, "MAX_DECODED_BYTES", 64):
            self.assertEqual(config_io.bounded_decompress(zlib.compress(b"x" * 64)), b"x" * 64)
            with self.assertRaises(config_io.StorageLimitError):
                config_io.bounded_decompress(zlib.compress(b"x" * 65))
            for data in (b"invalid", zlib.compress(b"small")[:-1], zlib.compress(b"small") + b"trailing"):
                with self.subTest(data=data), self.assertRaises(ValueError):
                    config_io.bounded_decompress(data)

    def test_file_budget_preserves_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            original = b" " * 65
            path.write_bytes(original)
            with patch.object(config_io, "MAX_STORAGE_BYTES", 64):
                with self.assertRaises(config_io.StorageLimitError):
                    config_io.read_storage_bytes(path)
                with self.assertRaises(config_io.StorageLimitError):
                    write_connections_file(path, self.groups, self.servers, self.terminals, "plain")
            self.assertEqual(path.read_bytes(), original)

    def test_store_limit_rejection_is_sticky_and_preserves_original(self) -> None:
        from termia.stores import ConnectionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "connections.json"
            original = b" " * 65
            path.write_bytes(original)
            with patch.object(config_io, "MAX_STORAGE_BYTES", 64):
                store = ConnectionStore(path, root / "settings.json", root / "statistics.json",
                                        root / "instance.lock", root / "history.jsonl")
            try:
                self.assertTrue(store.resource_limit_error)
                self.assertTrue(store.read_only)
                store.read_only = False
                self.assertTrue(store.read_only)
                store.load()
                store.save()
                self.assertFalse(store.unlock_connections("synthetic"))
                self.assertEqual(path.read_bytes(), original)
                self.assertFalse(list(root.glob("connections.json.invalid-*")))
            finally:
                store.close()

    def test_notes_limit_blocks_both_stores_without_recovery_rename(self) -> None:
        from termia.stores import ConnectionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connections = root / "connections.json"
            write_connections_file(connections, [], [], [], "plain")
            original_connections = connections.read_bytes()
            notes = root / "notes.json"
            original_notes = b" " * 1025
            notes.write_bytes(original_notes)
            with patch.object(config_io, "MAX_STORAGE_BYTES", 1024):
                store = ConnectionStore(connections, root / "settings.json", root / "statistics.json",
                                        root / "instance.lock", root / "history.jsonl")
            try:
                self.assertTrue(store.read_only)
                self.assertTrue(store.notes_file_store.resource_limit_error)
                store.save()
                store.notes_file_store.save("plain")
                self.assertEqual(connections.read_bytes(), original_connections)
                self.assertEqual(notes.read_bytes(), original_notes)
                self.assertFalse(list(root.glob("notes.json.invalid-*")))
            finally:
                store.close()

    def test_envelope_limits_precede_password_prompt_for_both_formats(self) -> None:
        from termia.notes_io import NOTES_ENCRYPTED_FORMAT, decode_notes_payload

        for format_name, reader in (
            (config_io.ENCRYPTED_CONNECTIONS_FORMAT, config_io.decoded_connections_payload),
            (NOTES_ENCRYPTED_FORMAT, decode_notes_payload),
        ):
            payload = {"format": format_name, "iterations": config_io.MAX_KDF_ITERATIONS + 1}
            with self.subTest(format=format_name), self.assertRaises(config_io.StorageLimitError):
                reader(payload)

    def test_obfuscated_readers_preserve_limit_exception(self) -> None:
        from termia.notes_io import NOTES_OBFUSCATED_FORMAT, decode_notes_payload

        encoded = base64.b64encode(zlib.compress(json.dumps({"value": "x" * 65}).encode())).decode()
        for format_name, reader in (
            (config_io.OBFUSCATED_CONNECTIONS_FORMAT, config_io.decoded_connections_payload),
            (NOTES_OBFUSCATED_FORMAT, decode_notes_payload),
        ):
            with (
                self.subTest(format=format_name),
                patch.object(config_io, "MAX_DECODED_BYTES", 64),
                self.assertRaises(config_io.StorageLimitError),
            ):
                reader({"format": format_name, "payload": encoded})

    def test_notes_writer_and_import_rejection_preserve_destination(self) -> None:
        from termia.notes_io import read_notes_file, write_notes_file

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.json"
            original = b" " * 65
            path.write_bytes(original)
            with patch.object(config_io, "MAX_STORAGE_BYTES", 64):
                with self.assertRaises(config_io.StorageLimitError):
                    read_notes_file(path)
                with self.assertRaises(config_io.StorageLimitError):
                    write_notes_file(path, [Note("synthetic", "Synthetic", "x" * 65)], [], "plain")
            self.assertEqual(path.read_bytes(), original)

    def test_recovery_requires_new_store_after_compatible_restore(self) -> None:
        from termia.stores import ConnectionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "connections.json"
            path.write_bytes(b" " * 65)
            args = (path, root / "settings.json", root / "statistics.json",
                    root / "instance.lock", root / "history.jsonl")
            with patch.object(config_io, "MAX_STORAGE_BYTES", 64):
                store = ConnectionStore(*args)
            try:
                write_connections_file(path, [], [], [], "plain")
                store.load()
                self.assertTrue(store.read_only)
            finally:
                store.close()
            restored = ConnectionStore(*args)
            try:
                self.assertFalse(restored.resource_limit_error)
                self.assertFalse(restored.read_only)
            finally:
                restored.close()

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

    def test_server_startup_command_round_trip_and_legacy_default(self) -> None:
        self.servers[0].command_on_start = "cd /srv/app && ./start.sh"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            write_connections_file(path, self.groups, self.servers, self.terminals, "plain")
            imported = load_store_data_from_json(path, StoreData())
            self.assertEqual(imported.servers[0].command_on_start, "cd /srv/app && ./start.sh")

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["servers"][0].pop("command_on_start")
            path.write_text(json.dumps(payload), encoding="utf-8")
            legacy_imported = load_store_data_from_json(path, StoreData())

        self.assertEqual(legacy_imported.servers[0].command_on_start, "")

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

    def test_connection_import_preserves_separate_notes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "connections.json"
            write_connections_file(path, self.groups, self.servers, self.terminals, "plain")
            note = Note("note-1", "Runbook", "Restart", server_id="server-1")
            current = StoreData(notes=[note], note_categories=["Ops"])
            imported = load_store_data_from_json(path, current)

        self.assertEqual(imported.notes, [note])
        self.assertEqual(imported.note_categories, ["Ops"])

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

            with self.assertRaises(TypeError):
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
