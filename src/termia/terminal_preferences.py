# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .constants import (
    DEFAULT_SPLIT_SEPARATOR_COLOR,
    DEFAULT_SPLIT_SEPARATOR_THICKNESS,
    DEFAULT_PROMPT_COLOR,
    DEFAULT_TERMINAL_BACKGROUND,
    DEFAULT_TERMINAL_FOREGROUND,
    MAX_SPLIT_SEPARATOR_THICKNESS,
    PROMPT_PRESETS,
    TERMINAL_PALETTES,
)
from .prompt_preferences import combined_terminal_preview_markup
from .stores import ReadOnlyStoreError
from .terminal_config import (
    parse_color,
    prompt_template_with_datetime,
    rgba_to_hex,
    split_prompt_datetime_template,
)


class TerminalPreferencesMixin:
    def on_terminal_settings(
        self,
        _button: Gtk.Button | None,
        parent: Gtk.Window | None = None,
    ) -> None:
        if not self.ensure_writable():
            return
        owner = parent if parent is not None else self
        dialog = Gtk.Dialog(title=self.t("terminal"), transient_for=owner, modal=True)
        dialog.set_resizable(True)
        dialog.set_default_size(760, 620)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        settings = self.store.data.terminal
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(10)
        preferences_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.append(preferences_box)
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        grid.set_margin_top(8)
        grid.set_margin_bottom(8)
        grid.set_margin_start(10)
        grid.set_margin_end(10)

        font_combo = Gtk.ComboBoxText()
        font_combo.set_halign(Gtk.Align.START)
        font_families = self.terminal_font_families()
        for font_family in font_families:
            font_combo.append_text(font_family)
        active_font = self.resolved_terminal_font_family(settings.font_family)
        font_combo.set_active(font_families.index(active_font) if active_font in font_families else 0)
        font_size_spin = Gtk.SpinButton.new_with_range(6, 72, 1)
        font_size_spin.set_value(settings.font_size)
        font_size_spin.set_width_chars(4)

        foreground_button = Gtk.ColorButton()
        foreground_button.set_halign(Gtk.Align.START)
        foreground_button.set_rgba(parse_color(settings.foreground, DEFAULT_TERMINAL_FOREGROUND))
        foreground_button.set_title(self.t("foreground"))
        background_button = Gtk.ColorButton()
        background_button.set_halign(Gtk.Align.START)
        background_button.set_rgba(parse_color(settings.background, DEFAULT_TERMINAL_BACKGROUND))
        background_button.set_title(self.t("background"))
        split_separator_color_button = Gtk.ColorButton()
        split_separator_color_button.set_halign(Gtk.Align.START)
        split_separator_color_button.set_rgba(parse_color(settings.split_separator_color, DEFAULT_SPLIT_SEPARATOR_COLOR))
        split_separator_color_button.set_title(self.t("split_separator_color"))
        split_separator_thickness_spin = Gtk.SpinButton.new_with_range(1, MAX_SPLIT_SEPARATOR_THICKNESS, 1)
        split_separator_thickness_spin.set_value(settings.split_separator_thickness or DEFAULT_SPLIT_SEPARATOR_THICKNESS)
        split_separator_thickness_spin.set_width_chars(4)

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
        palette_box.set_halign(Gtk.Align.START)
        for palette_name, (foreground, background) in TERMINAL_PALETTES.items():
            palette_button = Gtk.Button(label=palette_name)
            palette_button.set_halign(Gtk.Align.START)
            palette_button.connect(
                "clicked", self.on_terminal_palette_clicked, foreground_button, background_button, foreground, background
            )
            palette_box.append(palette_button)

        rows: list[tuple[str, Gtk.Widget, str, Gtk.Widget]] = [
            (self.t("font_size"), font_combo, "", font_size_spin),
            (self.t("foreground"), foreground_button, self.t("background"), background_button),
            (
                self.t("split_separator_color"),
                split_separator_color_button,
                self.t("split_separator_thickness"),
                split_separator_thickness_spin,
            ),
        ]
        for index, (left_text, left_widget, right_text, right_widget) in enumerate(rows):
            for column, label_text, widget in (
                (0, left_text, left_widget),
                (2, right_text, right_widget),
            ):
                label = Gtk.Label(label=label_text)
                label.set_xalign(0)
                grid.attach(label, column, index, 1, 1)
                grid.attach(widget, column + 1, index, 1, 1)
        palette_label = Gtk.Label(label=self.t("palettes"))
        palette_label.set_xalign(0)
        grid.attach(palette_label, 0, len(rows), 1, 1)
        grid.attach(palette_box, 1, len(rows), 3, 1)
        appearance_frame = Gtk.Frame(label=self.t("terminal_appearance"))
        appearance_frame.set_child(grid)
        preferences_box.append(appearance_frame)

        preview_title = Gtk.Label(label=self.t("terminal_preview"))
        preview_title.set_xalign(0)
        preview_title.add_css_class("heading")
        preferences_box.append(preview_title)
        preferences_box.append(preview_overlay)

        prompt_enabled = Gtk.CheckButton(label=self.t("custom_prompt"))
        prompt_enabled.set_active(settings.prompt_enabled)
        prompt_enabled.set_halign(Gtk.Align.START)
        prompt_datetime_id, prompt_base_template = split_prompt_datetime_template(
            settings.prompt_template
        )
        prompt_datetime_combo = Gtk.ComboBoxText()
        prompt_datetime_combo.set_halign(Gtk.Align.START)
        for option_id in ("none", "time", "time_seconds", "date", "both"):
            prompt_datetime_combo.append(option_id, self.t(f"prompt_datetime_{option_id}"))
        prompt_datetime_combo.set_active_id(prompt_datetime_id)
        prompt_template_entry = Gtk.Entry()
        prompt_template_entry.set_hexpand(True)
        prompt_template_entry.set_text(prompt_base_template)
        prompt_template_entry.set_placeholder_text(r"\u@\h:\w\$ ")
        prompt_color_button = Gtk.ColorButton()
        prompt_color_button.set_halign(Gtk.Align.START)
        prompt_color_button.set_rgba(parse_color(settings.prompt_color, DEFAULT_PROMPT_COLOR))
        prompt_color_button.set_title(self.t("prompt_color"))
        prompt_preset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        prompt_preset_box.set_halign(Gtk.Align.START)
        for preset_name, (template, color) in PROMPT_PRESETS.items():
            preset_button = Gtk.Button(label=preset_name)
            preset_button.set_halign(Gtk.Align.START)
            preset_button.add_css_class("prompt-preset-button")
            preset_button.set_size_request(-1, 24)
            preset_button.connect(
                "clicked",
                self.on_prompt_preset_clicked,
                prompt_template_entry,
                prompt_color_button,
                template,
                color,
            )
            prompt_preset_box.append(preset_button)
        prompt_controls = (
            prompt_datetime_combo,
            prompt_template_entry,
            prompt_color_button,
            prompt_preset_box,
        )
        for prompt_widget in prompt_controls:
            prompt_widget.set_sensitive(prompt_enabled.get_active())
        prompt_enabled.connect(
            "toggled",
            lambda current: [
                widget.set_sensitive(current.get_active()) for widget in prompt_controls
            ],
        )
        prompt_grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        prompt_grid.set_margin_top(8)
        prompt_grid.set_margin_bottom(8)
        prompt_grid.set_margin_start(10)
        prompt_grid.set_margin_end(10)
        prompt_grid.attach(prompt_enabled, 0, 0, 4, 1)
        prompt_datetime_label = Gtk.Label(label=self.t("prompt_datetime"))
        prompt_datetime_label.set_xalign(0)
        prompt_grid.attach(prompt_datetime_label, 0, 1, 1, 1)
        prompt_grid.attach(prompt_datetime_combo, 1, 1, 1, 1)
        prompt_color_label = Gtk.Label(label=self.t("prompt_color"))
        prompt_color_label.set_xalign(0)
        prompt_grid.attach(prompt_color_label, 2, 1, 1, 1)
        prompt_grid.attach(prompt_color_button, 3, 1, 1, 1)
        prompt_template_label = Gtk.Label(label=self.t("prompt_template"))
        prompt_template_label.set_xalign(0)
        prompt_grid.attach(prompt_template_label, 0, 2, 1, 1)
        prompt_grid.attach(prompt_template_entry, 1, 2, 3, 1)
        prompt_presets_label = Gtk.Label(label=self.t("prompt_presets"))
        prompt_presets_label.set_xalign(0)
        prompt_grid.attach(prompt_presets_label, 0, 3, 1, 1)
        prompt_grid.attach(prompt_preset_box, 1, 3, 3, 1)
        prompt_note = Gtk.Label(label=self.t("prompt_new_terminals_only"))
        prompt_note.set_xalign(0)
        prompt_note.set_wrap(True)
        prompt_note.add_css_class("dim-label")
        prompt_grid.attach(prompt_note, 0, 4, 4, 1)
        prompt_frame = Gtk.Frame(label=self.t("local_prompt"))
        prompt_frame.set_child(prompt_grid)
        preferences_box.append(prompt_frame)

        update_preview = lambda *_args: self.update_terminal_preview(
            preview,
            font_combo,
            font_size_spin,
            foreground_button,
            background_button,
            prompt_enabled,
            prompt_datetime_combo,
            prompt_template_entry,
            prompt_color_button,
            preview_provider,
        )
        update_preview()
        self.update_terminal_split_preview(
            split_preview_line, split_separator_color_button, split_separator_thickness_spin, split_preview_provider
        )
        font_combo.connect("changed", update_preview)
        font_size_spin.connect("value-changed", update_preview)
        foreground_button.connect("notify::rgba", update_preview)
        background_button.connect("notify::rgba", update_preview)
        prompt_enabled.connect("toggled", update_preview)
        prompt_datetime_combo.connect("changed", update_preview)
        prompt_template_entry.connect("changed", update_preview)
        prompt_color_button.connect("notify::rgba", update_preview)
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
            prompt_enabled,
            prompt_datetime_combo,
            prompt_template_entry,
            prompt_color_button,
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
        prompt_enabled: Gtk.CheckButton,
        prompt_datetime_combo: Gtk.ComboBoxText,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
        provider: Gtk.CssProvider,
    ) -> None:
        font_family = self.selected_terminal_font_family(font_combo)
        font_size = int(font_size_spin.get_value())
        foreground = foreground_button.get_rgba().to_string()
        background = background_button.get_rgba().to_string()
        preview.set_markup(
            combined_terminal_preview_markup(
                prompt_enabled=prompt_enabled.get_active(),
                prompt_template=prompt_template_entry.get_text(),
                prompt_datetime_id=prompt_datetime_combo.get_active_id() or "none",
                prompt_color=rgba_to_hex(prompt_color_button.get_rgba()),
                command_text=self.t("terminal_preview_command"),
                output_text=self.t("terminal_preview_output"),
                ansi_palette=self.store.data.terminal.ansi_palette,
            )
        )
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
        prompt_enabled: Gtk.CheckButton,
        prompt_datetime_combo: Gtk.ComboBoxText,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
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
                    prompt_enabled=prompt_enabled.get_active(),
                    prompt_template=prompt_template_with_datetime(
                        prompt_template_entry.get_text(),
                        prompt_datetime_combo.get_active_id() or "none",
                    ),
                    prompt_color=rgba_to_hex(prompt_color_button.get_rgba()),
                )
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.apply_terminal_settings_to_open_tabs()
            self.install_tree_styles()
            self.toast_label.set_label(self.t("terminal_settings_saved"))
        dialog.destroy()
