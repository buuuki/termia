# SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from termia.diagnostics import (
    DiagnosticContext,
    LocalProcessSampler,
    ManagedProcess,
    parse_stat,
)


def stat(pid, parent, *, start="100", ticks=0, rss=10, name="synthetic", threads=2):
    fields = ["0"] * 22
    fields[0], fields[1], fields[11], fields[17], fields[19], fields[21] = (
        "S", str(parent), str(ticks), str(threads), start, str(rss))
    return f"{pid} ({name}) " + " ".join(fields)


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.proc = Path(self.temp.name)
        self.now = 10.0
        self.sampler = LocalProcessSampler(10, self.proc, lambda: self.now)
        self.sampler.ticks_per_second = 100
        self.cancelled = Event()
        self.write(10, 1)

    def write(self, pid, parent, **kwargs):
        directory = self.proc / str(pid)
        directory.mkdir(exist_ok=True)
        (directory / "stat").write_text(stat(pid, parent, **kwargs))
        (directory / "fd").mkdir(exist_ok=True)
        (directory / "fd" / "0").touch()

    def sample(self, context=None):
        return self.sampler.sample(context or DiagnosticContext(), self.cancelled)

    def test_descendants_metrics_and_cpu_without_double_counting(self):
        self.write(11, 10, name="ssh", ticks=20)
        self.write(12, 11, name="bash", ticks=30)
        self.write(13, 1, name="unrelated")
        first = self.sample(DiagnosticContext(processes=(ManagedProcess(11, "100", "ssh"),)))
        self.assertIsNone(first.main.cpu)
        self.assertEqual([p.reading.pid for p in first.children], [11, 12])
        self.assertEqual(first.children[0].kind, "ssh")
        self.assertEqual(first.main.descriptors, 1)
        self.assertEqual(first.main.reading.rss, 10 * self.sampler.page_size)
        self.assertFalse(first.incomplete)
        self.now += 2
        self.write(10, 1, ticks=100)
        self.write(11, 10, ticks=60)
        self.write(12, 11, ticks=50)
        second = self.sample()
        self.assertEqual(second.main.cpu, 50)
        self.assertEqual(sum(p.cpu for p in second.children), 30)

    def test_reparented_children_are_retained_but_reused_pids_are_not(self):
        self.write(11, 10)
        self.sample()
        self.write(11, 1)
        orphan = self.sample().children[0]
        self.assertTrue(orphan.possible_orphan)
        self.write(11, 1, start="101")
        self.assertEqual(self.sample().children, ())

    def test_only_matching_captured_orphans_are_included(self):
        self.write(11, 1, start="new")
        self.write(12, 1)
        result = self.sample(DiagnosticContext(processes=(
            ManagedProcess(11, "old", possible_orphan=True),
            ManagedProcess(12, "100", possible_orphan=True))))
        self.assertEqual([p.reading.pid for p in result.children], [12])
        self.assertTrue(result.children[0].possible_orphan)

    def test_unavailable_proc_and_cancelled_sampling_do_not_invent_metrics(self):
        missing = LocalProcessSampler(10, self.proc / "missing").sample(DiagnosticContext(), self.cancelled)
        self.assertIsNone(missing.main)
        self.assertTrue(missing.incomplete)
        self.cancelled.set()
        self.assertIsNone(self.sample().main)

    def test_unreadable_descriptors_are_unknown_not_zero(self):
        original = Path.iterdir
        def denied(path):
            if path.name == "fd":
                raise PermissionError("synthetic")
            return original(path)
        with patch.object(Path, "iterdir", denied):
            result = self.sample()
        self.assertIsNone(result.main.descriptors)
        self.assertTrue(result.incomplete)

    def test_stat_parsing_handles_parentheses_and_control_characters(self):
        record = parse_stat(stat(10, 1, name="a)b\nc"), 4096)
        self.assertEqual(record.name, "a)b?c")
        self.assertEqual(record.parent, 1)
        with self.assertRaises(ValueError):
            parse_stat("invalid", 4096)
