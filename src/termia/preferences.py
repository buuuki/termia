# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .config_io import CONNECTION_STORAGE_OBFUSCATED, CONNECTION_STORAGE_PLAIN
from .constants import (
    APP_THEMES,
    DEFAULT_PROMPT_COLOR,
    DEFAULT_TERMINAL_BACKGROUND,
    DEFAULT_TERMINAL_FOREGROUND,
    DEFAULT_SPLIT_SEPARATOR_COLOR,
    DEFAULT_SPLIT_SEPARATOR_THICKNESS,
    PROMPT_PRESETS,
    TERMINAL_PALETTES,
)
from .i18n import LANGUAGES, detect_system_language
from .keybindings import (
    DEFAULT_KEYBINDINGS,
    KEYBINDING_ACTIONS,
    keybinding_from_event,
    keybinding_label,
    normalize_keybinding,
)
from .models import AppSettings
from .stores import ReadOnlyStoreError
from .terminal_config import (
    parse_color,
    prompt_template_with_datetime,
    render_prompt_preview,
    rgba_to_hex,
    split_prompt_datetime_template,
)


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
        if not self._capturing:
            return
        self._capturing = False
        self.update_label()

    def on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: object,
    ) -> bool:
        if not self._capturing:
            return False
        accelerator = keybinding_from_event(keyval, state)
        if not accelerator:
            return True
        self._accelerator = accelerator
        self._capturing = False
        self.update_label()
        return True


