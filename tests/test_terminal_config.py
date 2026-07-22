import unittest

from termia.models import TerminalSettings
from termia.terminal_config import (
    build_bash_rcfile_shell_command,
    build_local_prompt_shell_command,
    normalize_split_layout,
    normalized_prompt_template,
    prompt_template_with_datetime,
    render_prompt_preview,
    split_layout_plan,
    split_prompt_datetime_template,
)


class TerminalConfigTests(unittest.TestCase):
    def test_prompt_template_defaults_and_preview(self) -> None:
        self.assertEqual(normalized_prompt_template(""), r"\u@\h:\w\$ ")
        self.assertEqual(normalized_prompt_template(r"\w \$ "), r"\u@\h:\w\$ ")
        self.assertIn("usuario@servidor", render_prompt_preview(r"\u@\h:\w\$ "))

    def test_prompt_datetime_round_trip(self) -> None:
        template = prompt_template_with_datetime(r"\u@\h:\w\$ ", "both")

        self.assertEqual(split_prompt_datetime_template(template), ("both", r"\u@\h:\w\$ "))
        self.assertEqual(split_prompt_datetime_template("custom"), ("none", "custom"))

    def test_split_layouts_have_expected_plans(self) -> None:
        self.assertEqual(normalize_split_layout("unknown"), "none")
        self.assertEqual(len(split_layout_plan("grid")), 3)
        self.assertEqual(split_layout_plan("none"), [])

    def test_shell_commands_quote_arguments(self) -> None:
        command = build_bash_rcfile_shell_command("/bin/my bash", ["--name", "a value"], ["echo 'ready'"])
        local_command = build_local_prompt_shell_command(TerminalSettings(), "/bin/bash", ["--login"])

        self.assertEqual(command[:2], ["/bin/my bash", "-lc"])
        self.assertIn("'/bin/my bash'", command[2])
        self.assertIn("'a value'", command[2])
        self.assertEqual(local_command[:2], ["/bin/bash", "-lc"])
        self.assertIn("TERMIA_PS1=", local_command[2])
