import unittest

from termia.models import Group, LocalTerminalProfile, Server, Workspace
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
        self.workspaces = [Workspace(id="workspace", name="Production")]

    def build(self, **kwargs: object):
        options = {
            "groups": self.groups,
            "servers": self.servers,
            "local_terminal_profiles": self.profiles,
            "workspaces": self.workspaces,
            "recent_server_ids": ["db", "db", "missing", "web"],
            "query": "",
        }
        options.update(kwargs)
        return build_sidebar_projection(**options)

    def test_projection_indexes_sections_and_hierarchy(self) -> None:
        projection = self.build()

        self.assertEqual([profile.id for profile in projection.local_terminal_profiles], ["a", "z"])
        self.assertEqual([workspace.id for workspace in projection.workspaces], ["workspace"])
        self.assertEqual([server.id for server in projection.recent_servers], ["db", "web"])
        self.assertEqual([server.id for server in projection.favorite_servers], ["web"])
        self.assertEqual([group.id for group in projection.root_groups], ["prod"])
        self.assertEqual([server.id for server in projection.ungrouped_servers], ["loose"])
        self.assertEqual(projection.children_by_parent, {
            None: [self.groups[0]], "prod": [self.groups[1]],
        })
        self.assertEqual(projection.servers_by_group, {
            "nested": [self.servers[0]], "prod": [self.servers[1]], None: [self.servers[2]],
        })

    def test_server_search_filters_indexes_recent_and_favorite_sections(self) -> None:
        projection = self.build(query="web")

        self.assertEqual(projection.servers_by_group, {"nested": [self.servers[0]]})
        self.assertEqual([server.id for server in projection.recent_servers], ["web"])
        self.assertEqual([server.id for server in projection.favorite_servers], ["web"])
        self.assertEqual([group.id for group in projection.root_groups], ["prod"])
        self.assertEqual(projection.children_by_parent["prod"], [self.groups[1]])
        self.assertEqual(projection.ungrouped_servers, [])
        self.assertEqual(projection.local_terminal_profiles, [])
        self.assertEqual(projection.workspaces, [])

    def test_profile_directory_search_filters_other_sections(self) -> None:
        projection = self.build(query="projects")

        self.assertEqual([profile.id for profile in projection.local_terminal_profiles], ["a"])
        self.assertEqual(projection.workspaces, [])
        self.assertEqual(projection.recent_servers, [])
        self.assertEqual(projection.favorite_servers, [])
        self.assertEqual(projection.servers_by_group, {})
        self.assertEqual(projection.ungrouped_servers, [])
