# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Asynchronous update lifecycle with an injected UI dispatcher."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import tempfile
from threading import Event, Lock, Thread
from typing import Callable

from .update_installers import Installation, detect_installation, update_lock
from .update_service import Release, ReleaseClient, UpdateError, check_cancel, select_release


@dataclass(frozen=True)
class CheckResult:
    release: Release | None
    installation: Installation


class UpdateController:
    """One job at a time; all widget callbacks are dispatched, never run here.

    Close cancels preparation and suppresses queued callbacks. Applying is an
    irreversible phase: the non-daemon worker retains its lock and temporary
    package until the package manager exits, even if the UI is destroyed.
    """

    def __init__(self, current: str, dispatch: Callable, notify: Callable,
                 client=None, detect=detect_installation):
        self.current, self.dispatch, self.notify = current, dispatch, notify
        self.client = client or ReleaseClient()
        self.detect = detect
        self.cancel = Event()
        self.closed = False
        self.busy = False
        self.applying = False
        self.guard = Lock()
        self.thread: Thread | None = None

    def emit(self, state: str, payload=None) -> None:
        logging.getLogger("termia").debug("event=update.%s", state)

        def deliver():
            if not self.closed:
                self.notify(state, payload)
            return False

        self.dispatch(deliver)

    def start(self, operation: Callable) -> bool:
        with self.guard:
            if self.busy or self.closed:
                return False
            self.busy = True
            self.cancel.clear()

        def work():
            state, result = "done", None
            try:
                with update_lock():
                    result = operation()
            except UpdateError as error:
                state, result = "error", str(error)
            except Exception:
                state, result = "error", "update_failed"
            finally:
                with self.guard:
                    self.busy = self.applying = False
            self.emit(state, result)

        self.thread = Thread(target=work, name="termia-update", daemon=False)
        self.thread.start()
        return True

    def check(self) -> bool:
        def operation():
            items = self.client.releases(self.cancel)
            installation = self.detect(self.current, self.client, self.cancel)
            check_cancel(self.cancel)
            return CheckResult(select_release(items, self.current), installation)

        return self.start(operation)

    def install(self, result: CheckResult) -> bool:
        def operation():
            adapter, release = result.installation.adapter, result.release
            if adapter is None or release is None or result.installation.reason:
                raise UpdateError("update_unknown_installation")
            with tempfile.TemporaryDirectory(prefix="termia-update-") as directory:
                prepared = adapter.prepare(release, Path(directory), self.cancel)
                with self.guard:
                    check_cancel(self.cancel)
                    self.applying = True
                self.emit("applying")
                adapter.apply(prepared, release)
            return None

        return self.start(operation)

    def stop(self) -> bool:
        with self.guard:
            if self.applying:
                return False
            self.cancel.set()
            return True

    def close(self) -> None:
        with self.guard:
            self.closed = True
            if not self.applying:
                self.cancel.set()
