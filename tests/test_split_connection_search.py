# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import unittest

from termia.models import LocalTerminalProfile, Server
from termia.split_connection_search import build_split_connection_choices, filter_split_connection_choices


class SplitConnectionSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.choices = build_split_connection_choices(
            [
                Server(id="prod", name="Production", host="prod.example.test", user="deploy", port=2222),
                Server(id="backup", name="Backups", host="backup.example.test", user="restore"),
            ],
            [
                LocalTerminalProfile(
                    id="logs",
                    name="Logs",
                    working_directory="/var/log/termia",
                    shell="/bin/bash",
                )
            ],
        )

    def test_choices_include_ssh_and_local_profiles_in_name_order(self) -> None:
        self.assertEqual([choice.connection_id for choice in self.choices], ["server:backup", "local:logs", "server:prod"])
        self.assertEqual(self.choices[-1].detail, "deploy@prod.example.test:2222")

    def test_filter_matches_server_name_host_user_and_port(self) -> None:
        self.assertEqual([choice.connection_id for choice in filter_split_connection_choices(self.choices, "production")], ["server:prod"])
        self.assertEqual([choice.connection_id for choice in filter_split_connection_choices(self.choices, "backup.example")], ["server:backup"])
        self.assertEqual([choice.connection_id for choice in filter_split_connection_choices(self.choices, "deploy")], ["server:prod"])
        self.assertEqual([choice.connection_id for choice in filter_split_connection_choices(self.choices, "2222")], ["server:prod"])

    def test_filter_matches_local_profile_details_case_insensitively(self) -> None:
        self.assertEqual([choice.connection_id for choice in filter_split_connection_choices(self.choices, "TERMIA")], ["local:logs"])
        self.assertEqual(filter_split_connection_choices(self.choices, "missing"), [])


if __name__ == "__main__":
    unittest.main()
