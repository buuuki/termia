import unittest

from termia.asbru_import import extract_asbru_connections, merge_asbru_connections, normalize_asbru_name
from termia.models import StoreData


class AsbruImportTests(unittest.TestCase):
    def test_normalizes_copy_suffix(self) -> None:
        self.assertEqual(normalize_asbru_name(" Server - copy - COPY "), "Server")

    def test_extracts_ssh_nodes_and_skips_other_protocols(self) -> None:
        groups, servers = extract_asbru_connections(
            {
                "environments": {
                    "prod": {"_is_group": True, "name": "Production"},
                    "web": {"name": "Web", "host": "admin@example.test", "port": "2200", "parent": "prod"},
                    "ftp": {"name": "Files", "host": "files.test", "method": "ftp"},
                }
            }
        )

        self.assertEqual(groups, [("prod", "Production", None)])
        self.assertEqual(servers, [("Web", "example.test", "admin", 2200, "prod", "", "")])

    def test_merge_deduplicates_and_preserves_credentials(self) -> None:
        data = StoreData()
        groups, servers = extract_asbru_connections(
            {"group": {"_is_group": True, "name": "Group"}, "server": {"name": "Web", "ip": "host", "parent": "group"}}
        )

        added_groups, added_servers = merge_asbru_connections(data, groups, servers)
        again = merge_asbru_connections(data, groups, [("Web", "host", "", 22, "group", "key", "secret")])

        self.assertEqual((added_groups, added_servers), (1, 1))
        self.assertEqual(again, (0, 0))
        self.assertEqual(data.servers[0].public_key, "key")
        self.assertEqual(data.servers[0].password, "secret")
