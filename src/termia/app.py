#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import signal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from .config_actions import ConfigActionsMixin
from .connection_history_presenter import ConnectionHistoryPresenter
from .connection_history_view import ConnectionHistoryDialog
from .connection_dialogs import ConnectionDialogsMixin
from .constants import (
    APP_ID,
    DATA_FILE,
    INSTANCE_LOCK_FILE,
    SETTINGS_FILE,
    SESSION_SNAPSHOT_FILE,
    STATE_DIR,
)
from .debug import configure_debug_logging, log_event, log_startup_context, log_store_state
from .i18n import translate_key
from .keybindings import keybinding_matches
from .main_menu import MainMenuMixin
from .main_menu_actions import MainMenuActions
from .notifications import NOTIFICATION_ICONS, GroupedNotificationLabel, NotificationSeverity
from .preferences import PreferencesMixin
from .session_registry import SessionRegistry
from .session_snapshot import SessionSnapshotStore
from .stores import ConnectionStore
from .sidebar import SidebarMixin
from .statistics_presenter import StatisticsPresenter
from .statistics_view import StatisticsDialog
from .styles import build_application_css
from .tab_lifecycle_actions import TabLifecycleActions
from .tabs import TabsMixin
from .terminal_menus import TerminalMenusMixin
from .terminal_menu_actions import TerminalMenuActions
from .terminal_sessions import TerminalSessionsMixin
from .ui_state import RowObject

TOAST_VISIBLE_SECONDS = 5


def build_add_badged_icon(icon_name: str) -> Gtk.Overlay:
    overlay = Gtk.Overlay()

    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(16)
    overlay.set_child(icon)

    badge = Gtk.Image.new_from_icon_name("list-add-symbolic")
    badge.set_pixel_size(9)
    badge.set_halign(Gtk.Align.END)
    badge.set_valign(Gtk.Align.END)
    badge.add_css_class("termia-add-icon-badge")
    overlay.add_overlay(badge)
    return overlay


