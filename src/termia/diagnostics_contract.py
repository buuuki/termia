# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedProcess:
    pid: int
    start_time: str
    kind: str = "child"
    possible_orphan: bool = False


@dataclass(frozen=True)
class DiagnosticContext:
    sessions: int = 0
    terminals: int = 0
    ssh_clients: int = 0
    local_terminals: int = 0
    processes: tuple[ManagedProcess, ...] = ()
