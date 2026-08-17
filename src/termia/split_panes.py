# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import GLib, Gtk, Vte

from .ui_state import TerminalSession

PaneRect = tuple[float, float, float, float]
SplitPosition = tuple[Gtk.Paned, int]


def directional_pane_neighbor(
    source_id: int,
    direction: str,
    rectangles: dict[int, PaneRect],
) -> int | None:
    """Return the visually nearest pane in one cardinal direction."""
    source = rectangles.get(source_id)
    if source is None or direction not in {"left", "right", "up", "down"}:
        return None
    sx, sy, sw, sh = source
    source_primary = sx + sw / 2 if direction in {"left", "right"} else sy + sh / 2
    source_cross_start, source_cross_end = (sy, sy + sh) if direction in {"left", "right"} else (sx, sx + sw)
    candidates: list[tuple[tuple[float, ...], int]] = []
    for pane_id, (x, y, width, height) in rectangles.items():
        if pane_id == source_id:
            continue
        candidate_primary = x + width / 2 if direction in {"left", "right"} else y + height / 2
        if direction in {"left", "up"} and candidate_primary >= source_primary:
            continue
        if direction in {"right", "down"} and candidate_primary <= source_primary:
            continue
        cross_start, cross_end = (y, y + height) if direction in {"left", "right"} else (x, x + width)
        cross_overlap = max(
            0.0,
            min(source_cross_end, cross_end) - max(source_cross_start, cross_start),
        )
        cross_gap = max(0.0, source_cross_start - cross_end, cross_start - source_cross_end)
        primary_gap = abs(candidate_primary - source_primary)
        cross_center_gap = abs((cross_start + cross_end) / 2 - (source_cross_start + source_cross_end) / 2)
        score = (
            1.0 if cross_overlap == 0 else 0.0,
            cross_gap,
            primary_gap,
            -cross_overlap,
            cross_center_gap,
        )
        candidates.append((score, pane_id))
    return min(candidates)[1] if candidates else None


class SplitPaneController:
    def __init__(
        self,
        create_terminal: Callable[[TerminalSession], Vte.Terminal],
        pane_container: Callable[[TerminalSession, Vte.Terminal], Gtk.Widget | None],
        replace_terminal: Callable[[Gtk.Widget, Gtk.Widget], bool],
    ) -> None:
        self.create_terminal = create_terminal
        self.pane_container = pane_container
        self.replace_terminal = replace_terminal

    def split_terminal(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        direction: str,
        *,
        preserve_ancestor_positions: bool = True,
    ) -> Vte.Terminal | None:
        target = self.pane_container(session, terminal)
        if target is None:
            return None
        target_width = target.get_width()
        target_height = target.get_height()
        ancestor_positions = (
            self.capture_ancestor_positions(target)
            if preserve_ancestor_positions
            else ()
        )

        new_terminal = self.create_terminal(session)
        new_pane = self.pane_container(session, new_terminal)
        if new_pane is None:
            session.split_terminals.remove(new_terminal)
            session.active_terminal_ids.discard(id(new_terminal))
            session.panes.pop(id(new_terminal), None)
            return None
        orientation = Gtk.Orientation.HORIZONTAL if direction in {"left", "right"} else Gtk.Orientation.VERTICAL
        paned = Gtk.Paned(orientation=orientation)
        paned.add_css_class("termia-split-pane")
        paned.set_wide_handle(False)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        paned.set_shrink_start_child(True)
        paned.set_shrink_end_child(True)
        target.add_css_class("in-split")
        new_pane.add_css_class("in-split")

        if not self.replace_terminal(target, paned):
            session.split_terminals.remove(new_terminal)
            session.active_terminal_ids.discard(id(new_terminal))
            session.panes.pop(id(new_terminal), None)
            return None

        if direction in {"left", "up"}:
            paned.set_start_child(new_pane)
            paned.set_end_child(target)
        else:
            paned.set_start_child(target)
            paned.set_end_child(new_pane)

        target_size = (
            target_width
            if orientation == Gtk.Orientation.HORIZONTAL
            else target_height
        )
        self.initialize_split_position(paned, orientation, target_size)
        if ancestor_positions:
            self.restore_ancestor_positions(ancestor_positions)
            GLib.idle_add(self.restore_ancestor_positions, ancestor_positions)
        new_terminal.grab_focus()
        return new_terminal

    @staticmethod
    def capture_ancestor_positions(widget: Gtk.Widget) -> tuple[SplitPosition, ...]:
        positions: list[SplitPosition] = []
        parent = widget.get_parent()
        while parent is not None:
            if isinstance(parent, Gtk.Paned):
                positions.append((parent, parent.get_position()))
            parent = parent.get_parent()
        return tuple(positions)

    @staticmethod
    def restore_ancestor_positions(positions: tuple[SplitPosition, ...]) -> bool:
        for paned, position in positions:
            paned.set_position(position)
        return GLib.SOURCE_REMOVE

    @staticmethod
    def initialize_split_position(
        paned: Gtk.Paned,
        orientation: Gtk.Orientation,
        target_size: int,
    ) -> None:
        if target_size > 0:
            paned.set_position(target_size // 2)
            return

        handler: dict[str, int | None] = {"id": None}

        def center_when_allocated(current: Gtk.Paned, _parameter: object) -> None:
            size = (
                current.get_width()
                if orientation == Gtk.Orientation.HORIZONTAL
                else current.get_height()
            )
            if size <= 0:
                return
            current.set_position(size // 2)
            handler_id = handler["id"]
            if handler_id is not None:
                current.disconnect(handler_id)
                handler["id"] = None

        handler["id"] = paned.connect("notify::max-position", center_when_allocated)
        center_when_allocated(paned, object())
