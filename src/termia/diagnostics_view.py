# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional, bounded resource monitoring owned by one independent window."""
from __future__ import annotations

import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event
from weakref import ref

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import GLib, Gtk, Pango

from .diagnostics import LocalProcessSampler
from .dialog_actions import add_dialog_action_button, configure_dialog_content
from .dialog_window import DialogWindow

logger = logging.getLogger(__name__)


def memory_text(value):
    return "—" if value is None else f"{value / 1048576:.1f} MiB"


def cpu_text(value):
    return "—" if value is None else f"{value:.1f}%"


class DiagnosticsWindow(DialogWindow):
    def __init__(self, application, context, translate, *, sampler=None):
        super().__init__(application=application, title=translate("diagnostics"), modal=False)
        self.t = translate
        self.context = context
        self.sampler = sampler or LocalProcessSampler()
        self.closed = False
        self.cancelled = Event()
        self.history = deque(maxlen=60)
        self._future = None
        self._timer = None
        self._poll = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="termia-diagnostics")
        self.set_default_size(760, 640)
        header = Gtk.HeaderBar(show_title_buttons=True)
        header.set_decoration_layout(":minimize,maximize,close")
        self.set_titlebar(header)
        self.add_css_class("termia-diagnostics")
        content = configure_dialog_content(self.get_content_area(), spacing=12)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.set_margin_end(12)
        scroller.set_child(body)
        content.append(scroller)
        body.append(Gtk.Label(label=self.t("diagnostics_intro"), wrap=True, xalign=0))
        self.status = Gtk.Label(label=self.t("diagnostics_sampling"), wrap=True, xalign=0)
        body.append(self.status)
        self.sessions = Gtk.Label(wrap=True, xalign=0, selectable=True)
        body.append(self.sessions)
        self.values = {}
        for group in ("main", "children"):
            title = Gtk.Label(label=self.t("diagnostics_" + group), xalign=0)
            title.add_css_class("heading")
            body.append(title)
            grid = Gtk.Grid(column_spacing=16, row_spacing=6, halign=Gtk.Align.START)
            for row, metric in enumerate(("cpu", "memory", "threads", "descriptors", "processes")):
                label = Gtk.Label(label=self.t("diagnostics_" + metric), xalign=0)
                value = Gtk.Label(label="—", xalign=0, selectable=True)
                attributes = Pango.AttrList()
                attributes.insert(Pango.attr_scale_new(1.35))
                attributes.insert(Pango.attr_weight_new(Pango.Weight.SEMIBOLD))
                value.set_attributes(attributes)
                grid.attach(label, 0, row, 1, 1)
                grid.attach(value, 1, row, 1, 1)
                self.values[group, metric] = value
            body.append(grid)
        self.orphans = Gtk.Label(wrap=True, xalign=0)
        body.append(self.orphans)
        self.process_expander, self.process_view = self._details(body, "diagnostics_process_list", expanded=True)
        self.history_expander, self.history_view = self._details(body, "diagnostics_history")
        self.history_expander.connect("notify::expanded", self._history_toggled)
        note = Gtk.Label(label=self.t("diagnostics_measurement_note"), wrap=True, xalign=0)
        note.add_css_class("dim-label")
        body.append(note)
        add_dialog_action_button(self, self.t("close"), Gtk.ResponseType.CLOSE)
        self.connect("response", lambda window, _response: window.destroy())
        self.connect("destroy", lambda window: window.stop())
        self.connect("unrealize", lambda window: window.stop())
        self._timer = GLib.timeout_add_seconds(5, self._sample)
        self._sample()

    def _details(self, parent, key, expanded=False):
        expander = Gtk.Expander(label=self.t(key), expanded=expanded)
        view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        view.update_property([Gtk.AccessibleProperty.LABEL], [self.t(key)])
        scroller = Gtk.ScrolledWindow(min_content_height=120, max_content_height=220,
                                     propagate_natural_height=True, has_frame=True)
        scroller.set_margin_top(12)
        scroller.set_margin_bottom(6)
        scroller.add_css_class("termia-content-frame")
        scroller.add_css_class("termia-text-surface")
        scroller.set_child(view)
        expander.set_child(scroller)
        parent.append(expander)
        return expander, view

    @staticmethod
    def _history_toggled(expander, _property):
        window = expander.get_root()
        if isinstance(window, DiagnosticsWindow) and not window.closed and expander.get_expanded():
            window.history.clear()
            buffer = window.history_view.get_buffer()
            buffer.set_text(window.t("diagnostics_history_columns") + "\n")
            buffer.place_cursor(buffer.get_start_iter())

    def _record_history(self):
        if self.closed or not self.history_expander.get_expanded():
            return
        buffer = self.history_view.get_buffer()
        # Edit only the new/expired rows so GTK retains the reader's position
        # and selections in the remaining text instead of rebuilding the view.
        if len(self.history) == self.history.maxlen:
            first = buffer.get_start_iter()
            first.forward_line()  # Keep the column heading.
            end = first.copy()
            end.forward_line()
            buffer.delete(first, end)
        line = (f"{datetime.now():%H:%M:%S}  "
                f"{self.values['main', 'cpu'].get_text():>7}  "
                f"{self.values['main', 'memory'].get_text():>12}  "
                f"{self.values['children', 'cpu'].get_text():>7}  "
                f"{self.values['children', 'memory'].get_text():>12}")
        self.history.append(line)
        buffer.insert(buffer.get_end_iter(), line + "\n")

    def _sample(self):
        if self.closed:
            return GLib.SOURCE_REMOVE
        if self._future is None:
            # Only this immutable snapshot crosses from GTK to the worker.
            self._future = self._executor.submit(self.sampler.sample, self.context(), self.cancelled)
            self._poll = GLib.timeout_add(100, self._receive)
        return GLib.SOURCE_CONTINUE

    def _receive(self):
        if self.closed:
            self._poll = None
            return GLib.SOURCE_REMOVE
        if not self._future.done():
            return GLib.SOURCE_CONTINUE
        self._poll = None
        future, self._future = self._future, None
        try:
            snapshot = future.result()
        except Exception:
            logger.exception("Local diagnostics sampling failed")
            self.status.set_text(self.t("diagnostics_unavailable"))
        else:
            self.render(snapshot)
        return GLib.SOURCE_REMOVE

    def render(self, snapshot):
        self.status.set_text(self.t("diagnostics_partial" if snapshot.incomplete else "diagnostics_live"))
        self.sessions.set_text(self.t("diagnostics_sessions").format(
            sessions=snapshot.context.sessions, terminals=snapshot.context.terminals,
            ssh=snapshot.context.ssh_clients, local=snapshot.context.local_terminals))
        for group, samples in (("main", (snapshot.main,) if snapshot.main else ()),
                               ("children", snapshot.children)):
            available = snapshot.main is not None or bool(samples)
            def total(field, samples=samples, available=available):
                items = [getattr(sample, field) for sample in samples]
                return sum(items) if available and all(item is not None for item in items) else None

            data = {
                "cpu": cpu_text(total("cpu")),
                "memory": memory_text(sum(p.reading.rss for p in samples) if available else None),
                "threads": str(sum(p.reading.threads for p in samples)) if available else "—",
                "descriptors": str(total("descriptors")) if total("descriptors") is not None else "—",
                "processes": str(len(samples)) if available else "—",
            }
            for metric, value in data.items():
                self.values[group, metric].set_text(value)
        count = sum(sample.possible_orphan for sample in snapshot.children)
        self.orphans.set_text(self.t("diagnostics_orphans").format(count=count))
        self.orphans.set_visible(count > 0)
        lines = [self.t("diagnostics_process_columns")]
        samples = ((snapshot.main,) if snapshot.main else ()) + snapshot.children
        for sample in samples[:250]:
            record = sample.reading
            kind = "main" if sample is snapshot.main else ("orphan" if sample.possible_orphan else sample.kind)
            lines.append(f"{record.pid:>7}  {record.name:<16}  {cpu_text(sample.cpu):>7}  "
                         f"{memory_text(record.rss):>12}  {record.threads:>4}  "
                         f"{sample.descriptors if sample.descriptors is not None else '—':>5}  "
                         f"{self.t('diagnostics_kind_' + kind)}")
        if len(samples) > 250:
            lines.append(self.t("diagnostics_truncated"))
        self.process_view.get_buffer().set_text("\n".join(lines))
        self._record_history()

    def stop(self):
        if getattr(self, "closed", True):
            return
        self.closed = True
        self.cancelled.set()
        for source in (self._timer, self._poll):
            if source is not None:
                GLib.source_remove(source)
        self._timer = self._poll = None
        if self._future is not None:
            self._future.cancel()
            self._future = None
        self._executor.shutdown(wait=False, cancel_futures=True)

    def destroy(self):
        self.stop()
        super().destroy()


class DiagnosticsTool:
    def __init__(self, application, context):
        self.application = application
        self.context = context
        self.window = None

    def show(self, translate):
        if self.window is None or self.window.closed:
            self.window = DiagnosticsWindow(self.application, self.context, translate)
            owner = ref(self)

            def released(window):
                tool = owner()
                if tool is not None and getattr(tool, "window", None) is window:
                    tool.window = None

            self.window.connect("unrealize", released)
            self.window.connect("destroy", released)
        self.window.present()
        return self.window

    def close(self, *_args):
        if self.window is not None:
            window, self.window = self.window, None
            window.destroy()
