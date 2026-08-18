# SPDX-FileCopyrightText: 2026 Jordi Pons
# Copyright (C) 2026 Jordi Pons
# This file is distributed under the terms of the GNU General Public License.
from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Vte", "3.91")
from gi.repository import GLib, Vte


@dataclass(frozen=True)
class TerminalProcess:
    """Identity captured for a VTE child and its isolated process group."""

    pid: int
    process_group_id: int | None
    session_id: int | None
    start_time: str | None


def process_start_time(pid: int) -> str | None:
    """Return the Linux process start time, used to reject a reused PID."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    _prefix, separator, fields = stat.rpartition(")")
    if not separator:
        return None
    values = fields.split()
    return values[19] if len(values) > 19 else None


def process_group_and_session(pid: int) -> tuple[int, int] | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    _prefix, separator, fields = stat.rpartition(")")
    if not separator:
        return None
    values = fields.split()
    if len(values) < 4:
        return None
    return int(values[2]), int(values[3])


def process_groups_in_session(session_id: int) -> set[int]:
    groups: set[int] = set()
    try:
        candidates = Path("/proc").iterdir()
    except OSError:
        return groups
    for candidate in candidates:
        if not candidate.name.isdigit():
            continue
        identity = process_group_and_session(int(candidate.name))
        if identity is not None and identity[1] == session_id:
            groups.add(identity[0])
    return groups


def capture_terminal_process(pid: int) -> TerminalProcess:
    try:
        process_group_id = os.getpgid(pid)
    except OSError:
        process_group_id = None
    if process_group_id == os.getpgrp():
        process_group_id = None
    try:
        session_id = os.getsid(pid)
    except OSError:
        session_id = None
    if session_id == os.getsid(0):
        session_id = None
    return TerminalProcess(pid, process_group_id, session_id, process_start_time(pid))


def signal_terminal_process(process: TerminalProcess, signum: int) -> bool:
    """Signal every process group in an isolated VTE session when available."""
    if process.session_id is not None:
        groups = process_groups_in_session(process.session_id)
        if groups:
            signalled = False
            for process_group_id in groups:
                if process_group_id == os.getpgrp():
                    continue
                try:
                    os.killpg(process_group_id, signum)
                except (ProcessLookupError, PermissionError, OSError):
                    continue
                signalled = True
            if signalled:
                return True
    current_start_time = process_start_time(process.pid)
    if process.start_time is not None and current_start_time != process.start_time:
        return False
    try:
        if process.process_group_id is not None and os.getpgid(process.pid) == process.process_group_id:
            os.killpg(process.process_group_id, signum)
        else:
            os.kill(process.pid, signum)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def terminal_process_is_active(process: TerminalProcess) -> bool:
    """Return whether the captured VTE process or any session group still exists."""
    if process.session_id is not None and process_groups_in_session(process.session_id):
        return True
    current_start_time = process_start_time(process.pid)
    if process.start_time is not None:
        return current_start_time == process.start_time
    return current_start_time is not None


def spawn_terminal_process(
    terminal: Vte.Terminal,
    working_directory: str | None,
    command: list[str],
    environment: list[str],
) -> TerminalProcess:
    _ok, child_pid = terminal.spawn_sync(
        Vte.PtyFlags.DEFAULT,
        working_directory,
        command,
        environment,
        GLib.SpawnFlags.DEFAULT,
        None,
        None,
        None,
    )
    return capture_terminal_process(child_pid)
