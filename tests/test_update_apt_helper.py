import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from termia import update_apt_helper as helper


class AptHelperTests(unittest.TestCase):
    def test_packages_refresh_and_install_without_shell_or_removals(self):
        run = Mock(return_value=SimpleNamespace(returncode=0))
        self.assertEqual(helper.transaction(["packages", "gir1.2-gtksource-5"], run), 0)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0], [
            "/usr/bin/apt-get", "-o", "APT::Update::Error-Mode=any", "update",
        ])
        self.assertEqual(run.call_args.args[0], [
            "/usr/bin/apt-get", "--yes", "--no-remove", "-o",
            "DPkg::Lock::Timeout=15", "install", "gir1.2-gtksource-5",
        ])
        self.assertTrue(all(not call.kwargs.get("shell", False) for call in run.call_args_list))

    def test_refresh_failure_never_runs_install(self):
        run = Mock(return_value=SimpleNamespace(returncode=100))
        self.assertEqual(helper.transaction(["packages", "synthetic-package"], run), 100)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-1], "update")

    def test_install_failure_is_preserved(self):
        run = Mock(side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=42)])
        self.assertEqual(helper.transaction(["packages", "synthetic-package"], run), 42)

    def test_invalid_package_arguments_never_run_apt(self):
        run = Mock()
        for values in ([], ["--remove"], ["pkg-"], ["pkg;id"], ["$(id)"], ["pkg"] * 129):
            with self.subTest(values=values), self.assertRaises(ValueError):
                helper.transaction(["packages", *values], run)
        run.assert_not_called()

    def test_debian_install_uses_verified_private_copy_after_original_changes(self):
        data = b"synthetic verified package"
        seen = []
        with tempfile.TemporaryDirectory(prefix="termia package ") as directory:
            source = Path(directory) / "package.deb"
            source.write_bytes(data)

            def run(arguments, **_options):
                if arguments[-1] == "update":
                    source.write_bytes(b"synthetic replacement")
                else:
                    staged = Path(arguments[-1])
                    seen.append(staged)
                    self.assertNotEqual(staged, source)
                    self.assertEqual(staged.read_bytes(), data)
                    self.assertEqual(stat.S_IMODE(staged.stat().st_mode), 0o644)
                    self.assertEqual(stat.S_IMODE(staged.parent.stat().st_mode), 0o755)
                    self.assertEqual(staged.stat().st_uid, os.geteuid())
                return SimpleNamespace(returncode=0)

            self.assertEqual(helper.transaction([
                "debian", hashlib.sha256(data).hexdigest(), str(len(data)), str(source),
            ], run), 0)
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())

    def test_unverified_or_symlink_package_never_reaches_apt(self):
        data = b"synthetic verified package"
        run = Mock()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "package.deb"
            source.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            for expected, size in (("0" * 64, len(data)), (digest, len(data) + 1)):
                with self.subTest(expected=expected, size=size), self.assertRaises(ValueError):
                    helper.transaction(["debian", expected, str(size), str(source)], run)
            link = Path(directory) / "linked.deb"
            link.symlink_to(source)
            with self.assertRaises(OSError):
                helper.transaction(["debian", digest, str(len(data)), str(link)], run)
        run.assert_not_called()

    def test_invalid_metadata_never_reaches_apt(self):
        run = Mock()
        for arguments in ([], ["unknown"], ["debian", "invalid", "1", "unused"],
                          ["debian", "0" * 64, "0", "unused"],
                          ["debian", "0" * 64, str(helper.MAX_PACKAGE + 1), "unused"]):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                helper.transaction(arguments, run)
        run.assert_not_called()

    def test_entry_point_requires_root_before_starting_transaction(self):
        with patch.object(helper.os, "geteuid", return_value=1100), \
                patch.object(helper, "transaction") as transaction:
            self.assertEqual(helper.main(["packages", "synthetic-package"]), 77)
        transaction.assert_not_called()
