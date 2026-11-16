# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only Linux resource snapshots. No GTK, networking or process signals."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event


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


@dataclass(frozen=True)
class ProcessReading:
    pid: int
    parent: int
    start_time: str
    name: str
    ticks: int
    rss: int
    threads: int
    state: str


@dataclass(frozen=True)
class ProcessSample:
    reading: ProcessReading
    cpu: float | None
    descriptors: int | None
    kind: str
    possible_orphan: bool


@dataclass(frozen=True)
class ResourceSnapshot:
    timestamp: float
    main: ProcessSample | None
    children: tuple[ProcessSample, ...]
    context: DiagnosticContext
    incomplete: bool


def parse_stat(text: str, page_size: int) -> ProcessReading:
    prefix, separator, remainder = text.rpartition(")")
    pid, opening, name = prefix.partition("(")
    values = remainder.split()
    if not separator or not opening or len(values) < 22:
        raise ValueError("Incomplete process stat")
    return ProcessReading(int(pid.strip()), int(values[1]), values[19],
                          "".join(c if c.isprintable() else "?" for c in name)[:64],
                          int(values[11]) + int(values[12]), max(0, int(values[21])) * page_size,
                          int(values[17]), values[0])


class LocalProcessSampler:
    def __init__(self, pid=None, proc=Path("/proc"), clock=time.monotonic):
        self.pid = os.getpid() if pid is None else pid
        self.proc = Path(proc)
        self.clock = clock
        self.page_size = os.sysconf("SC_PAGE_SIZE")
        self.ticks_per_second = os.sysconf("SC_CLK_TCK")
        self._previous: dict[tuple[int, str], int] = {}
        self._known: set[tuple[int, str]] = set()
        self._sampled_at: float | None = None

    def sample(self, context: DiagnosticContext, cancelled: Event) -> ResourceSnapshot:
        now = self.clock()
        records: dict[int, ProcessReading] = {}
        incomplete = False
        try:
            paths = tuple(self.proc.iterdir())
        except OSError:
            paths = ()
            incomplete = True
        for path in paths:
            if cancelled.is_set():
                return ResourceSnapshot(now, None, (), context, True)
            if not path.name.isdecimal():
                continue
            try:
                reading = parse_stat((path / "stat").read_text(encoding="utf-8"), self.page_size)
                if reading.pid == int(path.name):
                    records[reading.pid] = reading
            except FileNotFoundError:
                continue  # Processes can exit during a sample.
            except (OSError, ValueError, UnicodeError):
                incomplete = True
        managed = {(p.pid, p.start_time): p for p in context.processes}
        children_by_parent: dict[int, list[int]] = {}
        for record in records.values():
            children_by_parent.setdefault(record.parent, []).append(record.pid)

        def descendants(roots):
            found = set(roots)
            pending = list(found)
            while pending:
                for child in children_by_parent.get(pending.pop(), ()):
                    if child not in found:
                        found.add(child)
                        pending.append(child)
            return found

        direct = descendants({self.pid}) if self.pid in records else set()
        retained = {pid for pid, start in self._known | set(managed)
                    if pid in records and records[pid].start_time == start}
        owned = descendants(direct | retained)
        elapsed = now - self._sampled_at if self._sampled_at is not None else 0
        samples = {}
        for pid in sorted(owned):
            if cancelled.is_set():
                return ResourceSnapshot(now, None, (), context, True)
            record = records.get(pid)
            if record is None:
                continue
            identity = (pid, record.start_time)
            previous = self._previous.get(identity)
            cpu = (max(0, record.ticks - previous) / self.ticks_per_second / elapsed * 100
                   if elapsed > 0 and previous is not None else None)
            try:
                descriptors = sum(1 for _ in (self.proc / str(pid) / "fd").iterdir())
                # Do not combine counters belonging to a reused PID.
                checked = parse_stat((self.proc / str(pid) / "stat").read_text(encoding="utf-8"), self.page_size)
                if checked.start_time != record.start_time:
                    incomplete = True
                    continue
            except (OSError, ValueError, UnicodeError):
                descriptors = None
                incomplete = True
            reference = managed.get(identity)
            orphan = pid != self.pid and (pid not in direct or bool(reference and reference.possible_orphan))
            samples[pid] = ProcessSample(record, cpu, descriptors,
                                         reference.kind if reference else "child", orphan)
        self._previous = {(p.reading.pid, p.reading.start_time): p.reading.ticks for p in samples.values()}
        self._known = set(self._previous) - {(self.pid, records[self.pid].start_time)} if self.pid in records else set()
        self._sampled_at = now
        main = samples.pop(self.pid, None)
        return ResourceSnapshot(now, main, tuple(samples.values()), context, incomplete or main is None)
