# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Asynchronous update lifecycle with an injected UI dispatcher."""
from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread

from .update_dependencies import DependencyPlan
from .update_installers import Installation, detect_installation, update_lock
from .update_output import MAX_LOG_CHARS
from .update_service import (
    Release,
    ReleaseClient,
    UpdateError,
    check_cancel,
    select_release,
)


@dataclass(frozen=True)
class CheckResult:
    release: Release | None
    installation: Installation


@dataclass(frozen=True)
class PreparedUpdate:
    result: CheckResult
    artifact: object
    dependencies: DependencyPlan


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
        self.prepared: PreparedUpdate | None = None
        self.directory: tempfile.TemporaryDirectory | None = None
        self.pending_output = ""
        self.output_queued = False

    def report_output(self, text: str) -> None:
        with self.guard:
            if self.closed:
                return
            self.pending_output = (self.pending_output + text)[-MAX_LOG_CHARS:]
            if self.output_queued:
                return
            self.output_queued = True

        def deliver():
            with self.guard:
                text, self.pending_output = self.pending_output, ""
                self.output_queued = False
                closed = self.closed
            if not closed:
                self.notify("output", text)
            return False

        self.dispatch(deliver)

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
                    if not self.applying:
                        check_cancel(self.cancel)
            except UpdateError as error:
                state, result = "error", str(error)
            except Exception:
                state, result = "error", "update_failed"
            finally:
                with self.guard:
                    self.busy = self.applying = False
            if self.closed or self.cancel.is_set():
                self.discard_prepared()
            self.emit(state, result)

        self.thread = Thread(target=work, name="termia-update", daemon=False)
        self.thread.start()
        return True

    def check(self) -> bool:
        def operation():
            self.discard_prepared()
            installation = self.detect(self.current, self.client, self.cancel)
            self.emit("installation", installation)
            items = self.client.releases(self.cancel)
            check_cancel(self.cancel)
            return CheckResult(select_release(items, self.current), installation)

        return self.start(operation)

    def discard_prepared(self) -> None:
        self.prepared = None
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None

    def prepare_update(self, result: CheckResult) -> bool:
        def operation():
            self.discard_prepared()
            adapter, release = result.installation.adapter, result.release
            if adapter is None or release is None or result.installation.reason:
                raise UpdateError("update_unknown_installation")
            self.directory = tempfile.TemporaryDirectory(prefix="termia-update-")
            try:
                adapter.set_output(self.report_output)
                self.emit("phase", "update_log_preparing")
                artifact = adapter.prepare(release, Path(self.directory.name), self.cancel)
                # Revalidate downloaded .deb bytes before presenting their requirements.
                if adapter.kind == "update_debian":
                    adapter.verify(artifact, release)
                plan = adapter.dependencies(artifact, self.cancel)
                check_cancel(self.cancel)
                prepared = PreparedUpdate(result, artifact, plan)
                self.prepared = prepared
                return prepared
            except Exception:
                self.discard_prepared()
                raise
        return self.start(operation)

    def install(self, prepared: PreparedUpdate, *, assisted: bool = False) -> bool:
        def operation():
            if prepared is not self.prepared:
                raise UpdateError("update_plan_expired")
            result = prepared.result
            adapter, release = result.installation.adapter, result.release
            if adapter is None or release is None:
                raise UpdateError("update_unknown_installation")
            if adapter.kind == "update_debian":
                adapter.verify(prepared.artifact, release)
            plan = adapter.dependencies(prepared.artifact, self.cancel)
            # Never install packages added to the plan after the user's confirmation.
            if plan.required != prepared.dependencies.required or not set(plan.packages) <= set(prepared.dependencies.packages):
                raise UpdateError("update_plan_expired")
            if plan.missing and not assisted:
                refreshed = PreparedUpdate(result, prepared.artifact, plan)
                self.prepared = refreshed
                return refreshed
            if plan.missing and not plan.assisted_available:
                raise UpdateError("update_installer_missing")
            with self.guard:
                check_cancel(self.cancel)
                self.applying = True
            self.emit("applying")
            if plan.missing and adapter.kind == "update_source":
                self.emit("phase", "update_log_dependencies")
                adapter.install_dependencies(plan)
                plan = adapter.dependencies(prepared.artifact, Event())
                if plan.missing:
                    raise UpdateError("update_dependencies_not_ready")
            self.emit("phase", "update_log_applying")
            adapter.apply(prepared.artifact, release)
            try:
                # Source verification is done before apply, while HEAD is still old.
                # Debian requirements must also pass after the APT transaction.
                if adapter.kind == "update_debian":
                    self.emit("phase", "update_log_verifying")
                    adapter.verify_installed()
                    remaining = adapter.dependencies(prepared.artifact, Event())
                    if remaining.missing:
                        raise UpdateError("update_verification_failed_after_apply")
            except UpdateError:
                raise UpdateError("update_verification_failed_after_apply") from None
            self.discard_prepared()
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
            idle = not self.busy
        if idle:
            self.discard_prepared()
