"""Real SFTP packets over a local socket pair; no SSH host or credentials."""
import os
from pathlib import Path
import socket
import tempfile
import unittest

import paramiko

from termia.sftp_backend import ParamikoBackend
from termia.sftp_service import Endpoint


class Auth(paramiko.ServerInterface):
    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL

    def check_channel_request(self, kind, channel_id):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED


class Files(paramiko.SFTPServerInterface):
    def __init__(self, server, *, root):
        super().__init__(server)
        self.root = Path(root)

    def path(self, path):
        target = (self.root / path.lstrip("/")).resolve()
        if not target.is_relative_to(self.root):
            raise OSError("outside test directory")
        return target

    def list_folder(self, path):
        entries = []
        for item in self.path(path).iterdir():
            entry = paramiko.SFTPAttributes.from_stat(item.lstat())
            entry.filename = item.name
            entries.append(entry)
        return entries

    def lstat(self, path):
        try:
            return paramiko.SFTPAttributes.from_stat(self.path(path).lstat())
        except OSError as error:
            return paramiko.SFTPServer.convert_errno(error.errno)

    stat = lstat

    def open(self, path, flags, attr):
        try:
            fd = os.open(self.path(path), flags, 0o600)
            stream = os.fdopen(fd, "wb" if flags & os.O_WRONLY else "rb")
            handle = paramiko.SFTPHandle(flags)
            handle.writefile = stream
            handle.readfile = stream
            return handle
        except OSError as error:
            return paramiko.SFTPServer.convert_errno(error.errno)

    def mkdir(self, path, attr):
        try:
            self.path(path).mkdir()
            return paramiko.SFTP_OK
        except OSError as error:
            return paramiko.SFTPServer.convert_errno(error.errno)


class SFTPProtocolTests(unittest.TestCase):
    def test_recursive_roundtrip_and_exclusive_remote_creation(self):
        with tempfile.TemporaryDirectory() as remote, tempfile.TemporaryDirectory() as local:
            first, second = socket.socketpair()
            server = paramiko.Transport(first)
            client = paramiko.Transport(second)
            self.addCleanup(server.close)
            self.addCleanup(client.close)
            server.add_server_key(paramiko.RSAKey.generate(1024))
            server.set_subsystem_handler("sftp", paramiko.SFTPServer, Files, root=remote)
            from threading import Event
            ready = Event()
            server.start_server(event=ready, server=Auth())
            client.connect(username="synthetic", password="synthetic")
            backend = ParamikoBackend(Endpoint("unused.example", 22, "synthetic"))
            backend.sftp = paramiko.SFTPClient.from_transport(client)
            self.addCleanup(backend.sftp.close)
            source = Path(local) / "source"
            source.mkdir()
            (source / "nested").mkdir()
            payload = b"test data\x00" * 40000
            (source / "nested" / "spaces ; ' name").write_bytes(payload)
            progress = []
            backend.upload(source, "/upload", lambda *args: progress.append(args))
            backend.download("/upload", Path(local) / "result", lambda *_: None)
            self.assertEqual((Path(local) / "result/nested/spaces ; ' name").read_bytes(), payload)
            self.assertEqual(progress[-1], (len(payload), len(payload)))
            with self.assertRaises(OSError):
                backend.upload(source / "nested" / "spaces ; ' name", "/upload/nested/spaces ; ' name", lambda *_: None)
            self.assertEqual((Path(remote) / "upload/nested/spaces ; ' name").read_bytes(), payload)
