# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""UI-independent SFTP contracts and serialized, cancellable execution."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, sleep
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


@dataclass(frozen=True)
class TransferProgress:
    name: str
    current: int
    total: int | None
    files_completed: int
    bytes_transferred: int
    bytes_per_second: float = 0.0


class IncompleteTransfer(Exception):
    pass


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
    def upload(self, local: Path, remote: str, progress: TransferReporter) -> None: ...
    def download(self, remote: str, local: Path, progress: TransferReporter) -> None: ...
    def close(self) -> None: ...


class TransferReporter(Protocol):
    """Per-file bytes; finished is emitted only after both files close safely.

    A directory reports total=None without incrementing the completed-file count.
    Discovery is streamed; there is deliberately no pre-scan of the tree.
    """

    def __call__(self, current: int, total: int | None, *,
                 name: str = "", finished: bool = False) -> None: ...


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
        self.close_worker: Thread | None = None
        self.cleanup_failed = False

    @property
    def stopped(self) -> bool:
        """A verified result, not merely a request to cancel. Never joins GTK."""
        return (self.cancelled.is_set() and not self.cleanup_failed
                and not (self.worker and self.worker.is_alive())
                and not (self.close_worker and self.close_worker.is_alive()))

    def submit(self, operation, done, failed, progress=None) -> None:
        if self.closed or self.busy or self.cancelled.is_set():
            raise RuntimeError("SFTP service unavailable")
        self.busy = True
        last_progress = 0.0
        progress_lock = Lock()
        latest = None
        queued = False
        completed_files = completed_bytes = 0
        # Sample at most four times a second, retaining a three-second window.
        # Operation-wide bytes keep the rate continuous across file boundaries.
        samples = deque([(monotonic(), 0)])

        def deliver_progress():
            nonlocal latest, queued
            with progress_lock:
                value, latest = latest, None
                queued = False
            if value is not None and not self.closed and not self.cancelled.is_set():
                progress(value)
            return False

        def report(current, total, *, name="", finished=False):
            nonlocal last_progress, latest, queued, completed_files, completed_bytes
            if self.cancelled.is_set():
                raise Cancelled()
            now = monotonic()
            with progress_lock:
                operation_bytes = completed_bytes + current
                if finished:
                    completed_files += 1
                    completed_bytes = operation_bytes
                while len(samples) > 1 and samples[1][0] <= now - 3:
                    samples.popleft()
                elapsed = now - samples[0][0]
                rate = max(0, operation_bytes - samples[0][1]) / elapsed if elapsed > 0 else 0.0
                if now - samples[-1][0] >= 0.25:
                    samples.append((now, operation_bytes))
                latest = TransferProgress(name, current, total, completed_files, operation_bytes, rate)
                schedule = progress and not queued and now - last_progress >= 0.1
                if schedule:
                    queued = True
                    last_progress = now
            if schedule:
                self.dispatch(deliver_progress)

        def finish(callback, value):
            self.busy = False
            if not self.closed:
                if self.cancelled.is_set():
                    failed(Cancelled())
                else:
                    if progress:
                        deliver_progress()
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
        if self.cancelled.is_set():
            return
        self.cancelled.set()

        def stop_backend():
            failures = 0

            def close_backend():
                nonlocal failures
                while True:
                    try:
                        self.backend.close()
                        return True
                    except Exception:
                        if failures:
                            self.cleanup_failed = True
                            return False
                        failures += 1
                        # One recovery attempt, on this same worker. Repeated
                        # cancel/close requests must not create more closers.
                        sleep(0.05)

            # Retry while setup is running: the first close may precede creation
            # of Paramiko's transport. The last close runs after the worker exits.
            while self.worker is not None and self.worker.is_alive():
                if not close_backend():
                    return
                self.worker.join(0.05)
            close_backend()

        self.close_worker = Thread(target=stop_backend, name="termia-sftp-close", daemon=True)
        self.close_worker.start()

    def close(self) -> None:
        self.closed = True
        self.cancel()
