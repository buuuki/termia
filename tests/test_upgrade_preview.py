"""Security contracts for preparing the disposable updater preview."""
import hashlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from termia.update_service import OfficialRedirects, ReleaseClient, UpdateError

PREPARE_PATH = (Path(__file__).resolve().parents[1]
                / "tools/docker-lab/upgrade-preview/prepare.py")
PANEL_PATH = PREPARE_PATH.with_name("panel.py")


def load_preparer():
    spec = importlib.util.spec_from_file_location("termia_upgrade_preview_prepare", PREPARE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_panel():
    spec = importlib.util.spec_from_file_location("termia_upgrade_preview_panel", PANEL_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"tkinter": Mock()}), \
            patch("pathlib.Path.read_text", return_value="synthetic password"), \
            patch("subprocess.Popen", side_effect=AssertionError("Unexpected process during import")):
        spec.loader.exec_module(module)
    return module


class UpgradePreviewEvidenceTests(unittest.TestCase):
    def test_launch_allocates_unique_private_directories_and_retains_logs(self):
        panel = load_panel()
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "upgrade-evidence"
            evidence.mkdir()
            with patch.object(panel.tempfile, "gettempdir", return_value=directory), \
                    patch.object(panel.subprocess, "Popen") as spawn:
                spawn.return_value.poll.return_value = 0
                original_umask = os.umask(0)
                try:
                    panel.launch("proposed")
                    first = Path(spawn.call_args.kwargs["env"]["TERMIA_CONFIG_DIR"]).parent
                    first_log = first / "console.log"
                    first_log.write_text("synthetic evidence")
                    panel.launch("debian")
                    second = Path(spawn.call_args.kwargs["env"]["TERMIA_CONFIG_DIR"]).parent
                finally:
                    os.umask(original_umask)
                self.assertEqual(spawn.call_count, 2)
                self.assertNotEqual(first, second)
                for trial in (first, second):
                    self.assertEqual(trial.parent, evidence)
                    self.assertEqual(trial.stat().st_mode & 0o777, 0o700)
                    self.assertFalse(trial.is_symlink())
                    self.assertTrue((trial / "console.log").is_file())
                self.assertEqual(first_log.read_text(), "synthetic evidence")
                self.assertIn(second.name, panel.status.set.call_args.args[0])

    def test_busy_trial_does_not_allocate_another_directory_or_process(self):
        panel = load_panel()
        panel.child = Mock()
        panel.child.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "upgrade-evidence"
            evidence.mkdir()
            with patch.object(panel.tempfile, "gettempdir", return_value=directory), \
                    patch.object(panel.subprocess, "Popen") as spawn:
                panel.launch("proposed")
            spawn.assert_not_called()
            self.assertEqual(list(evidence.iterdir()), [])


class UpgradePreviewPreparationTests(unittest.TestCase):
    def test_import_does_not_prepare_or_execute_commands(self):
        with patch("pathlib.Path.mkdir") as mkdir, \
                patch("subprocess.run") as run, \
                patch("subprocess.check_output") as output:
            load_preparer()
        mkdir.assert_not_called()
        run.assert_not_called()
        output.assert_not_called()

    def test_main_uses_the_official_client_and_writes_only_verified_bytes(self):
        module = load_preparer()
        data = b"synthetic approved package"
        digest = hashlib.sha256(data).hexdigest()
        opener = Mock()
        opener.open.return_value = io.BytesIO(data)
        client = ReleaseClient(opener=opener)
        assets = [("v0.6.0-beta.4", "synthetic.deb", "fixture.deb", digest)]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "context"
            with patch.object(module, "CONTEXT", destination), \
                    patch.object(module, "ASSETS", assets), \
                    patch.object(module.subprocess, "run"), \
                    patch.object(module.subprocess, "check_output", return_value=b""), \
                    patch("termia.update_service.ReleaseClient", return_value=client) as factory, \
                    patch("sys.path", list(sys.path)), redirect_stdout(io.StringIO()):
                module.main()
            factory.assert_called_once_with()
            self.assertEqual((destination / "fixtures/fixture.deb").read_bytes(), data)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url,
                             "https://github.com/buuuki/termia/releases/download/"
                             "v0.6.0-beta.4/synthetic.deb")

    def test_bad_digest_stops_before_writing_a_package_or_running_git(self):
        module = load_preparer()
        opener = Mock()
        opener.open.return_value = io.BytesIO(b"synthetic modified package")
        client = ReleaseClient(opener=opener)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "context"
            assets = [("v0.6.0-beta.4", "synthetic.deb", "fixture.deb", "0" * 64)]
            with patch.object(module, "CONTEXT", destination), \
                    patch.object(module, "ASSETS", assets), \
                    patch.object(module.subprocess, "run") as run, \
                    patch("termia.update_service.ReleaseClient", return_value=client), \
                    patch("sys.path", list(sys.path)), \
                    self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                module.main()
            run.assert_not_called()
            self.assertEqual(list((destination / "fixtures").iterdir()), [])

    def test_nonofficial_initial_urls_never_reach_the_network(self):
        module = load_preparer()
        for url in ("file:///synthetic-unread", "http://github.com/buuuki/termia/releases/download/a/b",
                    "https://example.invalid/synthetic.deb"):
            with self.subTest(url=url):
                opener = Mock()
                with self.assertRaises(UpdateError):
                    module.download_package(url, "0" * 64, ReleaseClient(opener=opener))
                opener.open.assert_not_called()

    def test_redirects_reject_downgrades_and_nonofficial_hosts(self):
        client = ReleaseClient()
        redirects = next(handler for handler in client.opener.handlers
                         if isinstance(handler, OfficialRedirects))
        for target in ("http://release-assets.githubusercontent.com/synthetic",
                       "file:///synthetic-unread", "https://example.invalid/synthetic.deb"):
            with self.subTest(target=target), self.assertRaises(UpdateError):
                redirects.redirect_request(None, None, 302, "", {}, target)

    def test_oversized_download_is_rejected_before_digest_acceptance(self):
        module = load_preparer()
        data = b"synthetic oversized package"
        opener = Mock()
        opener.open.return_value = io.BytesIO(data)
        with patch.object(module, "MAX_ASSET_BYTES", len(data) - 1), \
                self.assertRaises(UpdateError):
            module.download_package(
                "https://github.com/buuuki/termia/releases/download/a/b",
                hashlib.sha256(data).hexdigest(), ReleaseClient(opener=opener))
