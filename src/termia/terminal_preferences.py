# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .constants import (
    DEFAULT_SPLIT_SEPARATOR_COLOR,
    DEFAULT_SPLIT_SEPARATOR_THICKNESS,
    DEFAULT_TERMINAL_BACKGROUND,
    DEFAULT_TERMINAL_FOREGROUND,
    MAX_SPLIT_SEPARATOR_THICKNESS,
    TERMINAL_PALETTES,
)
from .stores import ReadOnlyStoreError
from .terminal_config import parse_color


class TerminalPreferencesMixin:
    def on_terminal_settings(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("terminal"), transient_for=self, modal=True)
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

        font_combo = Gtk.ComboBoxText()
        font_families = self.terminal_font_families()
        for font_family in font_families:
            font_combo.append_text(font_family)
        active_font = self.resolved_terminal_font_family(settings.font_family)
        font_combo.set_active(font_families.index(active_font) if active_font in font_families else 0)
        font_size_spin = Gtk.SpinButton.new_with_range(6, 72, 1)
        font_size_spin.set_value(settings.font_size)

        foreground_button = Gtk.ColorButton()
        foreground_button.set_rgba(parse_color(settings.foreground, DEFAULT_TERMINAL_FOREGROUND))
        foreground_button.set_title(self.t("foreground"))
        background_button = Gtk.ColorButton()
        background_button.set_rgba(parse_color(settings.background, DEFAULT_TERMINAL_BACKGROUND))
        background_button.set_title(self.t("background"))
        split_separator_color_button = Gtk.ColorButton()
        split_separator_color_button.set_rgba(parse_color(settings.split_separator_color, DEFAULT_SPLIT_SEPARATOR_COLOR))
        split_separator_color_button.set_title(self.t("split_separator_color"))
        split_separator_thickness_spin = Gtk.SpinButton.new_with_range(1, MAX_SPLIT_SEPARATOR_THICKNESS, 1)
        split_separator_thickness_spin.set_value(settings.split_separator_thickness or DEFAULT_SPLIT_SEPARATOR_THICKNESS)

        preview = Gtk.Label()
        preview.set_use_markup(True)
        preview.set_xalign(0)
        preview.set_margin_top(10)
        preview.set_margin_bottom(10)
        preview.set_margin_start(12)
        preview.set_margin_end(12)
        preview.set_css_classes(["terminal-preview"])
        preview_overlay = Gtk.Overlay()
        preview_overlay.set_hexpand(True)
        preview_overlay.set_child(preview)
        split_preview_line = Gtk.Box()
        split_preview_line.add_css_class("termia-split-preview-line")
        split_preview_line.set_halign(Gtk.Align.END)
        split_preview_line.set_valign(Gtk.Align.FILL)
        split_preview_line.set_margin_top(10)
        split_preview_line.set_margin_bottom(10)
        split_preview_line.set_margin_end(12)
        preview_overlay.add_overlay(split_preview_line)

        preview_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(preview.get_display(), preview_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        split_preview_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            split_preview_line.get_display(), split_preview_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        display = preview.get_display()

        def cleanup_preview_providers(*_args: object) -> None:
            Gtk.StyleContext.remove_provider_for_display(display, preview_provider)
            Gtk.StyleContext.remove_provider_for_display(display, split_preview_provider)

        palette_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for palette_name, (foreground, background) in TERMINAL_PALETTES.items():
            palette_button = Gtk.Button(label=palette_name)
            palette_button.connect(
                "clicked", self.on_terminal_palette_clicked, foreground_button, background_button, foreground, background
            )
            palette_box.append(palette_button)

        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("font_size"), font_combo),
            ("", font_size_spin),
            (self.t("foreground"), foreground_button),
            (self.t("background"), background_button),
            (self.t("split_separator_color"), split_separator_color_button),
            (self.t("split_separator_thickness"), split_separator_thickness_spin),
            (self.t("palettes"), palette_box),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)
        content.append(grid)
        content.append(preview_overlay)

        self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button, preview_provider)
        self.update_terminal_split_preview(
            split_preview_line, split_separator_color_button, split_separator_thickness_spin, split_preview_provider
        )
        font_combo.connect("changed", lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button, preview_provider))
        font_size_spin.connect("value-changed", lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button, preview_provider))
        foreground_button.connect("notify::rgba", lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button, preview_provider))
        background_button.connect("notify::rgba", lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button, preview_provider))
        split_separator_color_button.connect(
            "notify::rgba",
            lambda *_args: self.update_terminal_split_preview(split_preview_line, split_separator_color_button, split_separator_thickness_spin, split_preview_provider),
        )
        split_separator_thickness_spin.connect(
            "value-changed",
            lambda *_args: self.update_terminal_split_preview(split_preview_line, split_separator_color_button, split_separator_thickness_spin, split_preview_provider),
        )
        dialog.connect(
            "response",
            self.on_terminal_settings_response,
            font_combo,
            font_size_spin,
            foreground_button,
            background_button,
            split_separator_color_button,
            split_separator_thickness_spin,
        )
        dialog.connect("destroy", cleanup_preview_providers)
        dialog.present()

    def on_terminal_palette_clicked(
        self,
        _button: Gtk.Button,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
        foreground: str,
        background: str,
    ) -> None:
        foreground_button.set_rgba(parse_color(foreground, DEFAULT_TERMINAL_FOREGROUND))
        background_button.set_rgba(parse_color(background, DEFAULT_TERMINAL_BACKGROUND))

    def terminal_font_families(self) -> list[str]:
        families = [family.get_name() for family in self.get_pango_context().list_families() if family.is_monospace()]
        names = sorted(set(families), key=str.lower)
        if "Monospace" not in names:
            names.insert(0, "Monospace")
        return names or ["Monospace"]

    def resolved_terminal_font_family(self, preferred: str) -> str:
        font_families = self.terminal_font_families()
        if preferred in font_families:
            return preferred
        for fallback in ("JetBrains Mono", "Ubuntu Mono", "Monospace"):
            if fallback in font_families:
                return fallback
        return font_families[0] if font_families else "Monospace"

    def selected_terminal_font_family(self, font_combo: Gtk.ComboBoxText) -> str:
        return font_combo.get_active_text() or "Monospace"

    def update_terminal_preview(
        self,
        preview: Gtk.Label,
        font_combo: Gtk.ComboBoxText,
        font_size_spin: Gtk.SpinButton,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
        provider: Gtk.CssProvider,
    ) -> None:
        font_family = self.selected_terminal_font_family(font_combo)
        font_size = int(font_size_spin.get_value())
        foreground = foreground_button.get_rgba().to_string()
        background = background_button.get_rgba().to_string()
        preview.set_markup("usuario@servidor:~$ ssh ejemplo\nSalida de terminal")
        provider.load_from_data(
            f".terminal-preview {{font-family: '{font_family}';font-size: {font_size}pt;color: {foreground};background: {background};border-radius: 6px;}}".encode()
        )

    def update_terminal_split_preview(
        self,
        preview_line: Gtk.Widget,
        split_separator_color_button: Gtk.ColorButton,
        split_separator_thickness_spin: Gtk.SpinButton,
        provider: Gtk.CssProvider,
    ) -> None:
        split_separator_color = split_separator_color_button.get_rgba().to_string()
        split_separator_thickness = max(1, min(int(split_separator_thickness_spin.get_value()), MAX_SPLIT_SEPARATOR_THICKNESS))
        preview_line.set_size_request(split_separator_thickness, -1)
        provider.load_from_data(
            f".termia-split-preview-line {{background: {split_separator_color};background-color: {split_separator_color};border-radius: 999px;}}".encode()
        )

    def on_terminal_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        font_combo: Gtk.ComboBoxText,
        font_size_spin: Gtk.SpinButton,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
        split_separator_color_button: Gtk.ColorButton,
        split_separator_thickness_spin: Gtk.SpinButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            try:
                self.store.update_terminal_settings(
                    font_family=self.selected_terminal_font_family(font_combo),
                    font_size=int(font_size_spin.get_value()),
                    foreground=foreground_button.get_rgba().to_string(),
                    background=background_button.get_rgba().to_string(),
                    split_separator_color=split_separator_color_button.get_rgba().to_string(),
                    split_separator_thickness=int(split_separator_thickness_spin.get_value()),
                )
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.apply_terminal_settings_to_open_tabs()
            self.install_tree_styles()
            self.toast_label.set_label(self.t("terminal_settings_saved"))
        dialog.destroy()
