# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable application IDs for native Gtk.DropDown string models."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango


def text_choice() -> Gtk.DropDown:
    widget = Gtk.DropDown(model=Gtk.StringList.new([]))
    widget._termia_choice_ids = []
    return widget


def constrain_choice(widget: Gtk.DropDown, width: int, maximum: int) -> None:
    factory = Gtk.SignalListItemFactory()

    def setup(_factory, item):
        label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        label.set_width_chars(width)
        label.set_max_width_chars(maximum)
        item.set_child(label)

    def bind(_factory, item):
        item.get_child().set_label(item.get_item().get_string())

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    widget.set_factory(factory)


def append_choice(widget: Gtk.DropDown, value: str, label: str) -> None:
    widget._termia_choice_ids.append(value)
    widget.get_model().append(label)


def append_choice_text(widget: Gtk.DropDown, label: str) -> None:
    append_choice(widget, label, label)


def clear_choices(widget: Gtk.DropDown) -> None:
    widget._termia_choice_ids.clear()
    model = widget.get_model()
    model.splice(0, model.get_n_items(), [])


def choice_index(widget: Gtk.DropDown) -> int:
    selected = widget.get_selected()
    return -1 if selected == Gtk.INVALID_LIST_POSITION else selected


def choice_id(widget: Gtk.DropDown) -> str | None:
    selected = choice_index(widget)
    ids = widget._termia_choice_ids
    return ids[selected] if 0 <= selected < len(ids) else None


def choice_text(widget: Gtk.DropDown) -> str | None:
    item = widget.get_selected_item()
    return item.get_string() if item is not None else None


def select_choice(widget: Gtk.DropDown, value: str) -> bool:
    ids = widget._termia_choice_ids
    if value not in ids:
        return False
    widget.set_selected(ids.index(value))
    return True
