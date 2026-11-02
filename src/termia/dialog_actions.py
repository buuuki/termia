# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared layout rules for standard dialog action buttons."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .dialog_window import DialogWindow

DIALOG_ACTION_SPACING = 8
DIALOG_ACTION_INSET_TOP = 16
DIALOG_ACTION_INSET_BOTTOM = 16
DIALOG_ACTION_INSET_START = 16
DIALOG_ACTION_INSET_END = 16


def add_dialog_action_button(
    dialog: DialogWindow,
    label: str,
    response: Gtk.ResponseType,
) -> Gtk.Button:
    """Add a dialog action and apply Termia's shared action-area layout."""
    button = dialog.add_button(label, response)
    action_area = button.get_parent()
    if isinstance(action_area, Gtk.Box):
        configure_action_area(action_area)
    return button


def configure_dialog_content(
    content: Gtk.Widget, *, spacing: int | None = None,
) -> Gtk.Widget:
    """Align content with the shared action row without nested outer margins."""
    if spacing is not None:
        content.set_spacing(spacing)
    content.set_margin_top(DIALOG_ACTION_INSET_TOP)
    content.set_margin_bottom(0)
    content.set_margin_start(DIALOG_ACTION_INSET_START)
    content.set_margin_end(DIALOG_ACTION_INSET_END)
    return content


def configure_action_area(
    action_area: Gtk.Box, *, align: Gtk.Align | None = None,
) -> Gtk.Box:
    """Apply the shared action layout to a row built by an independent window."""
    if align is not None:
        action_area.set_halign(align)
    action_area.set_spacing(DIALOG_ACTION_SPACING)
    action_area.set_margin_top(DIALOG_ACTION_INSET_TOP)
    action_area.set_margin_bottom(DIALOG_ACTION_INSET_BOTTOM)
    action_area.set_margin_start(DIALOG_ACTION_INSET_START)
    action_area.set_margin_end(DIALOG_ACTION_INSET_END)
    return action_area


def configure_content_button(button: Gtk.Button) -> Gtk.Button:
    """Keep a content action compact without moving it into the footer."""
    button.set_halign(Gtk.Align.START)
    button.set_valign(Gtk.Align.CENTER)
    button.set_hexpand(False)
    button.set_vexpand(False)
    button.set_size_request(160, -1)
    return button