class PreferencesMixin:
    def on_app_preferences(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("general"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(380, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        theme_combo = Gtk.ComboBoxText()
        for theme_id in APP_THEMES:
            theme_combo.append(theme_id, self.t(f"theme_{theme_id}"))
        theme_combo.set_active_id(self.store.data.app.theme)

        language_combo = Gtk.ComboBoxText()
        for language_id, label in LANGUAGES.items():
            language_combo.append(language_id, label)
        language_combo.set_active_id(self.store.data.app.language)

        close_tab_on_disconnect = Gtk.CheckButton(label=self.t("close_tab_on_disconnect"))
        close_tab_on_disconnect.set_active(self.store.data.app.close_tab_on_disconnect)
        close_tab_on_disconnect.set_halign(Gtk.Align.START)
        close_tab_on_ssh_exit = Gtk.CheckButton(label=self.t("close_tab_on_ssh_exit"))
        close_tab_on_ssh_exit.set_active(self.store.data.app.close_tab_on_ssh_exit)
        close_tab_on_ssh_exit.set_halign(Gtk.Align.START)
        open_local_terminal_on_startup = Gtk.CheckButton(label=self.t("open_local_terminal_on_startup"))
        open_local_terminal_on_startup.set_active(self.store.data.app.open_local_terminal_on_startup)
        open_local_terminal_on_startup.set_halign(Gtk.Align.START)
        show_sidebar_on_startup = Gtk.CheckButton(label=self.t("show_sidebar_on_startup"))
        show_sidebar_on_startup.set_active(self.store.data.app.show_sidebar_on_startup)
        show_sidebar_on_startup.set_halign(Gtk.Align.START)
        show_session_status_bar = Gtk.CheckButton(label=self.t("show_session_status_bar"))
        show_session_status_bar.set_active(self.store.data.app.show_session_status_bar)
        show_session_status_bar.set_halign(Gtk.Align.START)
        confirm_disconnect = Gtk.CheckButton(label=self.t("confirm_disconnect"))
        confirm_disconnect.set_active(self.store.data.app.confirm_disconnect)
        confirm_disconnect.set_halign(Gtk.Align.START)
        confirm_close_app = Gtk.CheckButton(label=self.t("confirm_close_app"))
        confirm_close_app.set_active(self.store.data.app.confirm_close_app)
        confirm_close_app.set_halign(Gtk.Align.START)
        sudo_password_shortcut = Gtk.CheckButton(label=self.t("sudo_password_shortcut"))
        sudo_password_shortcut.set_active(self.store.data.app.sudo_password_shortcut)
        sudo_password_shortcut.set_halign(Gtk.Align.START)
        sudo_password_enter = Gtk.CheckButton(label=self.t("sudo_password_enter"))
        sudo_password_enter.set_active(self.store.data.app.sudo_password_enter)
        sudo_password_enter.set_halign(Gtk.Align.START)
        sudo_password_enter.set_sensitive(sudo_password_shortcut.get_active())
        sudo_password_shortcut.connect(
            "toggled", lambda current: sudo_password_enter.set_sensitive(current.get_active())
        )
        statistics_enabled = Gtk.CheckButton(label=self.t("statistics_enabled"))
        statistics_enabled.set_active(self.store.data.app.statistics_enabled)
        statistics_enabled.set_halign(Gtk.Align.START)
        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("theme"), theme_combo),
            (self.t("language"), language_combo),
            ("", close_tab_on_disconnect),
            ("", close_tab_on_ssh_exit),
            ("", open_local_terminal_on_startup),
            ("", show_sidebar_on_startup),
            ("", show_session_status_bar),
            ("", statistics_enabled),
            ("", confirm_disconnect),
            ("", confirm_close_app),
            ("", sudo_password_shortcut),
            ("", sudo_password_enter),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            widget.set_hexpand(True)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)

        dialog.get_content_area().append(grid)
        dialog.connect(
            "response", self.on_app_preferences_response, theme_combo, language_combo,
            close_tab_on_disconnect, close_tab_on_ssh_exit, open_local_terminal_on_startup,
            show_sidebar_on_startup, show_session_status_bar, confirm_disconnect, confirm_close_app,
            sudo_password_shortcut, sudo_password_enter, statistics_enabled
        )
        dialog.present()

    def on_app_preferences_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        theme_combo: Gtk.ComboBoxText,
        language_combo: Gtk.ComboBoxText,
        close_tab_on_disconnect: Gtk.CheckButton,
        close_tab_on_ssh_exit: Gtk.CheckButton,
        open_local_terminal_on_startup: Gtk.CheckButton,
        show_sidebar_on_startup: Gtk.CheckButton,
        show_session_status_bar: Gtk.CheckButton,
        confirm_disconnect: Gtk.CheckButton,
        confirm_close_app: Gtk.CheckButton,
        sudo_password_shortcut: Gtk.CheckButton,
        sudo_password_enter: Gtk.CheckButton,
        statistics_enabled: Gtk.CheckButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            previous_language = self.store.data.app.language
            try:
                self.store.update_app_settings(
                    AppSettings(
                        theme=theme_combo.get_active_id() or "system",
                        language=language_combo.get_active_id() or detect_system_language(),
                        close_tab_on_disconnect=close_tab_on_disconnect.get_active(),
                        close_tab_on_ssh_exit=close_tab_on_ssh_exit.get_active(),
                        open_local_terminal_on_startup=open_local_terminal_on_startup.get_active(),
                        show_sidebar_on_startup=show_sidebar_on_startup.get_active(),
                        show_session_status_bar=show_session_status_bar.get_active(),
                        confirm_disconnect=confirm_disconnect.get_active(),
                        confirm_close_app=confirm_close_app.get_active(),
                        sudo_password_shortcut=sudo_password_shortcut.get_active(),
                        sudo_password_enter=sudo_password_enter.get_active(),
                        connection_storage_mode=self.store.data.app.connection_storage_mode,
                        statistics_enabled=statistics_enabled.get_active(),
                        keybindings=self.store.data.app.keybindings,
                    )
                )
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.apply_app_theme()
            self.install_tree_styles()
            self.apply_session_status_bar_visibility_to_open_tabs()
            self.set_sidebar_visible(self.store.data.app.show_sidebar_on_startup)
            self.collapse_groups_on_startup = True
            self.group_expanded_state = {group.id: False for group in self.store.data.groups}
            self.group_expanded_state["__ungrouped__"] = False
            self.refresh_list()
            if previous_language != self.store.data.app.language:
                self.refresh_translated_chrome()
                self.toast_label.set_label(self.t("language_settings_saved"))
        dialog.destroy()


    def on_security_settings(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("security"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        storage_combo = Gtk.ComboBoxText()
        storage_combo.append(CONNECTION_STORAGE_PLAIN, self.t("connection_storage_plain"))
        storage_combo.append(CONNECTION_STORAGE_OBFUSCATED, self.t("connection_storage_obfuscated"))
        storage_combo.set_active_id(self.store.data.app.connection_storage_mode)
        storage_combo.set_hexpand(True)

        label = Gtk.Label(label=self.t("connection_storage_mode"))
        label.set_xalign(0)
        grid.attach(label, 0, 0, 1, 1)
        grid.attach(storage_combo, 1, 0, 1, 1)
        content.append(grid)

        warning = Gtk.Label(label=self.t("connection_storage_obfuscated_warning"))
        warning.set_xalign(0)
        warning.set_wrap(True)
        warning.add_css_class("dim-label")
        content.append(warning)

        dialog.connect("response", self.on_security_settings_response, storage_combo)
        dialog.present()

    def on_security_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        storage_combo: Gtk.ComboBoxText,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            try:
                self.store.update_connection_storage_mode(storage_combo.get_active_id() or CONNECTION_STORAGE_PLAIN)
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.toast_label.set_label(self.t("security_settings_saved"))
        dialog.destroy()

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
                self.t("keybinding_disabled"),
                self.t("keybinding_capture_prompt"),
                self.t("keybinding_clear"),
            )
            rows.append((action, row))
            grid.attach(label, 0, index, 1, 1)
            grid.attach(row, 1, index, 1, 1)
        content.append(grid)

        dialog.connect("response", self.on_keybindings_settings_response, rows)
        dialog.present()

    def on_keybindings_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        rows: list[tuple[str, KeybindingCaptureRow]],
    ) -> None:
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
        split_separator_color_button.set_rgba(
            parse_color(settings.split_separator_color, DEFAULT_SPLIT_SEPARATOR_COLOR)
        )
        split_separator_color_button.set_title(self.t("split_separator_color"))

        split_separator_thickness_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
        split_separator_thickness_spin.set_value(settings.split_separator_thickness or DEFAULT_SPLIT_SEPARATOR_THICKNESS)

        preview = Gtk.Label()
        preview.set_use_markup(True)
        preview.set_xalign(0)
        preview.set_margin_top(10)
        preview.set_margin_bottom(10)
        preview.set_margin_start(12)
        preview.set_margin_end(12)
        preview.set_css_classes(["terminal-preview"])

        palette_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for palette_name, (foreground, background) in TERMINAL_PALETTES.items():
            palette_button = Gtk.Button(label=palette_name)
            palette_button.connect(
                "clicked",
                self.on_terminal_palette_clicked,
                foreground_button,
                background_button,
                foreground,
                background,
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
        content.append(preview)

        self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button)
        font_combo.connect(
            "changed",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
        )
        font_size_spin.connect(
            "value-changed",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
        )
        foreground_button.connect(
            "notify::rgba",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
        )
        background_button.connect(
            "notify::rgba",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
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
        dialog.present()

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
            preset_button.connect(
                "clicked",
                self.on_prompt_preset_clicked,
                prompt_template_entry,
                prompt_color_button,
                template,
                color,
            )
            prompt_preset_box.append(preset_button)

        prompt_controls = (prompt_datetime_combo, prompt_template_entry, prompt_color_button, prompt_preset_box)
        for prompt_widget in prompt_controls:
            prompt_widget.set_sensitive(prompt_enabled.get_active())
        prompt_enabled.connect(
            "toggled",
            lambda current: [widget.set_sensitive(current.get_active()) for widget in prompt_controls],
        )

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

        content.append(grid)
        content.append(preview)

        self.update_prompt_preview(
            preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
        )
        prompt_enabled.connect(
            "toggled",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )
        prompt_datetime_combo.connect(
            "changed",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )
        prompt_template_entry.connect(
            "changed",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )
        prompt_color_button.connect(
            "notify::rgba",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )

        dialog.connect(
            "response",
            self.on_prompt_settings_response,
            prompt_enabled,
            prompt_datetime_combo,
            prompt_template_entry,
            prompt_color_button,
        )
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

    def terminal_font_families(self) -> list[str]:
        families = [
            family.get_name()
            for family in self.get_pango_context().list_families()
            if family.is_monospace()
        ]
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
    ) -> None:
        font_family = self.selected_terminal_font_family(font_combo)
        font_size = int(font_size_spin.get_value())
        foreground = foreground_button.get_rgba().to_string()
        background = background_button.get_rgba().to_string()
        preview.set_markup(GLib.markup_escape_text("usuario@servidor:~$ ssh ejemplo\nSalida de terminal"))
        css = (
            ".terminal-preview {"
            f"font-family: '{font_family}';"
            f"font-size: {font_size}pt;"
            f"color: {foreground};"
            f"background: {background};"
            "border-radius: 6px;"
            "}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            preview.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def update_prompt_preview(
        self,
        preview: Gtk.Label,
        prompt_enabled: Gtk.CheckButton,
        prompt_datetime_combo: Gtk.ComboBoxText,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
    ) -> None:
        command_markup = GLib.markup_escape_text("ssh ejemplo\nSalida de terminal")
        if prompt_enabled.get_active():
            prompt_text = render_prompt_preview(
                prompt_template_with_datetime(
                    prompt_template_entry.get_text(), prompt_datetime_combo.get_active_id() or "none"
                )
            )
            prompt_markup = GLib.markup_escape_text(prompt_text)
            prompt_color = rgba_to_hex(prompt_color_button.get_rgba())
            preview.set_markup(f'<span foreground="{prompt_color}">{prompt_markup}</span>{command_markup}')
        else:
            preview.set_markup(GLib.markup_escape_text("usuario@servidor:~$ ssh ejemplo\nSalida de terminal"))

        settings = self.store.data.terminal
        css = (
            ".terminal-preview {"
            f"font-family: '{settings.font_family}';"
            f"font-size: {settings.font_size}pt;"
            f"color: {settings.foreground};"
            f"background: {settings.background};"
            "border-radius: 6px;"
            "}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            preview.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
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
                    prompt_template_with_datetime(
                        prompt_template_entry.get_text(), prompt_datetime_combo.get_active_id() or "none"
                    ),
                    rgba_to_hex(prompt_color_button.get_rgba()),
                )
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.toast_label.set_label(self.t("prompt_settings_saved"))
        dialog.destroy()

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
                    self.selected_terminal_font_family(font_combo),
                    int(font_size_spin.get_value()),
                    foreground_button.get_rgba().to_string(),
                    background_button.get_rgba().to_string(),
                    split_separator_color_button.get_rgba().to_string(),
                    int(split_separator_thickness_spin.get_value()),
                )
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.apply_terminal_settings_to_open_tabs()
            self.install_tree_styles()
            self.toast_label.set_label(self.t("terminal_settings_saved"))
        dialog.destroy()
