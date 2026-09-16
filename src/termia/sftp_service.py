# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""UI-independent SFTP contracts and serialized, cancellable execution."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import Protocol, Any
import posixpath


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    user: str
    identity: str = ""
    password: str = field(default="", repr=False)


@dataclass(frozen=True)
class RemoteEntry:
    name: str
    size: int
    modified: int
    mode: int


class Cancelled(Exception):
    pass


class AuthenticationRequired(Exception):
    pass


class HostKeyChanged(Exception):
    pass


class UnknownHost(Exception):
    def __init__(self, hostname: str, key_type: str, key_data: str, fingerprint: str):
        super().__init__("unknown host key")
        self.hostname = hostname
        self.key_type = key_type
        self.key_data = key_data
        self.fingerprint = fingerprint


def child_path(parent: str, name: str) -> str:
    """Never trust names returned by a server as local or remote paths."""
    if not name or name in (".", "..") or "/" in name or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError("invalid filename")
    return posixpath.join(parent, name)


class SFTPBackend(Protocol):
    def connect(self) -> str: ...
    def list_directory(self, path: str) -> list[RemoteEntry]: ...
    def mkdir(self, path: str) -> None: ...
    def rename(self, source: str, target: str) -> None: ...
    def delete(self, path: str) -> None: ...
    def upload(self, local: Path, remote: str, progress: Callable[[int, int], None]) -> None: ...
    def download(self, remote: str, local: Path, progress: Callable[[int, int], None]) -> None: ...
    def close(self) -> None: ...


class SFTPService:
    """One operation at a time; dispatch is supplied by the UI/event loop.

    Cancellation closes the transport and invalidates the current connection.
    A fresh backend is required for reconnect. Late callbacks are suppressed
    on disposal, including callbacks already queued in the UI loop.
    """

    def __init__(self, backend: SFTPBackend, dispatch: Callable[..., Any]):
        self.backend = backend
        self.dispatch = dispatch
        self.busy = False
        self.closed = False
        self.cancelled = Event()
        self.worker: Thread | None = None

    def submit(self, operation, done, failed, progress=None) -> None:
        if self.closed or self.busy or self.cancelled.is_set():
            raise RuntimeError("SFTP service unavailable")
        self.busy = True
        last_progress = 0.0

        def deliver(callback, *args):
            if not self.closed:
                callback(*args)
            return False

        def report(current, total):
            nonlocal last_progress
            if self.cancelled.is_set():
                raise Cancelled()
            now = monotonic()
            if progress and (now - last_progress >= 0.1 or current == total):
                last_progress = now
                self.dispatch(deliver, progress, current, total)

        def finish(callback, value):
            self.busy = False
            if not self.closed:
                callback(value)
            return False

        def run():
            try:
                result = operation(self.backend, report)
                if self.cancelled.is_set():
                    raise Cancelled()
            except Exception as error:
                if self.cancelled.is_set():
                    error = Cancelled()
                self.dispatch(finish, failed, error)
            else:
                self.dispatch(finish, done, result)

        self.worker = Thread(target=run, name="termia-sftp", daemon=True)
        self.worker.start()

    def cancel(self) -> None:
        self.cancelled.set()
        self.backend.close()

    def close(self) -> None:
        self.closed = True
        self.cancel()
