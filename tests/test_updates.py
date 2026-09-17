import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock

from termia.update_service import (
    Asset, OfficialRedirects, Release, ReleaseClient, UpdateError, Version,
    REPOSITORY, allowed_url, select_release,
)
from termia.update_installers import (
    DebianInstaller, GitInstaller, Installation, command, detect_installation,
    update_lock,
)
from termia.update_controller import CheckResult, UpdateController


def release(tag="v0.6.0-beta.2", **values):
    return dict(tag_name=tag, draft=False, prerelease="-" in tag, assets=[], **values)


class ReleasePolicyTests(unittest.TestCase):
    def test_numeric_order_and_development_to_release(self):
        self.assertLess(Version.parse("0.6.0-beta.2-dev"), Version.parse("0.6.0-beta.2"))
        self.assertLess(Version.parse("0.6.0-beta.9"), Version.parse("0.6.0-beta.10"))
        self.assertLess(Version.parse("0.6.0-beta.10"), Version.parse("0.6.0-rc.1"))
        self.assertLess(Version.parse("0.6.0-rc.1"), Version.parse("0.6.0"))
        self.assertEqual(Version.parse("0.5.0-beta"), Version.parse("0.5.0-beta.1"))

    def test_prerelease_stays_in_current_application_line(self):
        result = select_release([release("v0.7.0"), release(), release("v0.6.1-beta.1")], "0.6.0-beta.1")
        self.assertEqual(result.tag, "v0.6.0-beta.2")
        self.assertIsNone(select_release([release("v0.6.0-beta.1")], "0.6.0-beta.2-dev"))

    def test_stable_can_upgrade_but_never_to_prerelease(self):
        result = select_release([release("v0.7.0-beta.1"), release("v0.6.1")], "0.6.0")
        self.assertEqual(result.tag, "v0.6.1")

    def test_drafts_invalid_tags_and_development_tags_are_excluded(self):
        draft = release()
        draft["draft"] = True
        items = [draft, release("v0.6.0-beta.3-dev"), release("v0.6.0;evil"), release("v0.6.0-beta.1")]
        self.assertIsNone(select_release(items, "0.6.0-beta.1"))

    def test_missing_digest_prevents_automatic_debian_install(self):
        item = release()
        item["assets"] = [{"name": "termia_0.6.0.beta.2-1_all.deb"}]
        self.assertIsNone(select_release([item], "0.6.0-beta.1").asset)

    def test_asset_url_must_match_official_release(self):
        item = release()
        name = "termia_0.6.0.beta.2-1_all.deb"
        asset = dict(name=name, size=10, digest="sha256:" + "a" * 64,
                     browser_download_url=f"{REPOSITORY}/releases/download/{item['tag_name']}/{name}")
        item["assets"] = [asset]
        self.assertIsNotNone(select_release([item], "0.6.0-beta.1").asset)
        asset["browser_download_url"] = "https://example.org/package.deb"
        self.assertIsNone(select_release([item], "0.6.0-beta.1").asset)


