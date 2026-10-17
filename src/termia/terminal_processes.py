# SPDX-FileCopyrightText: 2026 Jordi Pons
# Copyright (C) 2026 Jordi Pons
# This file is distributed under the terms of the GNU General Public License.
from __future__ import annotations

import os
import signal
from dataclasses import dataclass, replace
from pathlib import Path

import gi

gi.require_version("Vte", "3.91")
from gi.repository import GLib, Vte


@dataclass(frozen=True)
class SessionProcessIdentity:
    pid: int
    process_group_id: int
    start_time: str


@dataclass(frozen=True)
class TerminalProcess:
    """Identity captured for a VTE child and its isolated process group."""

    pid: int
    process_group_id: int | None
    session_id: int | None
    start_time: str | None
    session_members: tuple[SessionProcessIdentity, ...] = ()
    session_unverified: bool = False


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


def process_session_members(session_id: int) -> tuple[SessionProcessIdentity, ...]:
    members: list[SessionProcessIdentity] = []
    try:
        candidates = Path("/proc").iterdir()
    except (OSError, UnicodeError):
        return ()
    for candidate in candidates:
        if not candidate.name.isdigit():
            continue
        try:
            stat = (candidate / "stat").read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        _prefix, separator, fields = stat.rpartition(")")
        if not separator:
            continue
        values = fields.split()
        if len(values) <= 19:
            continue
        try:
            process_group_id = int(values[2])
            current_session_id = int(values[3])
        except ValueError:
            continue
        if current_session_id == session_id:
            members.append(
                SessionProcessIdentity(
                    pid=int(candidate.name),
                    process_group_id=process_group_id,
                    start_time=values[19],
                )
            )
    return tuple(members)


def snapshot_terminal_process(process: TerminalProcess) -> TerminalProcess:
    """Capture process identities that prove ownership of its isolated session."""
    if process.session_id is None or process.session_members or process.session_unverified:
        return process
    if process.start_time is None or process_start_time(process.pid) != process.start_time:
        return replace(
            process,
            session_unverified=bool(process_session_members(process.session_id)),
        )
    members = process_session_members(process.session_id)
    if (
        process_start_time(process.pid) != process.start_time
        or not any(
            member.pid == process.pid and member.start_time == process.start_time
            for member in members
        )
    ):
        return replace(process, session_unverified=bool(members))
    return replace(process, session_members=members)


def _verified_session_groups(process: TerminalProcess) -> set[int]:
    if process.session_id is None or process.session_unverified:
        return set()
    members = process.session_members
    if not members:
        members = snapshot_terminal_process(process).session_members
    if not members:
        return set()
    groups: set[int] = set()
    for member in members:
        if process_start_time(member.pid) != member.start_time:
            continue
        try:
            process_group_id = os.getpgid(member.pid)
            session_id = os.getsid(member.pid)
        except OSError:
            continue
        if process_group_id == member.process_group_id and session_id == process.session_id:
            groups.add(member.process_group_id)
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
    if process.session_unverified:
        return False
    if process.session_id is not None:
        groups = _verified_session_groups(process)
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
    if process.start_time is None or current_start_time != process.start_time:
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
    if process.session_unverified:
        # Uncertainty forbids signalling; it does not prove permanent activity.
        return process.session_id is not None and bool(process_session_members(process.session_id))
    if process.session_id is not None and _verified_session_groups(process):
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