class TermiaWindow(
    ConfigActionsMixin,
    ConnectionDialogsMixin,
    MainMenuMixin,
    PreferencesMixin,
    SidebarMixin,
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
        self.session_snapshot_store = SessionSnapshotStore(
            SESSION_SNAPSHOT_FILE,
            read_only=self.store.read_only,
        )
        self.pending_session_snapshot = (
            self.session_snapshot_store.load()
            if self.store.data.app.restore_sessions_on_startup
            else []
        )
        if not self.store.read_only and not self.store.data.app.restore_sessions_on_startup:
            self.session_snapshot_store.clear()
        self.startup_restore_prompt_pending = False
        self.toast_messages: list[str] = []
        self.toast_severity = NotificationSeverity.INFORMATION
        self.toast_icon = Gtk.Image.new_from_icon_name(
            NOTIFICATION_ICONS[NotificationSeverity.INFORMATION]
        )
        self.toast_icon.set_pixel_size(18)
        self.toast_label = GroupedNotificationLabel()
        self.toast_label.set_notification_handler(self.show_toast)
        self.toast_label.add_css_class("dim-label")
        self.toast_label.set_wrap(True)
        self.toast_label.set_max_width_chars(80)
        self.toast_label.set_margin_top(10)
        self.toast_label.set_margin_bottom(10)
        self.toast_hide_id: int | None = None
        self.history_presenter = ConnectionHistoryPresenter(
            lambda: self.store.history_store.entries,
            self.t,
        )
        self.connection_history_dialog = ConnectionHistoryDialog(
            self,
            self.history_presenter,
            self.t,
            self.store.clear_history,
            self.configure_write_action,
            lambda message: self.toast_label.set_label(message),
        )
        if self.store.data.app.debug_enabled:
            configure_debug_logging(True)
        log_startup_context(
            lock_path=INSTANCE_LOCK_FILE,
            data_path=DATA_FILE,
            settings_path=SETTINGS_FILE,
            state_dir=STATE_DIR,
        )
        log_store_state(self.store)
        log_event("application.window_created", read_only=self.store.read_only)
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
        self.session_registry = SessionRegistry()
        self.run_connections = 0
        self.statistics_presenter = StatisticsPresenter(
            lambda: self.store.data.statistics,
            lambda: self.store.data.servers,
            lambda: self.run_connections,
            self.t,
        )
        self.statistics_dialog = StatisticsDialog(self, self.statistics_presenter, self.t)
        self.tab_lifecycle_actions = TabLifecycleActions(
            duplicate_session=self.duplicate_session,
            disconnect_session=self.disconnect_session,
            terminate_split_processes=self.terminate_split_processes,
            confirm_session_action=self.confirm_session_action,
        )
        self.main_menu_actions = MainMenuActions(
            general_preferences=lambda: self.on_app_preferences(None),
            terminal_settings=lambda: self.on_terminal_settings(None),
            keybinding_settings=lambda: self.on_keybindings_settings(None),
            security_settings=lambda: self.on_security_settings(None),
            statistics=self.statistics_dialog.show,
            connection_history=self.connection_history_dialog.show,
            data_locations=self.on_data_locations,
            export_config=self.on_export_config,
            import_config=self.on_import_config,
            import_asbru_config=self.on_import_asbru_config,
            clear_config=self.on_request_clear_config,
            help=lambda: self.on_help(None),
            about=lambda: self.on_about(None),
        )
        self.terminal_menu_actions = TerminalMenuActions(
            disconnect=self.disconnect_from_terminal_menu,
            toggle_status_bar=self.toggle_session_status_bar_from_menu,
            copy=self.copy_terminal_selection,
            paste=self.paste_terminal_clipboard,
            send_files=self.on_send_files_to_server,
            configure=self.configure_terminal_from_menu,
            session_statistics=self.show_session_statistics,
            split=self.split_terminal_from_menu,
            split_connection=self.show_split_connection_dialog,
            rename_tab=self.show_rename_tab_dialog,
            reattach_tab=self.reattach_tab,
            duplicate_tab=self.duplicate_tab,
            new_tab=self.new_tab_from_terminal_menu,
            close_tab=self.close_tab_from_terminal_menu,
        )
        self.stats_save_id: int | None = None
        self.close_confirmation_pending = False
        self.shutdown_in_progress = False
        self.connect("close-request", self.on_main_window_close_request)
        self.connect("destroy", lambda *_args: self.store.close())
        if hasattr(GLib, "unix_signal_add"):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.on_unix_termination_signal)

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
            self.request_unlock_connections()
        else:
            self.schedule_startup_restore_or_local()

    def schedule_startup_local_terminal(self) -> None:
        if self.store.data.app.open_local_terminal_on_startup:
            GLib.idle_add(self.open_startup_local_terminal)

    def schedule_startup_restore_or_local(self) -> None:
        if self.store.data.app.restore_sessions_on_startup and self.pending_session_snapshot:
            GLib.idle_add(self.prompt_restore_last_session)
        else:
            self.schedule_startup_local_terminal()

    def prompt_restore_last_session(self) -> bool:
        if self.startup_restore_prompt_pending or self.session_registry:
            return GLib.SOURCE_REMOVE
        self.startup_restore_prompt_pending = True
        dialog = Gtk.AlertDialog(
            message=self.t("restore_sessions_title"),
            detail=self.t("restore_sessions_detail").format(count=len(self.pending_session_snapshot)),
        )
        dialog.set_buttons([self.t("skip_restore_sessions"), self.t("restore_sessions")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)
        dialog.choose(self, None, self.on_restore_last_session_decided, dialog)
        return GLib.SOURCE_REMOVE

    def on_restore_last_session_decided(
        self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, _data: Gtk.AlertDialog
    ) -> None:
        self.startup_restore_prompt_pending = False
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        snapshot = self.pending_session_snapshot
        self.pending_session_snapshot = []
        self.session_snapshot_store.clear()
        if response == 1:
            self.restore_session_snapshot(snapshot)
        else:
            self.schedule_startup_local_terminal()

    def open_startup_local_terminal(self) -> bool:
        if not self.session_registry:
            self.on_open_local_terminal(None)
        return GLib.SOURCE_REMOVE

    def show_toast(
        self,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.INFORMATION,
    ) -> None:
        if not message:
            return
        self.toast_messages.append(message)
        self.toast_severity = max(self.toast_severity, severity)
        self.toast_icon.set_from_icon_name(NOTIFICATION_ICONS[self.toast_severity])
        self.toast_label.set_grouped_text("\n".join(self.toast_messages))
        if not hasattr(self, "toast_revealer"):
            return
        if self.toast_hide_id is not None:
            GLib.source_remove(self.toast_hide_id)
            self.toast_hide_id = None
        self.toast_revealer.set_reveal_child(True)
        self.toast_hide_id = GLib.timeout_add_seconds(
            TOAST_VISIBLE_SECONDS,
            self.hide_toast,
        )

    def hide_toast(self) -> bool:
        self.toast_hide_id = None
        self.toast_revealer.set_reveal_child(False)
        self.toast_messages.clear()
        self.toast_severity = NotificationSeverity.INFORMATION
        self.toast_icon.set_from_icon_name(
            NOTIFICATION_ICONS[NotificationSeverity.INFORMATION]
        )
        self.toast_label.set_grouped_text("")
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

    def configure_write_action(
        self,
        widget: Gtk.Widget,
        *,
        enabled_tooltip: str | None = None,
    ) -> Gtk.Widget:
        write_blocked = self.store.read_only or self.store.encryption_locked
        widget.set_sensitive(not write_blocked)
        widget.set_tooltip_text(
            (
                self.t("connections_locked_tooltip")
                if self.store.encryption_locked
                else self.t("read_only_mode_tooltip")
            )
            if write_blocked
            else enabled_tooltip
        )
        return widget

    def request_unlock_connections(self) -> bool:
        self.unlock_password_entry.set_text("")
        self.unlock_error_label.set_label(self.store.encryption_error)
        self.unlock_scrim.set_visible(True)
        self.unlock_panel.set_visible(True)
        self.main_root.set_sensitive(False)
        self.set_unlock_header_actions_sensitive(False)
        self.unlock_password_entry.grab_focus()
        return GLib.SOURCE_REMOVE

    def set_unlock_header_actions_sensitive(self, sensitive: bool) -> None:
        for control in (
            self.toggle_sidebar_button,
            self.new_tab_button,
            self.main_menu_button,
        ):
            control.set_sensitive(sensitive)

    def hide_unlock_panel(self) -> None:
        self.unlock_panel.set_visible(False)
        self.unlock_scrim.set_visible(False)
        self.main_root.set_sensitive(True)
        self.set_unlock_header_actions_sensitive(True)

    def on_unlock_connections_cancelled(self, _button: Gtk.Button | None = None) -> None:
        self.hide_unlock_panel()
        self.toast_label.set_label(self.t("connections_locked"))
        self.pending_session_snapshot = []
        self.schedule_startup_local_terminal()

    def on_unlock_connections_requested(self, _button: Gtk.Button | None = None) -> None:
        if self.store.unlock_connections(self.unlock_password_entry.get_text()):
            self.hide_unlock_panel()
            self.apply_app_theme()
            self.refresh_translated_chrome()
            self.refresh_list()
            self.toast_label.set_label(self.t("connections_unlocked"))
            snapshot_store = getattr(self, "session_snapshot_store", None)
            if snapshot_store is None:
                self.schedule_startup_local_terminal()
                return
            self.pending_session_snapshot = (
                snapshot_store.load()
                if self.store.data.app.restore_sessions_on_startup
                else []
            )
            self.schedule_startup_restore_or_local()
            return
        self.unlock_error_label.set_label(self.t("unlock_connections_failed"))
        self.unlock_password_entry.set_text("")
        self.unlock_password_entry.grab_focus()

    def focus_startup_control(self) -> None:
        if self.unlock_panel.get_visible():
            self.unlock_password_entry.grab_focus()

    def on_main_window_close_request(self, _window: Gtk.Window) -> bool:
        if self.shutdown_in_progress:
            return False
        if not self.store.data.app.confirm_close_app:
            self.begin_main_window_shutdown()
            return True
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
            self.begin_main_window_shutdown()

    def on_unix_termination_signal(self) -> bool:
        self.begin_main_window_shutdown()
        return GLib.SOURCE_REMOVE

    def begin_main_window_shutdown(self) -> None:
        if self.shutdown_in_progress:
            return
        self.shutdown_in_progress = True
        log_event("application.shutdown_started", sessions=len(self.session_registry.sessions()))
        self.save_session_snapshot_before_close()
        self.save_history_before_close()
        self.save_statistics_before_close()
        self.prepare_terminal_sessions_for_shutdown()
        self.terminate_open_terminal_processes()
        GLib.timeout_add(500, self.finish_main_window_shutdown)

    def save_session_snapshot_before_close(self) -> None:
        if self.store.read_only or not self.store.data.app.restore_sessions_on_startup:
            return
        from .workspace_layout import capture_workspace_tabs

        self.session_snapshot_store.save(
            capture_workspace_tabs(
                self.session_registry.sessions(),
                include_local_context=False,
            )
        )

    def finish_main_window_shutdown(self) -> bool:
        self.terminate_open_terminal_processes(force=True)
        log_event("application.shutdown_finished")
        application = self.get_application()
        if application is not None:
            application.quit()
        return GLib.SOURCE_REMOVE

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
        window_overlay = Gtk.Overlay()
        self.set_child(window_overlay)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_root = root
        window_overlay.set_child(root)

        window_keys = Gtk.EventControllerKey.new()
        window_keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        window_keys.connect("key-pressed", self.on_window_key_pressed)
        self.add_controller(window_keys)

        header = Gtk.HeaderBar()
        self.header = header
        self.set_titlebar(header)

        header_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_actions.set_margin_start(6)

        toggle_sidebar = Gtk.Button(icon_name="sidebar-hide-symbolic")
        self.toggle_sidebar_button = toggle_sidebar
        toggle_sidebar.set_tooltip_text(self.t("servers"))
        toggle_sidebar.connect("clicked", self.on_toggle_sidebar)
        header_actions.append(toggle_sidebar)

        new_tab_button = Gtk.Button(icon_name="tab-new-symbolic")
        self.new_tab_button = new_tab_button
        new_tab_button.set_tooltip_text(self.t("open_local_terminal_tooltip"))
        new_tab_button.connect("clicked", self.on_open_local_terminal)
        header_actions.append(new_tab_button)

        menu_button = Gtk.MenuButton()
        self.main_menu_button = menu_button
        menu_button.set_tooltip_text(self.t("main_menu"))
        menu_button.set_popover(self.build_main_menu(self.main_menu_actions))
        menu_button.set_child(Gtk.Image.new_from_icon_name("open-menu-symbolic"))
        header_actions.append(menu_button)
        header.pack_start(header_actions)

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
        add_group.connect("clicked", self.on_add_group)
        self.configure_write_action(
            add_group,
            enabled_tooltip=self.t("create_group_tooltip"),
        )
        add_server = Gtk.Button(icon_name="list-add-symbolic")
        self.add_server_button = add_server
        add_server.connect("clicked", self.on_add_server)
        self.configure_write_action(
            add_server,
            enabled_tooltip=self.t("create_ssh_connection_tooltip"),
        )
        add_local_terminal = Gtk.Button()
        add_local_terminal.set_child(build_add_badged_icon("utilities-terminal-symbolic"))
        self.add_local_terminal_button = add_local_terminal
        add_local_terminal.connect("clicked", self.on_add_local_terminal)
        self.configure_write_action(
            add_local_terminal,
            enabled_tooltip=self.t("create_local_terminal_profile_tooltip"),
        )
        save_workspace = Gtk.Button(icon_name="document-save-symbolic")
        self.save_workspace_button = save_workspace
        save_workspace.connect("clicked", self.on_save_workspace)
        self.configure_write_action(
            save_workspace,
            enabled_tooltip=self.t("save_workspace"),
        )
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
        sidebar_actions.append(save_workspace)
        sidebar_actions.append(expand_all)
        sidebar_actions.append(collapse_all)
        sidebar.append(sidebar_actions)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(self.t("filter_servers"))
        self.search_entry.connect("search-changed", lambda _entry: self.refresh_list())
        sidebar.append(self.search_entry)

        self.server_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.server_list.set_focusable(False)

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

        self.session_tab_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.session_tab_controls.add_css_class("termia-session-tab-controls")
        self.session_tab_controls.set_visible(False)

        self.session_tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.session_tab_bar.set_homogeneous(True)
        self.session_tab_bar.add_css_class("termia-session-tabs")
        self.session_tab_bar.set_hexpand(True)
        tab_bar_drop = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        tab_bar_drop.set_preload(True)
        tab_bar_drop.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        tab_bar_drop.connect("motion", self.on_tab_bar_drop_motion)
        tab_bar_drop.connect("drop", self.on_tab_bar_drop)
        self.session_tab_bar.add_controller(tab_bar_drop)

        self.session_tab_scroller = Gtk.ScrolledWindow()
        self.session_tab_scroller.add_css_class("termia-session-tab-scroller")
        self.session_tab_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.session_tab_scroller.set_overlay_scrolling(False)
        self.session_tab_scroller.set_propagate_natural_width(False)
        self.session_tab_scroller.set_min_content_width(0)
        self.session_tab_scroller.set_hexpand(True)
        self.session_tab_scroller.set_child(self.session_tab_bar)
        self.session_tab_scroller.get_hadjustment().connect(
            "changed", self.on_tab_scroll_adjustment_changed
        )
        self.session_tab_scroller.get_hadjustment().connect(
            "notify::page-size", self.on_tab_scroll_adjustment_changed
        )
        self.session_tab_scroller.get_hadjustment().connect(
            "notify::upper", self.on_tab_scroll_adjustment_changed
        )
        self.session_tab_controls.append(self.session_tab_scroller)

        self.tab_overflow_button = Gtk.MenuButton()
        self.tab_overflow_button.add_css_class("termia-tab-overflow-button")
        self.tab_overflow_button.add_css_class("flat")
        overflow_icon = Gtk.Image.new_from_icon_name("view-more-symbolic")
        overflow_icon.set_pixel_size(14)
        self.tab_overflow_button.set_child(overflow_icon)
        self.tab_overflow_button.set_tooltip_text(self.t("tab"))
        self.session_tab_controls.append(self.tab_overflow_button)
        detail.append(self.session_tab_controls)

        self.terminal_stack = Gtk.Stack()
        self.terminal_stack.add_css_class("termia-terminal-stack")
        self.terminal_stack.set_hexpand(True)
        self.terminal_stack.set_vexpand(True)
        detail.append(self.terminal_stack)
        self.rebuild_tab_overflow_popover()

        unlock_scrim = Gtk.Box()
        self.unlock_scrim = unlock_scrim
        unlock_scrim.set_halign(Gtk.Align.FILL)
        unlock_scrim.set_valign(Gtk.Align.FILL)
        unlock_scrim.set_hexpand(True)
        unlock_scrim.set_vexpand(True)
        unlock_scrim.set_visible(False)
        window_overlay.add_overlay(unlock_scrim)

        unlock_panel = Gtk.Frame()
        self.unlock_panel = unlock_panel
        unlock_panel.add_css_class("background")
        unlock_panel.add_css_class("card")
        unlock_panel.set_halign(Gtk.Align.CENTER)
        unlock_panel.set_valign(Gtk.Align.CENTER)
        unlock_panel.set_size_request(420, -1)
        unlock_panel.set_margin_top(20)
        unlock_panel.set_margin_bottom(20)
        unlock_panel.set_margin_start(20)
        unlock_panel.set_margin_end(20)
        unlock_panel.set_visible(False)

        unlock_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        unlock_content.set_margin_top(20)
        unlock_content.set_margin_bottom(20)
        unlock_content.set_margin_start(20)
        unlock_content.set_margin_end(20)
        unlock_panel.set_child(unlock_content)

        unlock_title = Gtk.Label(label=self.t("unlock_connections_title"))
        unlock_title.set_xalign(0)
        unlock_title.add_css_class("title-2")
        unlock_content.append(unlock_title)

        unlock_detail = Gtk.Label(label=self.t("unlock_connections_detail"))
        unlock_detail.set_xalign(0)
        unlock_detail.set_wrap(True)
        unlock_content.append(unlock_detail)

        unlock_password_entry = Gtk.PasswordEntry()
        self.unlock_password_entry = unlock_password_entry
        unlock_password_entry.set_show_peek_icon(True)
        unlock_password_entry.connect("activate", self.on_unlock_connections_requested)
        unlock_content.append(unlock_password_entry)

        unlock_error = Gtk.Label()
        self.unlock_error_label = unlock_error
        unlock_error.set_xalign(0)
        unlock_error.set_wrap(True)
        unlock_error.add_css_class("error")
        unlock_content.append(unlock_error)

        unlock_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        unlock_actions.set_halign(Gtk.Align.END)
        cancel_button = Gtk.Button(label=self.t("cancel"))
        cancel_button.connect("clicked", self.on_unlock_connections_cancelled)
        unlock_actions.append(cancel_button)
        unlock_button = Gtk.Button(label=self.t("unlock"))
        unlock_button.add_css_class("suggested-action")
        unlock_button.connect("clicked", self.on_unlock_connections_requested)
        unlock_actions.append(unlock_button)
        unlock_content.append(unlock_actions)
        window_overlay.add_overlay(unlock_panel)

        toast_revealer = Gtk.Revealer()
        self.toast_revealer = toast_revealer
        toast_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        toast_revealer.set_transition_duration(180)
        toast_revealer.set_halign(Gtk.Align.CENTER)
        toast_revealer.set_valign(Gtk.Align.END)
        toast_revealer.set_margin_bottom(18)
        toast_revealer.set_margin_start(18)
        toast_revealer.set_margin_end(18)
        toast_revealer.set_can_target(False)

        toast_frame = Gtk.Frame()
        toast_frame.add_css_class("background")
        toast_frame.add_css_class("card")
        toast_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        toast_content.set_margin_start(14)
        toast_content.set_margin_end(14)
        toast_content.prepend(self.toast_icon)
        toast_content.append(self.toast_label)
        toast_frame.set_child(toast_content)
        toast_revealer.set_child(toast_frame)
        window_overlay.add_overlay(toast_revealer)

    def on_window_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if self.unlock_panel.get_visible():
            if keyval == Gdk.KEY_Escape:
                self.on_unlock_connections_cancelled()
                return True
            return False
        keybindings = self.store.data.app.keybindings
        if keybinding_matches(keybindings.get("filter_servers", ""), keyval, state):
            return self.focus_server_filter()
        if keybinding_matches(keybindings.get("toggle_sidebar", ""), keyval, state):
            self.on_toggle_sidebar(None)
            return True
        if keybinding_matches(keybindings.get("toggle_main_menu", ""), keyval, state):
            return self.toggle_main_menu()
        if keybinding_matches(keybindings.get("new_local_terminal", ""), keyval, state):
            self.on_open_local_terminal(None)
            return True
        if keybinding_matches(keybindings.get("focus_next_region", ""), keyval, state):
            return self.cycle_main_focus(1)
        if keybinding_matches(keybindings.get("focus_previous_region", ""), keyval, state):
            return self.cycle_main_focus(-1)
        if self.sidebar_navigation_has_focus():
            return self.on_sidebar_navigation_key_pressed(_controller, keyval, _keycode, state)
        return False

    def toggle_main_menu(self) -> bool:
        popover = self.main_menu_button.get_popover()
        if popover is None:
            return False
        if popover.get_visible():
            popover.popdown()
        else:
            popover.popup()
        return True

    def cycle_main_focus(self, delta: int) -> bool:
        focused = self.get_focus()
        regions: list[tuple[Gtk.Widget, Gtk.Widget]] = []
        if self.sidebar_visible:
            regions.append((self.sidebar, self.search_entry))

        visible_page = self.terminal_stack.get_visible_child()
        active_session = next(
            (
                session
                for session in self.visible_sessions_in_tab_order()
                if session.page is visible_page
            ),
            None,
        )
        if active_session is not None:
            if self.session_tab_bar.get_visible():
                active_session.tab_label.set_focusable(True)
                regions.append((self.session_tab_bar, active_session.tab_label))
            terminal = (
                active_session.split_terminals[-1]
                if active_session.split_terminals
                else active_session.terminal
            )
            regions.append((self.terminal_stack, terminal))

        if not regions:
            return False

        current_index = next(
            (
                index
                for index, (region, _target) in enumerate(regions)
                if focused is region or (focused is not None and focused.is_ancestor(region))
            ),
            -1 if delta > 0 else 0,
        )
        target_index = (current_index + delta) % len(regions)
        regions[target_index][1].grab_focus()
        return True

    def refresh_translated_chrome(self) -> None:
        self.toggle_sidebar_button.set_tooltip_text(self.t("servers"))
        self.new_tab_button.set_tooltip_text(self.t("open_local_terminal_tooltip"))
        self.main_menu_button.set_tooltip_text(self.t("main_menu"))
        self.main_menu_button.set_popover(
            self.build_main_menu(self.main_menu_actions)
        )
        self.read_only_badge.set_label(self.t("read_only_badge"))
        if self.store.read_only:
            self.set_title(f"Termia ({self.t('read_only_badge')})")
        else:
            self.set_title("Termia")
        self.configure_write_action(
            self.add_group_button,
            enabled_tooltip=self.t("create_group_tooltip"),
        )
        self.configure_write_action(
            self.add_server_button,
            enabled_tooltip=self.t("create_ssh_connection_tooltip"),
        )
        self.configure_write_action(
            self.add_local_terminal_button,
            enabled_tooltip=self.t("create_local_terminal_profile_tooltip"),
        )
        self.configure_write_action(
            self.save_workspace_button,
            enabled_tooltip=self.t("save_workspace"),
        )
        self.expand_all_button.set_tooltip_text(self.t("expand_all"))
        self.collapse_all_button.set_tooltip_text(self.t("collapse_all"))
        self.search_entry.set_placeholder_text(self.t("filter_servers"))
        self.render_detail()


class TermiaApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self) -> None:
        window = self.props.active_window
        created = window is None
        if window is None:
            window = TermiaWindow(self)
        log_event("application.activated", window_created=created)
        window.present()
        if created:
            window.focus_startup_control()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Termia")
    parser.add_argument("--debug", action="store_true", help="enable diagnostic logging")
    args = parser.parse_args(argv)
    configure_debug_logging(args.debug)
    app = TermiaApp()
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