class DownloadTests(unittest.TestCase):
    def client(self, data):
        opener = Mock()
        opener.open.side_effect = lambda *a, **kw: io.BytesIO(data)
        return ReleaseClient(opener)

    def test_download_verified_and_existing_file_never_removed(self):
        data = b"synthetic package"
        asset = Asset(f"{REPOSITORY}/releases/download/v0.6.0-beta.2/package.deb",
                      hashlib.sha256(data).hexdigest(), len(data))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.deb"
            self.client(data).download(asset, path, Event())
            self.assertEqual(path.read_bytes(), data)
            with self.assertRaises(FileExistsError):
                self.client(data).download(asset, path, Event())
            self.assertEqual(path.read_bytes(), data)

    def test_bad_digest_oversize_and_truncation_remove_partial_download(self):
        for size, digest in [(4, "a" * 64), (3, hashlib.sha256(b"test").hexdigest()), (5, "a" * 64)]:
            with self.subTest(size=size), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "package.deb"
                asset = Asset(f"{REPOSITORY}/releases/download/v0.6.0-beta.2/package.deb", digest, size)
                with self.assertRaises(UpdateError):
                    self.client(b"test").download(asset, path, Event())
                self.assertFalse(path.exists())

    def test_cancellation_prevents_network_request(self):
        client, cancel = self.client(b"test"), Event()
        cancel.set()
        with self.assertRaisesRegex(UpdateError, "update_cancelled"):
            client.read(f"{REPOSITORY}/releases/download/x/y", cancel, 10)
        client.opener.open.assert_not_called()

    def test_url_and_redirect_restrictions(self):
        for url in ["http://github.com/buuuki/termia/releases/download/a/b", "https://github.com.evil.invalid/x",
                    "https://github.com/other/repo/releases/download/a/b", "https://user@github.com/buuuki/termia/releases/download/a/b"]:
            self.assertFalse(allowed_url(url))
        with self.assertRaises(UpdateError):
            OfficialRedirects().redirect_request(None, None, 302, "", {}, "https://example.org/")

    def test_malformed_metadata_and_network_errors(self):
        for data in [b"not json", b'{}', b'[1]']:
            with self.assertRaises(UpdateError):
                self.client(data).releases(Event())
        client = self.client(b"")
        client.opener.open.side_effect = OSError("private path or token")
        with self.assertRaisesRegex(UpdateError, "^update_network_failed$"):
            client.releases(Event())


class InstallerTests(unittest.TestCase):
    def test_development_checkout_never_runs_git(self):
        run = Mock()
        adapter = GitInstaller(Path("/unused"), "0.6.0-beta.2-dev", run)
        self.assertEqual(adapter.availability(adapter.current, Event()), "update_checkout_blocked")
        run.assert_not_called()

    def test_real_clean_checkout_and_local_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True)
            git("init", "-b", "main")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "test")
            git("tag", "v0.6.0-beta.1")
            adapter = GitInstaller(root, "0.6.0-beta.1")
            self.assertEqual(adapter.availability(adapter.current, Event()), "")
            (root / "local-change").touch()
            self.assertEqual(adapter.availability(adapter.current, Event()), "update_checkout_blocked")
            (root / "local-change").unlink()
            git("switch", "-c", "feature/test")
            self.assertEqual(adapter.availability(adapter.current, Event()), "update_checkout_blocked")

    def test_debian_rejects_wrong_package_before_privileges(self):
        client, run = Mock(), Mock(side_effect=["other-package", "0.6.0~beta.2-1", "all"])
        adapter = DebianInstaller(client, run)
        candidate = Release("v0.6.0-beta.2", Version.parse("0.6.0-beta.2"), Asset("", "", 1))
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(UpdateError, "update_untrusted"):
            adapter.prepare(candidate, Path(directory), Event())
        self.assertFalse(any(call.args[0][0] == "/usr/bin/pkexec" for call in run.call_args_list))

    def test_git_applies_fast_forward_but_preserves_ignored_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", directory, *args], check=True, capture_output=True, text=True).stdout.strip()
            git("init", "-b", "main")
            (root / ".gitignore").write_text("protected\n")
            git("add", ".gitignore")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "base")
            git("tag", "v0.6.0-beta.1")
            previous = git("rev-parse", "HEAD")
            (root / "protected").write_text("new release content")
            git("add", "-f", "protected")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "next")
            target = git("rev-parse", "HEAD")
            git("checkout", "-B", "main", previous)
            (root / "protected").write_text("local ignored data")
            adapter = GitInstaller(root, "0.6.0-beta.1")
            adapter.original_head = previous
            candidate = select_release([release()], "0.6.0-beta.1")
            with self.assertRaises(UpdateError):
                adapter.apply(target, candidate)
            self.assertEqual((root / "protected").read_text(), "local ignored data")
            self.assertEqual(git("rev-parse", "HEAD"), previous)
            (root / "protected").unlink()
            adapter.apply(target, candidate)
            self.assertEqual(git("rev-parse", "HEAD"), target)

    def test_debian_rejects_changes_after_verification(self):
        data = b"verified"
        candidate = Release("v0.6.0-beta.2", Version.parse("0.6.0-beta.2"),
                            Asset("", hashlib.sha256(data).hexdigest(), len(data)))
        run = Mock()
        adapter = DebianInstaller(Mock(), run)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.deb"
            path.write_bytes(b"replaced")
            with self.assertRaisesRegex(UpdateError, "update_untrusted"):
                adapter.apply(path, candidate)
        run.assert_not_called()

    def test_debian_verified_download_and_exact_install_arguments(self):
        data = b"synthetic"
        candidate = Release("v0.6.0-beta.2", Version.parse("0.6.0-beta.2"),
                            Asset("", hashlib.sha256(data).hexdigest(), len(data)))
        client = Mock()
        client.download.side_effect = lambda asset, path, cancel: path.write_bytes(data)
        run = Mock(side_effect=["termia", "0.6.0~beta.2-1", "all", "0.6.0~beta.1-1", "", ""])
        adapter = DebianInstaller(client, run)
        with tempfile.TemporaryDirectory(prefix="termia test ") as directory:
            path = adapter.prepare(candidate, Path(directory), Event())
            adapter.apply(path, candidate)
            self.assertEqual(run.call_args.args[0][-2:], ["install", str(path)])
            self.assertEqual(run.call_args.args[0][0], "/usr/bin/pkexec")
            self.assertTrue(run.call_args.kwargs["applying"])

    def test_unknown_installation_is_check_only(self):
        result = detect_installation("0.6.0-beta.2", Mock(), Event(), Path("/tmp/unknown/package/update_installers.py"),
                                     Mock(return_value="different-package: /other"))
        self.assertIsNone(result.adapter)

    def test_lock_serializes_profiles(self):
        with update_lock():
            with self.assertRaisesRegex(UpdateError, "update_busy"):
                with update_lock():
                    self.fail("second lock acquired")

    def test_command_does_not_expose_stderr(self):
        with self.assertRaisesRegex(UpdateError, "^update_install_failed$"):
            command(["/usr/bin/false"], Event())


