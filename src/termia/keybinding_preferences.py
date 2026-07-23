# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .keybindings import DEFAULT_KEYBINDINGS, KEYBINDING_ACTIONS, keybinding_from_event, keybinding_label, normalize_keybinding
from .stores import ReadOnlyStoreError


class KeybindingCaptureRow(Gtk.Box):
    def __init__(self, accelerator: str, disabled_label: str, capture_prompt: str, clear_label: str) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_hexpand(True)
        self._disabled_label = disabled_label
        self._capture_prompt = capture_prompt
        self._clear_label = clear_label
        self._accelerator = normalize_keybinding(accelerator)
        self._capturing = False
        self._capture_button = Gtk.Button()
        self._capture_button.set_hexpand(True)
        self._capture_button.set_halign(Gtk.Align.FILL)
        self._capture_button.connect("clicked", self.on_capture_clicked)
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self._capture_button.add_controller(key_controller)
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect("leave", self.on_focus_leave)
        self._capture_button.add_controller(focus_controller)
        self._clear_button = Gtk.Button(label=self._clear_label)
        self._clear_button.connect("clicked", self.on_clear_clicked)
        self.append(self._capture_button)
        self.append(self._clear_button)
        self.update_label()

    def get_accelerator(self) -> str:
        return self._accelerator

    def set_accelerator(self, accelerator: str) -> None:
        self._accelerator = normalize_keybinding(accelerator)
        self._capturing = False
        self.update_label()

    def update_label(self) -> None:
        if self._capturing:
            self._capture_button.set_label(self._capture_prompt)
            self._capture_button.add_css_class("suggested-action")
        else:
            self._capture_button.set_label(keybinding_label(self._accelerator, self._disabled_label))
            self._capture_button.remove_css_class("suggested-action")

    def on_capture_clicked(self, _button: Gtk.Button) -> None:
        self._capturing = True
        self.update_label()
        self._capture_button.grab_focus()

    def on_clear_clicked(self, _button: Gtk.Button) -> None:
        self.set_accelerator("")

    def on_focus_leave(self, _controller: Gtk.EventControllerFocus) -> None:
        if self._capturing:
            self._capturing = False
            self.update_label()

    def on_key_pressed(self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: object) -> bool:
        if not self._capturing:
            return False
        accelerator = keybinding_from_event(keyval, state)
        if not accelerator:
            return True
        self._accelerator = accelerator
        self._capturing = False
        self.update_label()
        return True


class KeybindingPreferencesMixin:
    def on_keybindings_settings(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("keybindings"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(520, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        self.add_dialog_action_button(dialog, self.t("keybindings_restore_defaults"), Gtk.ResponseType.APPLY)
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)
        description = Gtk.Label(label=self.t("keybindings_description"))
        description.set_xalign(0)
        description.set_wrap(True)
        description.add_css_class("dim-label")
        content.append(description)
        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        rows: list[tuple[str, KeybindingCaptureRow]] = []
        for index, (action, label_key) in enumerate(KEYBINDING_ACTIONS):
            label = Gtk.Label(label=self.t(label_key))
            label.set_xalign(0)
            row = KeybindingCaptureRow(
                self.store.data.app.keybindings.get(action, DEFAULT_KEYBINDINGS[action]),
                self.t("keybinding_disabled"), self.t("keybinding_capture_prompt"), self.t("keybinding_clear"),
            )
            rows.append((action, row))
            grid.attach(label, 0, index, 1, 1)
            grid.attach(row, 1, index, 1, 1)
        content.append(grid)
        dialog.connect("response", self.on_keybindings_settings_response, rows)
        dialog.present()

    def on_keybindings_settings_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType,
                                         rows: list[tuple[str, KeybindingCaptureRow]]) -> None:
        if response == Gtk.ResponseType.APPLY:
            for action, row in rows:
                row.set_accelerator(DEFAULT_KEYBINDINGS[action])
            return
        if response == Gtk.ResponseType.OK:
            keybindings = {action: row.get_accelerator() for action, row in rows}
            conflict = self.duplicate_keybinding(keybindings)
            if conflict:
                self.toast_label.set_label(self.t("keybindings_conflict").format(shortcut=conflict))
                return
            try:
                self.store.update_keybindings(keybindings)
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.toast_label.set_label(self.t("keybindings_settings_saved"))
        dialog.destroy()

    def duplicate_keybinding(self, keybindings: dict[str, str]) -> str:
        seen: set[str] = set()
        for shortcut in keybindings.values():
            normalized = normalize_keybinding(shortcut)
            if not normalized:
                continue
            if normalized in seen:
                return normalized
            seen.add(normalized)
        return ""
