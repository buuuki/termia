# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .constants import DEFAULT_PROMPT_COLOR, PROMPT_PRESETS
from .stores import ReadOnlyStoreError
from .terminal_config import (
    parse_color,
    prompt_template_with_datetime,
    render_prompt_preview,
    rgba_to_hex,
    split_prompt_datetime_template,
)


class PromptPreferencesMixin:
    def on_prompt_settings(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("prompt"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(540, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        settings = self.store.data.terminal
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(14)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)

        prompt_enabled = Gtk.CheckButton(label=self.t("custom_prompt"))
        prompt_enabled.set_active(settings.prompt_enabled)
        prompt_enabled.set_halign(Gtk.Align.START)
        prompt_datetime_id, prompt_base_template = split_prompt_datetime_template(settings.prompt_template)
        prompt_datetime_combo = Gtk.ComboBoxText()
        prompt_datetime_combo.append("none", self.t("prompt_datetime_none"))
        prompt_datetime_combo.append("time", self.t("prompt_datetime_time"))
        prompt_datetime_combo.append("time_seconds", self.t("prompt_datetime_time_seconds"))
        prompt_datetime_combo.append("date", self.t("prompt_datetime_date"))
        prompt_datetime_combo.append("both", self.t("prompt_datetime_both"))
        prompt_datetime_combo.set_active_id(prompt_datetime_id)
        prompt_template_entry = Gtk.Entry()
        prompt_template_entry.set_text(prompt_base_template)
        prompt_template_entry.set_placeholder_text(r"\u@\h:\w\$ ")
        prompt_color_button = Gtk.ColorButton()
        prompt_color_button.set_rgba(parse_color(settings.prompt_color, DEFAULT_PROMPT_COLOR))
        prompt_color_button.set_title(self.t("prompt_color"))

        prompt_preset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        for preset_name, (template, color) in PROMPT_PRESETS.items():
            preset_button = Gtk.Button(label=preset_name)
            preset_button.add_css_class("prompt-preset-button")
            preset_button.set_size_request(-1, 24)
            preset_button.connect("clicked", self.on_prompt_preset_clicked, prompt_template_entry, prompt_color_button, template, color)
            prompt_preset_box.append(preset_button)

        prompt_controls = (prompt_datetime_combo, prompt_template_entry, prompt_color_button, prompt_preset_box)
        for prompt_widget in prompt_controls:
            prompt_widget.set_sensitive(prompt_enabled.get_active())
        prompt_enabled.connect("toggled", lambda current: [widget.set_sensitive(current.get_active()) for widget in prompt_controls])

        rows: list[tuple[str, Gtk.Widget]] = [
            ("", prompt_enabled),
            (self.t("prompt_datetime"), prompt_datetime_combo),
            (self.t("prompt_template"), prompt_template_entry),
            (self.t("prompt_color"), prompt_color_button),
            (self.t("prompt_presets"), prompt_preset_box),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)

        preview = Gtk.Label()
        preview.set_use_markup(True)
        preview.set_xalign(0)
        preview.set_margin_top(10)
        preview.set_margin_bottom(10)
        preview.set_margin_start(12)
        preview.set_margin_end(12)
        preview.set_css_classes(["terminal-preview"])
        preview_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(preview.get_display(), preview_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        display = preview.get_display()

        def cleanup_preview_provider(*_args: object) -> None:
            Gtk.StyleContext.remove_provider_for_display(display, preview_provider)

        content.append(grid)
        content.append(preview)
        self.update_prompt_preview(preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button, preview_provider)
        prompt_enabled.connect("toggled", lambda *_args: self.update_prompt_preview(preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button, preview_provider))
        prompt_datetime_combo.connect("changed", lambda *_args: self.update_prompt_preview(preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button, preview_provider))
        prompt_template_entry.connect("changed", lambda *_args: self.update_prompt_preview(preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button, preview_provider))
        prompt_color_button.connect("notify::rgba", lambda *_args: self.update_prompt_preview(preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button, preview_provider))
        dialog.connect("response", self.on_prompt_settings_response, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button)
        dialog.connect("destroy", cleanup_preview_provider)
        dialog.present()

    def on_prompt_preset_clicked(
        self,
        _button: Gtk.Button,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
        template: str,
        color: str,
    ) -> None:
        prompt_template_entry.set_text(template)
        prompt_color_button.set_rgba(parse_color(color, DEFAULT_PROMPT_COLOR))

    def update_prompt_preview(
        self,
        preview: Gtk.Label,
        prompt_enabled: Gtk.CheckButton,
        prompt_datetime_combo: Gtk.ComboBoxText,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
        provider: Gtk.CssProvider,
    ) -> None:
        command_markup = GLib.markup_escape_text("ssh ejemplo\nSalida de terminal")
        if prompt_enabled.get_active():
            prompt_text = render_prompt_preview(
                prompt_template_with_datetime(prompt_template_entry.get_text(), prompt_datetime_combo.get_active_id() or "none")
            )
            prompt_markup = GLib.markup_escape_text(prompt_text)
            prompt_color = rgba_to_hex(prompt_color_button.get_rgba())
            preview.set_markup(f'<span foreground="{prompt_color}">{prompt_markup}</span>{command_markup}')
        else:
            preview.set_markup(GLib.markup_escape_text("usuario@servidor:~$ ssh ejemplo\nSalida de terminal"))
        settings = self.store.data.terminal
        provider.load_from_data(
            f".terminal-preview {{font-family: '{settings.font_family}';font-size: {settings.font_size}pt;color: {settings.foreground};background: {settings.background};border-radius: 6px;}}".encode()
        )

    def on_prompt_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        prompt_enabled: Gtk.CheckButton,
        prompt_datetime_combo: Gtk.ComboBoxText,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            try:
                self.store.update_prompt_settings(
                    prompt_enabled.get_active(),
                    prompt_template_with_datetime(prompt_template_entry.get_text(), prompt_datetime_combo.get_active_id() or "none"),
                    rgba_to_hex(prompt_color_button.get_rgba()),
                )
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.toast_label.set_label(self.t("prompt_settings_saved"))
        dialog.destroy()