class ControllerTests(unittest.TestCase):
    def test_close_suppresses_queued_callbacks(self):
        queued, notifications = [], Mock()
        controller = UpdateController("0.6.0-beta.1", queued.append, notifications,
                                      Mock(releases=Mock(return_value=[])),
                                      Mock(return_value=Installation(None, "update_unknown_installation")))
        self.assertTrue(controller.check())
        controller.thread.join(5)
        self.assertFalse(controller.thread.is_alive())
        controller.close()
        for callback in queued:
            callback()
        notifications.assert_not_called()

    def test_cancel_during_prepare_does_not_apply_and_cleans_temp(self):
        entered, proceed = Event(), Event()
        paths = []
        adapter = Mock()
        def prepare(release, directory, cancel):
            paths.append(directory)
            entered.set()
            proceed.wait(5)
            return directory
        adapter.prepare.side_effect = prepare
        controller = UpdateController("0.6.0-beta.1", lambda f: None, Mock())
        result = CheckResult(select_release([release()], "0.6.0-beta.1"), Installation(adapter, ""))
        controller.install(result)
        self.assertTrue(entered.wait(5))
        self.assertFalse(controller.check())
        self.assertTrue(controller.stop())
        proceed.set()
        controller.thread.join(5)
        adapter.apply.assert_not_called()
        self.assertFalse(paths[0].exists())

    def test_application_cannot_be_cancelled_and_retains_temp_until_finished(self):
        entered, proceed = Event(), Event()
        adapter = Mock()
        adapter.prepare.side_effect = lambda r, directory, c: directory
        def apply(path, release):
            self.assertTrue(path.exists())
            entered.set()
            proceed.wait(5)
            self.assertTrue(path.exists())
        adapter.apply.side_effect = apply
        controller = UpdateController("0.6.0-beta.1", lambda f: None, Mock())
        result = CheckResult(select_release([release()], "0.6.0-beta.1"), Installation(adapter, ""))
        controller.install(result)
        self.assertTrue(entered.wait(5))
        self.assertFalse(controller.stop())
        controller.close()
        self.assertFalse(controller.cancel.is_set())
        proceed.set()
        controller.thread.join(5)
        self.assertFalse(controller.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
