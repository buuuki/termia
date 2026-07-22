import unittest

from termia.models import Group, LocalTerminalProfile, Server
from termia.sidebar_projection import build_sidebar_projection


class SidebarProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.groups = [
            Group(id="prod", name="Production"),
            Group(id="nested", name="Nested", parent_id="prod"),
        ]
        self.servers = [
            Server(id="web", name="Web", host="web.test", user="admin", group_id="nested", favorite=True),
            Server(id="db", name="Database", host="db.test", user="db", group_id="prod"),
            Server(id="loose", name="Loose", host="loose.test", user="user"),
        ]
        self.profiles = [
            LocalTerminalProfile(id="z", name="Zulu"),
            LocalTerminalProfile(id="a", name="Alpha", working_directory="/srv/projects"),
        ]

    def build(self, **kwargs: object):
        options = {
            "groups": self.groups,
            "servers": self.servers,
            "local_terminal_profiles": self.profiles,
            "recent_server_ids": ["db", "db", "missing", "web"],
            "query": "",
            "expanded_groups": {},
            "collapse_groups_on_startup": False,
        }
        options.update(kwargs)
        return build_sidebar_projection(**options)

    def test_projection_indexes_sections_and_rows_in_one_result(self) -> None:
        projection = self.build()

        self.assertEqual([profile.id for profile in projection.local_terminal_profiles], ["a", "z"])
        self.assertEqual([server.id for server in projection.recent_servers], ["db", "web"])
        self.assertEqual([server.id for server in projection.favorite_servers], ["web"])
        self.assertEqual([group.id for group in projection.root_groups], ["prod"])
        self.assertEqual([server.id for server in projection.ungrouped_servers], ["loose"])
        self.assertEqual(
            [(row.kind, row.item_id) for row in projection.rows],
            [
                ("local_terminal", "a"),
                ("local_terminal", "z"),
                ("recent", "db"),
                ("recent", "web"),
                ("favorite", "web"),
                ("group", "prod"),
                ("group", "nested"),
                ("server", "web"),
                ("server", "db"),
                ("server", "loose"),
            ],
        )

    def test_collapsed_groups_are_hidden_from_navigation_rows(self) -> None:
        projection = self.build(expanded_groups={"prod": False})

        self.assertEqual(
            [(row.kind, row.item_id) for row in projection.rows],
            [
                ("local_terminal", "a"),
                ("local_terminal", "z"),
                ("recent", "db"),
                ("recent", "web"),
                ("favorite", "web"),
                ("group", "prod"),
                ("server", "loose"),
            ],
        )

    def test_query_expands_matching_hierarchy_and_filters_sections(self) -> None:
        projection = self.build(query="projects", expanded_groups={"prod": False})

        self.assertEqual([profile.id for profile in projection.local_terminal_profiles], ["a"])
        self.assertEqual(projection.recent_servers, [])
        self.assertEqual(projection.favorite_servers, [])
        self.assertEqual([(row.kind, row.item_id) for row in projection.rows], [("local_terminal", "a")])
