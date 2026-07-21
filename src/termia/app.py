#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from .config_actions import ConfigActionsMixin
from .connection_history_view import ConnectionHistoryViewMixin
from .connection_dialogs import ConnectionDialogsMixin
from .constants import (
    APP_ID,
    DATA_FILE,
)
from .i18n import translate_key
from .keybindings import keybinding_matches
from .main_menu import MainMenuMixin
from .preferences import PreferencesMixin
from .stores import ConnectionStore
from .sidebar import SidebarMixin
from .statistics_view import StatisticsViewMixin
from .styles import build_application_css
from .tabs import TabsMixin
from .terminal_menus import TerminalMenusMixin
from .terminal_sessions import TerminalSessionsMixin
from .ui_state import RowObject, TerminalSession


class TermiaWindow(
    ConfigActionsMixin,
    ConnectionDialogsMixin,
    MainMenuMixin,
    PreferencesMixin,
    SidebarMixin,
    ConnectionHistoryViewMixin,
    StatisticsViewMixin,
    TerminalMenusMixin,
    TerminalSessionsMixin,
    TabsMixin,
    Gtk.ApplicationWindow,
):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Termia")
        self.set_default_size(1000, 620)
        if hasattr(self, "set_handle_menubar_accel"):
            self.set_handle_menubar_accel(False)

        self.store = ConnectionStore(DATA_FILE)
        if self.store.read_only:
            self.set_title(f"Termia ({self.t('read_only_badge')})")
        self.apply_app_theme()
        self.install_tree_styles()
        self.selected: RowObject | None = None
        self.selected_tree_widget: Gtk.Widget | None = None
        self.group_expanded_state: dict[str, bool] = {}
        self.collapse_groups_on_startup = True
        self.tree_widgets: dict[tuple[str, str], Gtk.Widget] = {}
        self.active_context_popover: Gtk.Popover | None = None
        self.open_tabs: dict[str, TerminalSession] = {}
        self.run_connections = 0
        self.stats_save_id: int | None = None
        self.close_confirmation_pending = False
        self.connect("close-request", self.on_main_window_close_request)
        self.connect("destroy", lambda *_args: self.store.close())

        self.toast_label = Gtk.Label()
        self.toast_label.add_css_class("dim-label")

        self._build_ui()
        if self.store.recovery_messages:
            self.toast_label.set_label(
                self.t("config_file_recovered").format(path=self.store.recovery_messages[0])
            )
        elif self.store.read_only:
            self.toast_label.set_label(self.t("read_only_mode_enabled"))
        self.set_sidebar_visible(self.store.data.app.show_sidebar_on_startup)
        self.refresh_list()
        if self.store.encryption_locked:
            self.toast_label.set_label(self.t("connections_locked"))
            GLib.idle_add(self.request_unlock_connections)
        elif self.store.data.app.open_local_terminal_on_startup:
            GLib.idle_add(self.open_startup_local_terminal)

    def open_startup_local_terminal(self) -> bool:
        if not self.open_tabs:
            self.on_open_local_terminal(None)
        return GLib.SOURCE_REMOVE

    def t(self, key: str) -> str:
        return translate_key(key, self.store.data.app.language)

    def ensure_writable(self) -> bool:
        if self.store.encryption_locked:
            self.toast_label.set_label(self.t("connections_locked"))
            self.request_unlock_connections()
            return False
        if not self.store.read_only:
            return True
        self.toast_label.set_label(self.t("read_only_mode_enabled"))
        return False

    def configure_write_action(self, widget: Gtk.Widget) -> Gtk.Widget:
        if self.store.read_only or self.store.encryption_locked:
            widget.set_sensitive(False)
            widget.set_tooltip_text(
                self.t("connections_locked_tooltip")
                if self.store.encryption_locked
                else self.t("read_only_mode_tooltip")
            )
        return widget

    def request_unlock_connections(self) -> bool:
        dialog = Gtk.Dialog(title=self.t("unlock_connections_title"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(420, -1)
        dialog.add_button(self.t("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.t("unlock"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        detail = Gtk.Label(label=self.t("unlock_connections_detail"))
        detail.set_xalign(0)
        detail.set_wrap(True)
        content.append(detail)

        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        password_entry.connect("activate", lambda _entry: dialog.response(Gtk.ResponseType.OK))
        content.append(password_entry)

        error = Gtk.Label(label=self.store.encryption_error)
        error.set_xalign(0)
        error.set_wrap(True)
        error.add_css_class("error")
        content.append(error)

        dialog.connect("response", self.on_unlock_connections_response, password_entry, error)
        dialog.present()
        password_entry.grab_focus()
        return GLib.SOURCE_REMOVE

    def on_unlock_connections_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        password_entry: Gtk.PasswordEntry,
        error: Gtk.Label,
    ) -> None:
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            self.toast_label.set_label(self.t("connections_locked"))
            return
        if self.store.unlock_connections(password_entry.get_text()):
            dialog.destroy()
            self.apply_app_theme()
            self.refresh_list()
            self.toast_label.set_label(self.t("connections_unlocked"))
            if self.store.data.app.open_local_terminal_on_startup:
                GLib.idle_add(self.open_startup_local_terminal)
            return
        error.set_label(self.t("unlock_connections_failed"))
        password_entry.set_text("")
        password_entry.grab_focus()

    def on_main_window_close_request(self, _window: Gtk.Window) -> bool:
        if not self.store.data.app.confirm_close_app:
            self.save_history_before_close()
            self.save_statistics_before_close()
            return False
        if self.close_confirmation_pending:
            return True
        self.close_confirmation_pending = True
        dialog = Gtk.AlertDialog(message=self.t("close_app"), detail=self.t("close_app_confirm"))
        dialog.set_buttons([self.t("cancel"), self.t("close_app")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_main_window_close_confirmed, dialog)
        return True

    def on_main_window_close_confirmed(
        self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, _data: Gtk.AlertDialog
    ) -> None:
        self.close_confirmation_pending = False
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 1:
            self.save_history_before_close()
            self.save_statistics_before_close()
            application = self.get_application()
            if application is not None:
                application.quit()

    def apply_app_theme(self) -> None:
        settings = Gtk.Settings.get_default()
        if settings is None:
            return
        theme = self.store.data.app.theme
        settings.set_property("gtk-application-prefer-dark-theme", theme == "dark")

    def install_tree_styles(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        gtk_settings = Gtk.Settings.get_default()
        prefer_dark = bool(
            gtk_settings.get_property("gtk-application-prefer-dark-theme")
        ) if gtk_settings is not None else False
        menu_bg = "#3a3a3a" if self.store.data.app.theme == "dark" or prefer_dark else "#f6f6f6"
        terminal_settings = self.store.data.terminal
        provider = Gtk.CssProvider()
        provider.load_from_data(
            build_application_css(
                menu_bg,
                terminal_settings.split_separator_color,
                terminal_settings.split_separator_thickness,
            )
        )
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        window_keys = Gtk.EventControllerKey.new()
        window_keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        window_keys.connect("key-pressed", self.on_window_key_pressed)
        self.add_controller(window_keys)

        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        toggle_sidebar = Gtk.Button(icon_name="sidebar-hide-symbolic")
        self.toggle_sidebar_button = toggle_sidebar
        toggle_sidebar.set_tooltip_text(self.t("servers"))
        toggle_sidebar.connect("clicked", self.on_toggle_sidebar)
        header.pack_start(toggle_sidebar)

        new_tab_button = Gtk.Button(icon_name="tab-new-symbolic")
        self.new_tab_button = new_tab_button
        new_tab_button.set_tooltip_text(self.t("new_tab"))
        new_tab_button.connect("clicked", self.on_open_local_terminal)
        header.pack_start(new_tab_button)

        menu_button = Gtk.MenuButton()
        self.main_menu_button = menu_button
        menu_button.set_tooltip_text(self.t("main_menu"))
        menu_button.set_popover(self.build_main_menu())
        menu_button.set_child(Gtk.Image.new_from_icon_name("open-menu-symbolic"))
        header.pack_start(menu_button)

        self.read_only_badge = Gtk.Label(label=self.t("read_only_badge"))
        self.read_only_badge.add_css_class("dim-label")
        self.read_only_badge.add_css_class("termia-read-only-badge")
        self.read_only_badge.set_visible(self.store.read_only)
        header.pack_end(self.read_only_badge)

        body = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_position(280)
        body.set_wide_handle(True)
        self.body = body
        self.sidebar_visible = True
        self.sidebar_width = 280
        root.append(body)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar.set_size_request(120, -1)
        sidebar.set_margin_top(12)
        sidebar.set_margin_bottom(12)
        sidebar.set_margin_start(12)
        sidebar.set_margin_end(12)
        self.sidebar = sidebar
        body.set_start_child(sidebar)
        body.set_resize_start_child(False)
        body.set_shrink_start_child(True)
        body.set_resize_end_child(True)
        body.set_shrink_end_child(False)

        sidebar_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_group = Gtk.Button(icon_name="folder-new-symbolic")
        self.add_group_button = add_group
        add_group.set_tooltip_text(self.t("new_group"))
        add_group.connect("clicked", self.on_add_group)
        self.configure_write_action(add_group)
        add_server = Gtk.Button(icon_name="list-add-symbolic")
        self.add_server_button = add_server
        add_server.set_tooltip_text(self.t("new_server"))
        add_server.connect("clicked", self.on_add_server)
        self.configure_write_action(add_server)
        add_local_terminal = Gtk.Button(icon_name="utilities-terminal-symbolic")
        self.add_local_terminal_button = add_local_terminal
        add_local_terminal.set_tooltip_text(self.t("new_local_terminal"))
        add_local_terminal.connect("clicked", self.on_add_local_terminal)
        self.configure_write_action(add_local_terminal)
        expand_all = Gtk.Button(icon_name="pan-down-symbolic")
        self.expand_all_button = expand_all
        expand_all.set_tooltip_text(self.t("expand_all"))
        expand_all.connect("clicked", lambda _button: self.set_all_groups_expanded(True))
        collapse_all = Gtk.Button(icon_name="pan-up-symbolic")
        self.collapse_all_button = collapse_all
        collapse_all.set_tooltip_text(self.t("collapse_all"))
        collapse_all.connect("clicked", lambda _button: self.set_all_groups_expanded(False))
        sidebar_actions.append(add_group)
        sidebar_actions.append(add_server)
        sidebar_actions.append(add_local_terminal)
        sidebar_actions.append(expand_all)
        sidebar_actions.append(collapse_all)
        sidebar.append(sidebar_actions)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(self.t("filter_servers"))
        self.search_entry.connect("search-changed", lambda _entry: self.refresh_list())
        search_navigation_key = Gtk.EventControllerKey.new()
        search_navigation_key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        search_navigation_key.connect("key-pressed", self.on_sidebar_navigation_key_pressed)
        self.search_entry.add_controller(search_navigation_key)
        sidebar.append(self.search_entry)

        self.server_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.server_list.set_focusable(True)
        list_navigation_key = Gtk.EventControllerKey.new()
        list_navigation_key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        list_navigation_key.connect("key-pressed", self.on_sidebar_navigation_key_pressed)
        self.server_list.add_controller(list_navigation_key)

        scroller = Gtk.ScrolledWindow()
        self.server_scroller = scroller
        self.scroll_restore_id: int | None = None
        scroller.set_child(self.server_list)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        scroller.set_min_content_width(80)
        sidebar.append(scroller)

        self.summary_label = Gtk.Label()
        self.summary_label.set_xalign(0)
        self.summary_label.add_css_class("dim-label")
        sidebar.append(self.summary_label)

        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        detail.set_margin_top(0)
        detail.set_margin_bottom(0)
        detail.set_margin_start(0)
        detail.set_margin_end(0)
        detail.set_hexpand(True)
        detail.set_vexpand(True)
        body.set_end_child(detail)

        self.title_label = Gtk.Label(label=self.t("select_server"))
        self.title_label.set_xalign(0)
        self.title_label.add_css_class("title-2")

        self.info_label = Gtk.Label(label=self.t("empty_detail_hint"))
        self.info_label.set_xalign(0)
        self.info_label.set_wrap(True)

        self.session_tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.session_tab_bar.set_homogeneous(True)
        self.session_tab_bar.add_css_class("termia-session-tabs")
        self.session_tab_bar.set_hexpand(True)
        self.session_tab_bar.set_visible(False)
        tab_bar_drop = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        tab_bar_drop.set_preload(True)
        tab_bar_drop.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        tab_bar_drop.connect("motion", self.on_tab_bar_drop_motion)
        tab_bar_drop.connect("drop", self.on_tab_bar_drop)
        self.session_tab_bar.add_controller(tab_bar_drop)
        detail.append(self.session_tab_bar)

        self.terminal_stack = Gtk.Stack()
        self.terminal_stack.add_css_class("termia-terminal-stack")
        self.terminal_stack.set_hexpand(True)
        self.terminal_stack.set_vexpand(True)
        detail.append(self.terminal_stack)

    def on_window_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keybinding_matches(self.store.data.app.keybindings.get("filter_servers", ""), keyval, state):
            return self.focus_server_filter()
        return False

    def refresh_translated_chrome(self) -> None:
        self.toggle_sidebar_button.set_tooltip_text(self.t("servers"))
        self.new_tab_button.set_tooltip_text(self.t("new_tab"))
        self.main_menu_button.set_tooltip_text(self.t("main_menu"))
        self.main_menu_button.set_popover(self.build_main_menu())
        self.read_only_badge.set_label(self.t("read_only_badge"))
        if self.store.read_only:
            self.set_title(f"Termia ({self.t('read_only_badge')})")
        else:
            self.set_title("Termia")
        self.add_group_button.set_tooltip_text(self.t("new_group"))
        self.configure_write_action(self.add_group_button)
        self.add_server_button.set_tooltip_text(self.t("new_server"))
        self.configure_write_action(self.add_server_button)
        self.add_local_terminal_button.set_tooltip_text(self.t("new_local_terminal"))
        self.configure_write_action(self.add_local_terminal_button)
        self.expand_all_button.set_tooltip_text(self.t("expand_all"))
        self.collapse_all_button.set_tooltip_text(self.t("collapse_all"))
        self.search_entry.set_placeholder_text(self.t("filter_servers"))
        self.render_detail()


class TermiaApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = TermiaWindow(self)
        window.present()


def main() -> int:
    app = TermiaApp()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
