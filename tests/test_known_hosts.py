import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from termia.known_hosts import inspect_known_host_async, known_host_lookup_commands


class FakeProcess:
    def __init__(self, successful: bool) -> None:
        self.successful = successful

    def wait_async(self, _cancellable, callback) -> None:
        callback(self, object())

    def wait_finish(self, _result) -> bool:
        return True

    def get_successful(self) -> bool:
        return self.successful


class FakeLauncher:
    def __init__(self, results: list[bool], commands: list[list[str]]) -> None:
        self.results = results
        self.commands = commands

    def spawnv(self, command: list[str]) -> FakeProcess:
        self.commands.append(command)
        return FakeProcess(self.results.pop(0))


class KnownHostsTests(unittest.TestCase):
    def test_builds_lookups_only_for_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "known_hosts"
            existing.touch()
            missing = Path(directory) / "known_hosts2"

            commands = known_host_lookup_commands(
                "example.test",
                2200,
                "/usr/bin/ssh-keygen",
                [existing, missing],
            )

        self.assertEqual(
            commands,
            [
                ["/usr/bin/ssh-keygen", "-F", "[example.test]:2200", "-f", str(existing)],
                ["/usr/bin/ssh-keygen", "-F", "example.test", "-f", str(existing)],
            ],
        )

    def test_uses_only_host_for_default_ssh_port(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            known_hosts = Path(directory) / "known_hosts"
            known_hosts.touch()

            commands = known_host_lookup_commands(
                "example.test",
                22,
                "/usr/bin/ssh-keygen",
                [known_hosts],
            )

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][2], "example.test")

    def test_checks_files_sequentially_until_host_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "known_hosts"
            second = Path(directory) / "known_hosts2"
            first.touch()
            second.touch()
            commands: list[list[str]] = []
            launcher = FakeLauncher([False, False, True], commands)
            results: list[bool] = []

            with (
                patch("termia.known_hosts.GLib.find_program_in_path", return_value="/usr/bin/ssh-keygen"),
                patch("termia.known_hosts.Gio.SubprocessLauncher.new", return_value=launcher),
            ):
                inspect_known_host_async(
                    "example.test",
                    2200,
                    results.append,
                    known_hosts_files=[first, second],
                )

        self.assertEqual(results, [True])
        self.assertEqual(len(commands), 3)
        self.assertEqual(commands[0][2], "[example.test]:2200")

    def test_reports_unknown_after_all_files_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            known_hosts = Path(directory) / "known_hosts"
            known_hosts.touch()
            launcher = FakeLauncher([False, False], [])
            results: list[bool] = []

            with (
                patch("termia.known_hosts.GLib.find_program_in_path", return_value="/usr/bin/ssh-keygen"),
                patch("termia.known_hosts.Gio.SubprocessLauncher.new", return_value=launcher),
            ):
                inspect_known_host_async(
                    "example.test",
                    22,
                    results.append,
                    known_hosts_files=[known_hosts],
                )

        self.assertEqual(results, [False])

    def test_defers_unknown_result_when_ssh_keygen_is_missing(self) -> None:
        callback = unittest.mock.Mock()

        with (
            patch("termia.known_hosts.GLib.find_program_in_path", return_value=None),
            patch("termia.known_hosts.GLib.idle_add") as idle_add,
        ):
            inspect_known_host_async("example.test", 22, callback)

        idle_add.assert_called_once_with(callback, False)
        callback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
