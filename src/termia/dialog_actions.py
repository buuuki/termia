# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared layout rules for standard dialog action buttons."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

DIALOG_ACTION_SPACING = 8
DIALOG_ACTION_INSET_TOP = 16
DIALOG_ACTION_INSET_BOTTOM = 16
DIALOG_ACTION_INSET_START = 16
DIALOG_ACTION_INSET_END = 16


def add_dialog_action_button(
    dialog: Gtk.Dialog,
    label: str,
    response: Gtk.ResponseType,
) -> Gtk.Button:
    """Add a dialog action and apply Termia's shared action-area layout."""
    button = dialog.add_button(label, response)
    action_area = button.get_parent()
    if isinstance(action_area, Gtk.Box):
        configure_action_area(action_area)
    return button


def configure_dialog_content(content: Gtk.Widget) -> Gtk.Widget:
    """Align content with the shared action row without nested outer margins."""
    content.set_margin_top(DIALOG_ACTION_INSET_TOP)
    content.set_margin_bottom(0)
    content.set_margin_start(DIALOG_ACTION_INSET_START)
    content.set_margin_end(DIALOG_ACTION_INSET_END)
    return content


def configure_action_area(action_area: Gtk.Box) -> Gtk.Box:
    """Apply the shared action layout to a row built by an independent window."""
    action_area.set_spacing(DIALOG_ACTION_SPACING)
    action_area.set_margin_top(DIALOG_ACTION_INSET_TOP)
    action_area.set_margin_bottom(DIALOG_ACTION_INSET_BOTTOM)
    action_area.set_margin_start(DIALOG_ACTION_INSET_START)
    action_area.set_margin_end(DIALOG_ACTION_INSET_END)
    return action_area
