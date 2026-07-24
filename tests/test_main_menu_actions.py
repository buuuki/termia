import unittest
from dataclasses import fields

from termia.main_menu_actions import MainMenuActions


class MainMenuActionsTests(unittest.TestCase):
    def test_each_explicit_action_dispatches_to_its_callback(self) -> None:
        calls = []

        def action(name):
            return lambda: calls.append(name)

        actions = MainMenuActions(
            general_preferences=action("general_preferences"),
            terminal_settings=action("terminal_settings"),
            prompt_settings=action("prompt_settings"),
            keybinding_settings=action("keybinding_settings"),
            security_settings=action("security_settings"),
            statistics=action("statistics"),
            connection_history=action("connection_history"),
            data_locations=action("data_locations"),
            export_config=action("export_config"),
            import_config=action("import_config"),
            import_asbru_config=action("import_asbru_config"),
            clear_config=action("clear_config"),
            help=action("help"),
            about=action("about"),
        )

        action_names = [field.name for field in fields(actions)]
        for name in action_names:
            getattr(actions, name)()

        self.assertEqual(calls, action_names)
