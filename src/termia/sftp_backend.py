# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Paramiko adapter. All calls except close run in the SFTP worker."""
from __future__ import annotations

import base64
from dataclasses import replace
import hashlib
import logging
import os
from pathlib import Path
import stat
from threading import Event, Lock

import paramiko

from .sftp_service import (
    AuthenticationRequired, Cancelled, Endpoint, HostKeyChanged, RemoteEntry,
    UnknownHost, child_path,
)


class RequireConfirmation(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        digest = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
        raise UnknownHost(hostname, key.get_name(), key.get_base64(), "SHA256:" + digest)


class ParamikoBackend:
    def __init__(self, endpoint: Endpoint, *, known_hosts=None, client_factory=paramiko.SSHClient):
        self.endpoint = endpoint
        self.known_hosts = known_hosts if known_hosts is not None else (
            Path("/etc/ssh/ssh_known_hosts"), Path("/etc/ssh/ssh_known_hosts2"),
            Path.home() / ".ssh/known_hosts", Path.home() / ".ssh/known_hosts2",
        )
        self.client_factory = client_factory
        self.client = None
        self.sftp = None
        self.stopped = Event()
        self.lock = Lock()

    def check(self):
        if self.stopped.is_set():
            raise Cancelled()

    def connect(self):
        self.check()
        client = self.client_factory()
        with self.lock:
            self.check()
            self.client = client
        # Paramiko debug output contains identities and paths: never propagate it.
        logger = logging.getLogger("termia.sftp.transport")
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        logger.propagate = False
        logger.setLevel(logging.CRITICAL)
        client.set_log_channel(logger.name)
        try:
            for path in self.known_hosts:
                if path.exists():
                    client.load_host_keys(str(path))
            endpoint = self.endpoint
            keys = client.get_host_keys()
            name = endpoint.host if endpoint.port == 22 else f"[{endpoint.host}]:{endpoint.port}"
            # Mirror Termia/OpenSSH's endpoint-first, bare-host fallback.
            if endpoint.port != 22 and keys.lookup(name) is None:
                fallback = keys.lookup(endpoint.host)
                if fallback:
                    for kind, key in fallback.items():
                        keys.add(name, kind, key)
            client.set_missing_host_key_policy(RequireConfirmation())
            client.connect(
                hostname=endpoint.host, port=endpoint.port, username=endpoint.user,
                password=endpoint.password or None,
                key_filename=str(Path(endpoint.identity).expanduser()) if endpoint.identity else None,
                allow_agent=not bool(endpoint.password),
                look_for_keys=not bool(endpoint.password),
                timeout=10, banner_timeout=10, auth_timeout=10,
            )
            self.check()
            self.sftp = client.open_sftp()
            self.sftp.get_channel().settimeout(15)
            self.check()
            return self.sftp.normalize(".")
        except (paramiko.AuthenticationException, paramiko.PasswordRequiredException):
            client.close()
            raise AuthenticationRequired() from None
        except paramiko.BadHostKeyException:
            client.close()
            raise HostKeyChanged() from None
        except Exception:
            client.close()
            raise

    def list_directory(self, path):
        self.check()
        entries = []
        for entry in self.sftp.listdir_attr(path):
            self.check()
            child_path(path, entry.filename)
            entries.append(RemoteEntry(entry.filename, entry.st_size or 0,
                                       entry.st_mtime or 0, entry.st_mode or 0))
        return sorted(entries, key=lambda entry: (not stat.S_ISDIR(entry.mode), entry.name.casefold()))

    def mkdir(self, path):
        self.check()
        self.sftp.mkdir(path)

    def rename(self, source, target):
        self.check()
        # Standard SFTP rename refuses an existing destination.
        self.sftp.rename(source, target)

    def delete(self, path):
        self.check()
        if stat.S_ISDIR(self.sftp.lstat(path).st_mode):
            self.sftp.rmdir(path)  # Intentionally only empty directories.
        else:
            self.sftp.remove(path)

    def upload(self, local, remote, progress, _depth=0):
        self.check()
        if _depth > 64:
            raise ValueError("directory nesting limit")
        mode = local.lstat().st_mode
        if stat.S_ISDIR(mode):
            self.sftp.mkdir(remote)  # Refuse existing directories; never merge silently.
            for item in local.iterdir():
                self.upload(item, child_path(remote, item.name), progress, _depth + 1)
        elif stat.S_ISREG(mode):
            # Exclusive creation protects existing remote data from overwrites.
            with local.open("rb") as source, self.sftp.open(remote, "wx") as target:
                self.copy(source, target, local.stat().st_size, progress)
        else:
            raise ValueError("unsupported file type")

    def download(self, remote, local, progress, _depth=0):
        self.check()
        if _depth > 64:
            raise ValueError("directory nesting limit")
        attrs = self.sftp.lstat(remote)
        if stat.S_ISDIR(attrs.st_mode):
            local.mkdir(mode=0o700)  # Reject existing paths, including symlinks.
            for entry in self.list_directory(remote):
                path = child_path(remote, entry.name)
                self.download(path, local / entry.name, progress, _depth + 1)
        elif stat.S_ISREG(attrs.st_mode):
            # Exclusive creation prevents following a pre-existing local symlink.
            fd = os.open(local, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as target, self.sftp.open(remote, "rb") as source:
                    self.copy(source, target, attrs.st_size or 0, progress)
            except Exception:
                local.unlink(missing_ok=True)
                raise
        else:
            raise ValueError("unsupported file type")

    def copy(self, source, target, total, progress):
        transferred = 0
        progress(0, total)
        while True:
            self.check()
            data = source.read(256 * 1024)
            if not data:
                break
            target.write(data)
            transferred += len(data)
            progress(transferred, total)
        self.check()

    def close(self):
        self.stopped.set()
        self.endpoint = replace(self.endpoint, password="")
        with self.lock:
            client = self.client
        if client:
            client.close()
