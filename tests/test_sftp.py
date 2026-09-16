import io
from pathlib import Path
from queue import Queue
import stat
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock
from unittest.mock import patch
from types import SimpleNamespace

import paramiko

from termia.sftp_service import (
    AuthenticationRequired, Cancelled, Endpoint, HostKeyChanged, SFTPService,
    UnknownHost, child_path,
)
from termia.sftp_backend import ParamikoBackend, RequireConfirmation


class SFTPTests(unittest.TestCase):
    def test_untrusted_names_cannot_escape_download_directory(self):
        for name in ("", ".", "..", "../secret", "/root", "a/b", "a\\b", "a\n", "a\x00"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                child_path("/safe", name)
        self.assertEqual(child_path("/safe", "file ; $(text).txt"), "/safe/file ; $(text).txt")

    def test_password_is_not_in_endpoint_repr(self):
        self.assertNotIn("test-secret", repr(Endpoint("example.test", 22, "test", password="test-secret")))

    def backend(self, **kwargs):
        return ParamikoBackend(Endpoint("example.test", 2222, "test"), known_hosts=(), **kwargs)

    def test_unknown_host_requires_confirmation_with_sha256(self):
        key = paramiko.RSAKey.generate(1024)
        with self.assertRaises(UnknownHost) as result:
            RequireConfirmation().missing_host_key(Mock(), "example.test", key)
        self.assertEqual(result.exception.key_data, key.get_base64())
        self.assertTrue(result.exception.fingerprint.startswith("SHA256:"))

    def test_bare_host_fallback_and_timeouts(self):
        key = paramiko.RSAKey.generate(1024)
        client = Mock()
        keys = paramiko.HostKeys()
        keys.add("example.test", key.get_name(), key)
        client.get_host_keys.return_value = keys
        client.open_sftp.return_value.normalize.return_value = "/home/test"
        backend = self.backend(client_factory=lambda: client)
        self.assertEqual(backend.connect(), "/home/test")
        self.assertEqual(keys.lookup("[example.test]:2222")[key.get_name()], key)
        self.assertEqual(client.connect.call_args.kwargs["timeout"], 10)
        backend.close()
        client.close.assert_called()

    def test_exact_endpoint_key_takes_precedence(self):
        client = Mock()
        keys = paramiko.HostKeys()
        bare, exact = paramiko.RSAKey.generate(1024), paramiko.RSAKey.generate(1024)
        keys.add("example.test", bare.get_name(), bare)
        keys.add("[example.test]:2222", exact.get_name(), exact)
        client.get_host_keys.return_value = keys
        backend = self.backend(client_factory=lambda: client)
        backend.connect()
        self.assertEqual(keys.lookup("[example.test]:2222")[exact.get_name()], exact)
        backend.close()

    def test_authentication_failure_closes_client(self):
        client = Mock()
        client.connect.side_effect = paramiko.AuthenticationException("sensitive detail")
        with self.assertRaises(AuthenticationRequired) as error:
            self.backend(client_factory=lambda: client).connect()
        self.assertNotIn("sensitive", str(error.exception))
        client.close.assert_called_once()

    def test_changed_key_is_not_an_accept_prompt(self):
        client = Mock()
        key = paramiko.RSAKey.generate(1024)
        client.connect.side_effect = paramiko.BadHostKeyException("example.test", key, key)
        with self.assertRaises(HostKeyChanged):
            self.backend(client_factory=lambda: client).connect()
        client.close.assert_called_once()

    def test_download_never_overwrites_or_follows_existing_symlink(self):
        backend = self.backend()
        backend.sftp = Mock()
        backend.sftp.lstat.return_value = Mock(st_mode=stat.S_IFREG, st_size=4)
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "existing"
            existing.write_text("keep")
            link = Path(directory) / "link"
            link.symlink_to(existing)
            for path in (existing, link):
                with self.assertRaises(FileExistsError):
                    backend.download("/remote", path, Mock())
            self.assertEqual(existing.read_text(), "keep")
            backend.sftp.open.assert_not_called()

    def test_remote_symlinks_are_not_downloaded(self):
        backend = self.backend()
        backend.sftp = Mock()
        backend.sftp.lstat.return_value = Mock(st_mode=stat.S_IFLNK)
        with self.assertRaises(ValueError):
            backend.download("/remote/link", Path("unused"), Mock())
        backend.sftp.open.assert_not_called()

    def test_failed_download_removes_partial_local_file(self):
        backend = self.backend()
        backend.sftp = Mock()
        backend.sftp.lstat.return_value = Mock(st_mode=stat.S_IFREG, st_size=4)
        backend.sftp.open.side_effect = OSError("connection lost")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            with self.assertRaises(OSError):
                backend.download("/remote", target, Mock())
            self.assertFalse(target.exists())

    def test_upload_uses_exclusive_creation(self):
        backend = self.backend()
        backend.sftp = Mock()
        backend.sftp.open.side_effect = FileExistsError()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.write_text("data")
            with self.assertRaises(FileExistsError):
                backend.upload(source, "/target", Mock())
        backend.sftp.open.assert_called_once_with("/target", "wx")

    def test_delete_only_empty_directories_and_unlinks_symlinks(self):
        backend = self.backend()
        backend.sftp = Mock()
        backend.sftp.lstat.return_value = Mock(st_mode=stat.S_IFDIR)
        backend.delete("/empty")
        backend.sftp.rmdir.assert_called_once_with("/empty")
        backend.sftp.lstat.return_value = Mock(st_mode=stat.S_IFLNK)
        backend.delete("/link")
        backend.sftp.remove.assert_called_once_with("/link")

    def test_copy_reports_progress_and_cancellation(self):
        backend = self.backend()
        target = io.BytesIO()
        reports = []
        backend.copy(io.BytesIO(b"data"), target, 4, lambda *args: reports.append(args))
        self.assertEqual(target.getvalue(), b"data")
        self.assertEqual(reports[-1], (4, 4))
        backend.close()
        with self.assertRaises(Cancelled):
            backend.copy(io.BytesIO(b"data"), io.BytesIO(), 4, Mock())


class SFTPServiceTests(unittest.TestCase):
    def setUp(self):
        self.queue = Queue()
        self.backend = Mock()
        self.service = SFTPService(self.backend, lambda *args: self.queue.put(args))

    def drain(self):
        self.service.worker.join(2)
        self.assertFalse(self.service.worker.is_alive())
        while not self.queue.empty():
            callback, *args = self.queue.get_nowait()
            callback(*args)

    def test_serializes_until_completion_delivered(self):
        done = Mock()
        self.service.submit(lambda *_: 42, done, Mock())
        with self.assertRaises(RuntimeError):
            self.service.submit(Mock(), Mock(), Mock())
        self.drain()
        done.assert_called_once_with(42)
        self.assertFalse(self.service.busy)

    def test_close_suppresses_queued_completion_and_progress(self):
        done, progress = Mock(), Mock()
        self.service.submit(lambda backend, report: report(1, 1), done, Mock(), progress)
        self.service.worker.join(2)
        self.service.close()
        self.drain()
        done.assert_not_called()
        progress.assert_not_called()
        self.backend.close.assert_called_once()

    def test_cancel_interrupts_operation_and_prevents_reuse(self):
        started, released = Event(), Event()
        self.backend.close.side_effect = released.set
        failed = Mock()
        def operation(*_args):
            started.set()
            released.wait(2)
        self.service.submit(operation, Mock(), failed)
        self.assertTrue(started.wait(2))
        self.service.cancel()
        self.drain()
        self.assertIsInstance(failed.call_args.args[0], Cancelled)
        with self.assertRaises(RuntimeError):
            self.service.submit(Mock(), Mock(), Mock())


class SFTPIntegrationTests(unittest.TestCase):
    def test_terminal_owner_is_registered_and_cancelled_independently(self):
        from termia.terminal_sessions import TerminalSessionsMixin
        from termia.models import Server
        class Host(TerminalSessionsMixin):
            shutdown_in_progress = False
            t = staticmethod(lambda key: key)
        host = Host()
        host.file_transfer_controllers = set()
        host.session_registry = Mock()
        host.session_registry.contains.return_value = True
        host.window_for_session = Mock(return_value=object())
        session = SimpleNamespace(id="owner")
        server = Server("saved", "Synthetic", "example.test", "test")
        window = Mock(owner_session_id="owner")
        other = Mock(owner_session_id=None)
        host.file_transfer_controllers.add(other)
        with patch("termia.sftp_view.SFTPWindow", return_value=window), patch(
            "termia.terminal_sessions.GLib.idle_add", side_effect=lambda callback: callback()
        ):
            host.on_browse_sftp(Mock(), session, server)
        self.assertIn(window, host.file_transfer_controllers)
        host.cancel_file_transfers("owner", close_dialog=True)
        window.cancel_active_transfer.assert_called_once_with(close_dialog=True)
        other.cancel_active_transfer.assert_not_called()

    def test_closed_session_does_not_open_a_delayed_explorer(self):
        from termia.terminal_sessions import TerminalSessionsMixin
        from termia.models import Server
        class Host(TerminalSessionsMixin):
            shutdown_in_progress = False
        host = Host()
        host.session_registry = Mock()
        host.session_registry.contains.return_value = False
        host.window_for_session = Mock()
        with patch("termia.sftp_view.SFTPWindow") as window, patch(
            "termia.terminal_sessions.GLib.idle_add", side_effect=lambda callback: callback()
        ):
            host.on_browse_sftp(Mock(), SimpleNamespace(id="closed"),
                                Server("saved", "Synthetic", "example.test", "test"))
        window.assert_not_called()
