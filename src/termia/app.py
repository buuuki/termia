#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import signal
import subprocess
import time
from urllib.parse import unquote, urlparse

from pathlib import Path
from typing import Any
from uuid import uuid4

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Pango, Vte

from .config_actions import ConfigActionsMixin
from .connection_utils import (
    find_group,
    find_server,
    group_descendant_ids,
    group_path_labels,
)
from .constants import (
    APP_ID,
    APP_THEMES,
    DATA_FILE,
    PROMPT_PRESETS,
    TERMINAL_PALETTES,
)
from .i18n import LANGUAGES, TRANSLATIONS, detect_system_language
from .main_menu import MainMenuMixin
from .models import (
    DEFAULT_ANSI_PALETTE,
    Group,
    Server,
)
from .stores import ConnectionStore
from .sidebar import SidebarMixin
from .statistics_view import StatisticsViewMixin
from .styles import build_application_css
from .terminal_config import (
    build_local_prompt_shell_command,
    build_terminal_environment,
    parse_color,
    prompt_template_with_datetime,
    render_prompt_preview,
    rgba_to_hex,
    split_prompt_datetime_template,
)
from .ui_state import RowObject, TerminalSession


class TermiaWindow(ConfigActionsMixin, MainMenuMixin, SidebarMixin, StatisticsViewMixin, Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Termia")
        self.set_default_size(1000, 620)

        self.store = ConnectionStore(DATA_FILE)
        self.apply_app_theme()
        self.install_tree_styles()
        self.selected: RowObject | None = None
        self.selected_tree_widget: Gtk.Widget | None = None
        self.group_expanded_state: dict[str, bool] = {}
        self.collapse_groups_on_startup = True
        self.tree_widgets: dict[tuple[str, str], Gtk.Widget] = {}
        self.active_context_popover: Gtk.Popover | None = None
        self.model = Gio.ListStore(item_type=RowObject)
        self.open_tabs: dict[str, TerminalSession] = {}
        self.session_sequence = 0
        self.run_connections = 0
        self.run_commands = 0
        self.run_keystrokes = 0
        self.stats_save_id: int | None = None
        self.close_confirmation_pending = False
        self.connect("close-request", self.on_main_window_close_request)

        self.toast_label = Gtk.Label()
        self.toast_label.add_css_class("dim-label")

        self._build_ui()
        self.set_sidebar_visible(self.store.data.app.show_sidebar_on_startup)
        self.refresh_list()
        if self.store.data.app.open_local_terminal_on_startup:
            GLib.idle_add(self.open_startup_local_terminal)

    def open_startup_local_terminal(self) -> bool:
        if not self.open_tabs:
            self.on_open_local_terminal(None)
        return GLib.SOURCE_REMOVE

    def t(self, key: str) -> str:
        language = self.store.data.app.language
        return TRANSLATIONS.get(language, TRANSLATIONS["es"]).get(key, key)

    def on_main_window_close_request(self, _window: Gtk.Window) -> bool:
        if not self.store.data.app.confirm_close_app:
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
        provider = Gtk.CssProvider()
        provider.load_from_data(build_application_css(menu_bg))
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        toggle_sidebar = Gtk.Button(icon_name="sidebar-hide-symbolic")
        self.toggle_sidebar_button = toggle_sidebar
        toggle_sidebar.set_tooltip_text(self.t("servers"))
        toggle_sidebar.connect("clicked", self.on_toggle_sidebar)
        header.pack_start(toggle_sidebar)

        new_tab_button = Gtk.Button(icon_name="tab-new-symbolic")
        new_tab_button.set_tooltip_text(self.t("new_tab"))
        new_tab_button.connect("clicked", self.on_open_local_terminal)
        header.pack_start(new_tab_button)

        menu_button = Gtk.MenuButton()
        menu_button.set_tooltip_text(self.t("main_menu"))
        menu_button.set_popover(self.build_main_menu())
        menu_button.set_child(Gtk.Image.new_from_icon_name("open-menu-symbolic"))
        header.pack_start(menu_button)

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
        add_group.set_tooltip_text(self.t("new_group"))
        add_group.connect("clicked", self.on_add_group)
        add_server = Gtk.Button(icon_name="list-add-symbolic")
        add_server.set_tooltip_text(self.t("new_server"))
        add_server.connect("clicked", self.on_add_server)
        expand_all = Gtk.Button(icon_name="pan-down-symbolic")
        expand_all.set_tooltip_text(self.t("expand_all"))
        expand_all.connect("clicked", lambda _button: self.set_all_groups_expanded(True))
        collapse_all = Gtk.Button(icon_name="pan-up-symbolic")
        collapse_all.set_tooltip_text(self.t("collapse_all"))
        collapse_all.connect("clicked", lambda _button: self.set_all_groups_expanded(False))
        sidebar_actions.append(add_group)
        sidebar_actions.append(add_server)
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

        self.title_label = Gtk.Label(label="Selecciona un servidor")
        self.title_label.set_xalign(0)
        self.title_label.add_css_class("title-2")

        self.info_label = Gtk.Label(label="Crea grupos y servidores desde la barra superior.")
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

        self.update_actions()

    def on_open_local_terminal(self, _button: Gtk.Button) -> None:
        shell = os.environ.get("SHELL") or GLib.find_program_in_path("bash") or "/bin/sh"
        command = [shell]
        if self.store.data.terminal.prompt_enabled:
            bash_path = GLib.find_program_in_path("bash")
            if bash_path is not None:
                command = build_local_prompt_shell_command(self.store.data.terminal, bash_path)
        self.open_process_terminal_tab(self.local_directory_title(Path.home()), command, None, working_directory=str(Path.home()))

    def open_process_terminal_tab(
        self,
        title: str,
        command: list[str],
        server_id: str | None,
        envv: list[str] | None = None,
        working_directory: str | None = None,
    ) -> None:
        session_id = str(uuid4())
        tab_title = title
        terminal = Vte.Terminal()
        terminal.set_hexpand(True)
        terminal.set_vexpand(True)
        terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.ON)
        terminal.set_scrollback_lines(10000)
        self.apply_terminal_settings(terminal)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        status_label = Gtk.Label(label=self.t("connecting"))
        status_label.set_xalign(0)
        status_label.add_css_class("dim-label")
        timer_label = Gtk.Label(label="00:00:00")
        focus_button = Gtk.Button(label=self.t("hide_status_bar"))
        focus_button.add_css_class("termia-status-hide")
        focus_button.set_size_request(-1, 18)
        disconnect_button = Gtk.Button(label=self.t("disconnect"))
        disconnect_button.add_css_class("destructive-action")
        disconnect_button.add_css_class("termia-disconnect-button")
        disconnect_button.set_size_request(-1, 18)
        toolbar.set_visible(self.should_show_session_status_bar())
        toolbar.append(status_label)
        toolbar.append(focus_button)
        toolbar.append(Gtk.Box(hexpand=True))
        toolbar.append(timer_label)
        toolbar.append(disconnect_button)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(terminal)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.append(toolbar)
        page.append(scroller)
        page.set_hexpand(True)
        page.set_vexpand(True)

        tab_label = self.build_tab_label(tab_title, session_id, page)
        session = TerminalSession(
            id=session_id, server_id=server_id, title=tab_title, terminal=terminal, page=page,
            tab_label=tab_label, status_label=status_label, timer_label=timer_label,
            disconnect_button=disconnect_button, status_bar=toolbar,
            started_at=time.monotonic(),
        )
        focus_button.connect("clicked", self.on_hide_session_status_bar, session)
        disconnect_button.connect("clicked", self.on_request_disconnect_session, session)
        self.configure_terminal_interactions(terminal, session)
        self.open_tabs[session_id] = session
        self.add_session_to_main_view(session)
        self.update_local_session_directory_title(session)
        terminal.grab_focus()
        try:
            _ok, child_pid = terminal.spawn_sync(
                Vte.PtyFlags.DEFAULT, working_directory, command, envv or build_terminal_environment(self.store.data.terminal.ls_colors),
                GLib.SpawnFlags.DEFAULT, None, None, None,
            )
        except GLib.Error as exc:
            terminal.feed(f"No se pudo iniciar el proceso: {exc.message}\r\n".encode())
            status_label.set_label("Error")
            session.connected = False
            disconnect_button.set_sensitive(False)
            return
        session.child_pid = child_pid
        self.update_local_session_directory_title(session)
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_process_terminal_exited, session)
        status_label.set_label(f"{title} · PID {child_pid}")

    def on_process_terminal_exited(self, _terminal: Vte.Terminal, _status: int, session: TerminalSession) -> None:
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        if session.disconnect_requested:
            session.status_label.set_label(f"Desconectada: {session.title}")
            return
        if self.child_status_successful(_status) and self.store.data.app.close_tab_on_ssh_exit:
            self.close_tab(session.id, session.page, disconnect=False)
            self.toast_label.set_label(f"Sesion cerrada: {session.title}")
            return
        session.status_label.set_label(f"Cerrada: {session.title}")
        self.update_session_tab_title(session, f"{session.title} (cerrada)")

    def open_terminal_tab(self, server: Server) -> None:
        session_id = str(uuid4())
        tab_title = server.name
        terminal = Vte.Terminal()
        terminal.set_hexpand(True)
        terminal.set_vexpand(True)
        terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.ON)
        terminal.set_scrollback_lines(10000)
        self.apply_terminal_settings(terminal)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_top(0)
        toolbar.set_margin_bottom(0)
        toolbar.set_margin_start(4)
        toolbar.set_margin_end(4)

        status_label = Gtk.Label(label=self.t("connecting"))
        status_label.set_xalign(0)
        status_label.add_css_class("dim-label")
        timer_label = Gtk.Label(label="00:00:00")
        focus_button = Gtk.Button(label=self.t("hide_status_bar"))
        focus_button.add_css_class("termia-status-hide")
        focus_button.set_size_request(-1, 18)
        disconnect_button = Gtk.Button(label=self.t("disconnect"))
        disconnect_button.add_css_class("destructive-action")
        disconnect_button.add_css_class("termia-disconnect-button")
        disconnect_button.set_size_request(-1, 18)
        toolbar.set_visible(self.should_show_session_status_bar())

        toolbar.append(status_label)
        toolbar.append(focus_button)
        toolbar.append(Gtk.Box(hexpand=True))
        toolbar.append(timer_label)
        toolbar.append(disconnect_button)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(terminal)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.append(toolbar)
        page.append(scroller)
        page.set_hexpand(True)
        page.set_vexpand(True)

        tab_label = self.build_tab_label(tab_title, session_id, page)
        session = TerminalSession(
            id=session_id,
            server_id=server.id,
            title=tab_title,
            terminal=terminal,
            page=page,
            tab_label=tab_label,
            status_label=status_label,
            timer_label=timer_label,
            disconnect_button=disconnect_button,
            status_bar=toolbar,
            started_at=time.monotonic(),
        )
        focus_button.connect("clicked", self.on_hide_session_status_bar, session)
        disconnect_button.connect("clicked", self.on_request_disconnect_session, session)
        self.configure_terminal_interactions(terminal, session)
        self.open_tabs[session_id] = session
        self.add_session_to_main_view(session)

        self.start_ssh_session(server, session)

    def start_ssh_session(self, server: Server, session: TerminalSession) -> None:
        terminal = session.terminal
        session.started_at = time.monotonic()
        session.duration_recorded = False
        session.disconnect_requested = False
        session.pending_reconnect = False
        session.child_pid = None
        session.connected = True
        session.disconnect_button.set_sensitive(True)
        session.status_label.set_label(self.t("connecting"))

        ssh_path = GLib.find_program_in_path("ssh")
        if ssh_path is None:
            terminal.feed(b"No se encontro el cliente ssh en el PATH.\r\n")
            session.status_label.set_label("Sin ssh")
            self.mark_session_for_reconnect(session, server, "No se encontro ssh en el PATH")
            return

        ssh_target = f"{server.user}@{server.host}"
        command = [ssh_path, "-p", str(server.port)]
        if server.public_key:
            command.extend(["-i", str(Path(server.public_key).expanduser())])
        command.append(ssh_target)
        envv = build_terminal_environment(self.store.data.terminal.ls_colors, server.password)
        use_sshpass = bool(server.password)
        if server.password and not self.has_known_host_key(server.host, server.port):
            use_sshpass = False
            message = self.t("ssh_fingerprint_manual")
            terminal.feed(f"{message}\r\n\r\n".encode())
            self.toast_label.set_label(message)
        if use_sshpass:
            sshpass_path = GLib.find_program_in_path("sshpass")
            if sshpass_path is None:
                terminal.feed(b"No se encontro sshpass. Instala sshpass o deja la contrasena vacia.\r\n")
                session.status_label.set_label("Sin sshpass")
                self.mark_session_for_reconnect(session, server, "No se encontro sshpass")
                return
            command = [sshpass_path, "-e", *command]
        terminal.feed(f"Conectando: {' '.join(command)}\r\n\r\n".encode())
        terminal.grab_focus()
        try:
            _ok, child_pid = terminal.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                None,
                command,
                envv,
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                None,
            )
        except GLib.Error as exc:
            terminal.feed(f"No se pudo iniciar ssh: {exc.message}\r\n".encode())
            session.status_label.set_label("Error")
            self.mark_session_for_reconnect(session, server, f"No se pudo iniciar ssh para {server.name}")
            return

        session.child_pid = child_pid
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_terminal_exited, server, session)
        self.record_connection(server.id)
        session.status_label.set_label(f"{server.name} · PID {child_pid}")
        self.toast_label.set_label(f"Sesion abierta: {session.title}")

    def mark_session_for_reconnect(self, session: TerminalSession, server: Server, toast: str) -> None:
        session.connected = False
        session.pending_reconnect = True
        session.disconnect_button.set_sensitive(False)
        self.toast_label.set_label(toast)
        prompt = f"  {self.t('reconnect_prompt')}  "
        session.terminal.feed(f"\r\n\x1b[1;30;48;2;255;213;79m{prompt}\x1b[0m\r\n".encode())
        self.update_session_tab_title(session, f"{session.title} (error)")

    def reconnect_session(self, session: TerminalSession) -> None:
        if not session.pending_reconnect or session.server_id is None:
            return
        server = find_server(self.store.data.servers, session.server_id)
        if server is None:
            session.pending_reconnect = False
            self.toast_label.set_label("No se encontro el servidor para reconectar")
            return
        session.pending_reconnect = False
        self.close_tab(session.id, session.page, disconnect=False)
        self.open_terminal_tab(server)

    def child_status_successful(self, status: int) -> bool:
        if status == 0:
            return True
        try:
            return os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
        except ValueError:
            return False

    def has_known_host_key(self, host: str, port: int) -> bool:
        ssh_keygen = GLib.find_program_in_path("ssh-keygen")
        if ssh_keygen is None:
            return False
        lookup_host = f"[{host}]:{port}" if port != 22 else host
        known_hosts_files = [Path.home() / ".ssh" / "known_hosts", Path.home() / ".ssh" / "known_hosts2"]
        for known_hosts in known_hosts_files:
            if not known_hosts.exists():
                continue
            result = subprocess.run(
                [ssh_keygen, "-F", lookup_host, "-f", str(known_hosts)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 0:
                return True
        return False

    def schedule_statistics_save(self) -> None:
        if self.stats_save_id is None:
            self.stats_save_id = GLib.timeout_add_seconds(30, self.flush_statistics)

    def save_statistics_before_close(self) -> None:
        for session in tuple(self.open_tabs.values()):
            self.record_session_duration(session)
        if self.stats_save_id is not None:
            GLib.source_remove(self.stats_save_id)
            self.stats_save_id = None
        self.store.save_statistics()

    def flush_statistics(self) -> bool:
        self.stats_save_id = None
        self.store.save_statistics()
        return GLib.SOURCE_REMOVE

    def save_statistics_now(self) -> None:
        if self.stats_save_id is not None:
            GLib.source_remove(self.stats_save_id)
            self.stats_save_id = None
        self.store.save_statistics()

    def record_connection(self, server_id: str) -> None:
        stats = self.store.data.statistics
        stats.connections += 1
        stats.server_connections[server_id] = stats.server_connections.get(server_id, 0) + 1
        self.run_connections += 1
        self.schedule_statistics_save()
        self.refresh_statistics_menu()

    def record_session_duration(self, session: TerminalSession) -> None:
        if session.duration_recorded or session.child_pid is None:
            return
        session.duration_recorded = True
        duration = max(0.0, time.monotonic() - session.started_at)
        stats = self.store.data.statistics
        stats.completed_sessions += 1
        stats.duration_total += duration
        stats.duration_min = duration if stats.duration_min is None else min(stats.duration_min, duration)
        stats.duration_max = max(stats.duration_max, duration)
        self.schedule_statistics_save()
        self.refresh_statistics_menu()

    def configure_terminal_interactions(self, terminal: Vte.Terminal, session: TerminalSession) -> None:
        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self.on_terminal_key_pressed, session)
        terminal.add_controller(keys)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_terminal_right_click, session, terminal)
        terminal.add_controller(right_click)

    def on_terminal_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
        session: TerminalSession,
    ) -> bool:
        stats = self.store.data.statistics
        session.keystrokes += 1
        stats.keystrokes += 1
        self.run_keystrokes += 1
        enter_keys = {Gdk.KEY_Return, Gdk.KEY_KP_Enter, getattr(Gdk, "KEY_ISO_Enter", Gdk.KEY_Return)}
        if keyval in enter_keys and session.pending_reconnect:
            self.schedule_statistics_save()
            self.reconnect_session(session)
            return True
        if keyval in enter_keys:
            session.commands += 1
            stats.commands += 1
            self.run_commands += 1
        self.schedule_statistics_save()
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (Gdk.KEY_Page_Up, Gdk.KEY_KP_Page_Up):
                self.move_terminal_tab_focus(session, -1)
                return True
            if keyval in (Gdk.KEY_Page_Down, Gdk.KEY_KP_Page_Down):
                self.move_terminal_tab_focus(session, 1)
                return True
            if keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
                self.change_terminal_font_size(1)
                return True
            if keyval in (Gdk.KEY_minus, Gdk.KEY_underscore, Gdk.KEY_KP_Subtract):
                self.change_terminal_font_size(-1)
                return True
        required_modifiers = Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.SHIFT_MASK
        if (
            self.store.data.app.sudo_password_shortcut
            and keyval in (Gdk.KEY_p, Gdk.KEY_P)
            and state & required_modifiers == required_modifiers
        ):
            self.send_saved_password(session)
            return True
        return False

    def move_terminal_tab_focus(self, session: TerminalSession, delta: int) -> None:
        sessions = self.visible_sessions_in_tab_order()
        if len(sessions) <= 1:
            return
        visible = self.terminal_stack.get_visible_child()
        current = 0
        for index, item in enumerate(sessions):
            if item.page is visible or item.id == session.id:
                current = index
                break
        self.set_active_session(sessions[(current + delta) % len(sessions)].id)

    def focus_current_terminal_page_later(self) -> bool:
        visible = self.terminal_stack.get_visible_child()
        for session in self.open_tabs.values():
            if session.page is visible:
                session.terminal.grab_focus()
                break
        return GLib.SOURCE_REMOVE

    def should_show_session_status_bar(self) -> bool:
        return self.store.data.app.show_session_status_bar

    def on_hide_session_status_bar(self, _button: Gtk.Button, session: TerminalSession) -> None:
        session.status_bar.set_visible(False)
        session.terminal.grab_focus()

    def apply_session_status_bar_visibility_to_open_tabs(self) -> None:
        visible = self.should_show_session_status_bar()
        for session in self.open_tabs.values():
            session.status_bar.set_visible(visible)

    def change_terminal_font_size(self, delta: int) -> None:
        settings = self.store.data.terminal
        new_size = max(6, min(settings.font_size + delta, 72))
        if new_size == settings.font_size:
            return
        self.store.update_terminal_settings(
            settings.font_family,
            new_size,
            settings.foreground,
            settings.background,
            settings.ls_colors,
        )
        self.apply_terminal_settings_to_open_tabs()
        self.toast_label.set_label(self.t("terminal_font_size_changed").format(size=new_size))

    def send_saved_password(self, session: TerminalSession) -> None:
        server = find_server(self.store.data.servers, session.server_id) if session.server_id is not None else None
        if not session.connected or server is None or not server.password:
            self.toast_label.set_label(self.t("sudo_password_unavailable"))
            return
        payload = server.password.encode()
        if self.store.data.app.sudo_password_enter:
            payload += b"\r"
        session.terminal.feed_child(payload)
        self.toast_label.set_label(self.t("sudo_password_sent"))

    def on_terminal_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(terminal)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("duplicate_tab"), lambda: self.duplicate_tab(popover, session))
        self.add_context_menu_item(menu, self.t("disconnect"), lambda: self.disconnect_from_terminal_menu(popover, session))
        if not session.status_bar.get_visible():
            self.add_context_menu_item(
                menu, self.t("show_session_status_bar"), lambda: self.show_session_status_bar_from_menu(popover, session)
            )
        self.add_context_menu_item(menu, self.t("copy"), lambda: self.copy_terminal_selection(popover, terminal))
        self.add_context_menu_item(menu, self.t("paste"), lambda: self.paste_terminal_clipboard(popover, terminal))
        self.add_context_menu_item(menu, self.t("configure_terminal"), lambda: self.configure_terminal_from_menu(popover))
        self.add_context_menu_item(menu, self.t("session_statistics"), lambda: self.show_session_statistics(popover, session))
        popover.set_child(menu)
        popover.popup()

    def show_session_status_bar_from_menu(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        session.status_bar.set_visible(True)
        session.terminal.grab_focus()

    def disconnect_from_terminal_menu(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        self.on_request_disconnect_session(None, session)

    def copy_terminal_selection(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.copy_clipboard_format(Vte.Format.TEXT)

    def paste_terminal_clipboard(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.paste_clipboard()

    def configure_terminal_from_menu(self, popover: Gtk.Popover) -> None:
        popover.popdown()
        self.on_terminal_settings(None)

    def show_session_statistics(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        server_connections = 0
        if session.server_id is not None:
            server_connections = self.store.data.statistics.server_connections.get(session.server_id, 0)
        dialog = Gtk.Dialog(title=self.t("session_statistics"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE, last=True)
        label = Gtk.Label(
            label=(
                f"{self.t('keystrokes')}: {session.keystrokes}\n"
                f"{self.t('commands')}: {session.commands}\n"
                f"{self.t('server_connections')}: {server_connections}"
            )
        )
        label.set_xalign(0)
        label.set_selectable(True)
        label.set_margin_top(12)
        label.set_margin_bottom(12)
        label.set_margin_start(12)
        label.set_margin_end(12)
        dialog.get_content_area().append(label)
        dialog.connect("response", lambda current, _response: current.destroy())
        dialog.present()

    def local_directory_title(self, path: Path) -> str:
        try:
            resolved = path.resolve()
            if resolved == Path.home().resolve():
                return "~"
            return str(resolved)
        except OSError:
            return str(path)

    def directory_title_from_uri(self, uri: str | None) -> str:
        if not uri:
            return ""
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            return ""
        path = Path(unquote(parsed.path))
        return self.local_directory_title(path)

    def local_session_cwd_title(self, session: TerminalSession) -> str:
        if session.child_pid is not None:
            try:
                return self.local_directory_title(Path(os.readlink(f"/proc/{session.child_pid}/cwd")))
            except OSError:
                pass
        return self.directory_title_from_uri(session.terminal.get_current_directory_uri())

    def update_local_session_directory_title(self, session: TerminalSession) -> None:
        if session.server_id is not None or session.title_locked:
            return
        title = self.local_session_cwd_title(session)
        if not title or title == session.last_directory_title:
            return
        session.last_directory_title = title
        session.title = title
        self.update_session_tab_title(session, title)

    def add_session_to_main_view(self, session: TerminalSession) -> None:
        self.terminal_stack.add_named(session.page, session.id)
        self.session_tab_bar.append(session.tab_label)
        self.update_session_tab_bar_visibility()
        self.set_active_session(session.id)

    def visible_sessions_in_tab_order(self) -> list[TerminalSession]:
        sessions_by_label = {
            session.tab_label: session
            for session in self.open_tabs.values()
            if session.detached_window is None
        }
        ordered: list[TerminalSession] = []
        child = self.session_tab_bar.get_first_child()
        while child is not None:
            session = sessions_by_label.get(child)
            if session is not None:
                ordered.append(session)
            child = child.get_next_sibling()
        return ordered

    def set_active_session(self, session_id: str) -> None:
        session = self.open_tabs.get(session_id)
        if session is None or session.detached_window is not None:
            return
        self.terminal_stack.set_visible_child(session.page)
        self.update_session_tab_states()
        session.terminal.grab_focus()

    def update_session_tab_states(self) -> None:
        visible_page = self.terminal_stack.get_visible_child()
        for session in self.open_tabs.values():
            session.tab_label.remove_css_class("active")
            if visible_page is session.page and session.detached_window is None:
                session.tab_label.add_css_class("active")

    def remove_session_from_main_view(self, session: TerminalSession) -> None:
        if session.detached_window is None:
            parent = session.tab_label.get_parent()
            if parent is self.session_tab_bar:
                self.session_tab_bar.remove(session.tab_label)
            try:
                self.terminal_stack.remove(session.page)
            except Exception:
                pass
        self.update_session_tab_states()
        self.update_session_tab_bar_visibility()

    def update_session_tab_bar_visibility(self) -> None:
        visible_sessions = [session for session in self.open_tabs.values() if session.detached_window is None]
        self.session_tab_bar.set_visible(len(visible_sessions) > 1)

    def focus_available_session_after_close(self, closed_session_id: str) -> None:
        for session in self.visible_sessions_in_tab_order():
            if session.id != closed_session_id:
                self.set_active_session(session.id)
                return

    def update_session_tab_title(self, session: TerminalSession, title: str) -> None:
        child = session.tab_label.get_first_child()
        if isinstance(child, Gtk.Label):
            child.set_label(title)
            return
        if isinstance(child, Gtk.Box):
            label = child.get_first_child()
            if isinstance(label, Gtk.Label):
                label.set_label(title)

    def apply_terminal_settings(self, terminal: Vte.Terminal) -> None:
        settings = self.store.data.terminal
        font_family = self.resolved_terminal_font_family(settings.font_family)
        font = Pango.FontDescription(f"{font_family} {settings.font_size}")
        foreground = parse_color(settings.foreground, "#f2f2f2")
        background = parse_color(settings.background, "#101010")
        palette_values = settings.ansi_palette or DEFAULT_ANSI_PALETTE
        palette = [parse_color(color, fallback) for color, fallback in zip(palette_values, DEFAULT_ANSI_PALETTE)]
        terminal.set_font(font)
        terminal.set_colors(foreground, background, palette)

    def apply_terminal_settings_to_open_tabs(self) -> None:
        for session in self.open_tabs.values():
            self.apply_terminal_settings(session.terminal)

    def update_session_timer(self, session: TerminalSession) -> bool:
        if not session.connected:
            return GLib.SOURCE_REMOVE
        elapsed = int(time.monotonic() - session.started_at)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        session.timer_label.set_label(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.update_local_session_directory_title(session)
        return GLib.SOURCE_CONTINUE

    def build_tab_label(self, title: str, session_id: str, page: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.add_css_class("termia-tab-label")
        box.set_hexpand(True)
        box.set_can_target(True)
        box.set_margin_start(0)
        box.set_margin_end(0)
        label = Gtk.Label(label=title)
        label.add_css_class("termia-tab-title")
        label.set_hexpand(True)
        label.set_single_line_mode(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_width_chars(1)
        label.set_max_width_chars(36)
        label.set_tooltip_text(title)
        label.set_can_target(False)
        label.set_margin_start(4)
        label.set_margin_end(4)
        close_button = Gtk.Button(icon_name="window-close-symbolic")
        close_button.add_css_class("termia-tab-close")
        close_button.set_has_frame(False)
        close_button.set_tooltip_text(self.t("close_tab"))
        close_button.connect("clicked", self.on_request_close_tab, session_id, page)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_tab_left_press, session_id)
        box.add_controller(left_click)
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self.on_tab_drag_prepare, session_id, box)
        drag_source.connect("drag-begin", self.on_tab_drag_begin, session_id, box)
        drag_source.connect("drag-end", self.on_tab_drag_end, session_id)
        box.add_controller(drag_source)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_tab_right_click, session_id, box)
        box.add_controller(right_click)
        box.append(label)
        box.append(close_button)
        return box

    def on_tab_left_press(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        session_id: str,
    ) -> None:
        self.set_active_session(session_id)

    def on_tab_drag_prepare(
        self,
        _source: Gtk.DragSource,
        _x: float,
        _y: float,
        session_id: str,
        _tab: Gtk.Widget,
    ) -> Gdk.ContentProvider | None:
        if session_id not in self.open_tabs:
            return None
        return Gdk.ContentProvider.new_for_value(session_id)

    def on_tab_drag_begin(
        self,
        source: Gtk.DragSource,
        _drag: Gdk.Drag,
        session_id: str,
        tab: Gtk.Widget,
    ) -> None:
        self.set_active_session(session_id)
        self.tab_drag_session_id = session_id
        tab.add_css_class("dragging")
        source.set_icon(Gtk.WidgetPaintable.new(tab), tab.get_allocated_width() // 2, tab.get_allocated_height() // 2)

    def on_tab_drag_end(
        self,
        _source: Gtk.DragSource,
        _drag: Gdk.Drag,
        _delete_data: bool,
        session_id: str,
    ) -> None:
        session = self.open_tabs.get(session_id)
        if session is not None:
            session.tab_label.remove_css_class("dragging")
        self.tab_drag_session_id = None

    def on_tab_bar_drop_motion(self, target: Gtk.DropTarget, x: float, _y: float) -> Gdk.DragAction:
        self.reorder_dragged_tab_at_bar_x(target, x)
        return Gdk.DragAction.MOVE

    def on_tab_bar_drop(self, target: Gtk.DropTarget, dragged_session_id: str, x: float, _y: float) -> bool:
        self.reorder_dragged_tab_at_bar_x(target, x, dragged_session_id)
        dragged = self.open_tabs.get(dragged_session_id)
        if dragged is not None:
            self.set_active_session(dragged.id)
        return True

    def reorder_dragged_tab_at_bar_x(
        self,
        target: Gtk.DropTarget,
        pointer_x: float,
        dragged_session_id: str | None = None,
    ) -> None:
        dragged_session_id = dragged_session_id or getattr(self, "tab_drag_session_id", None) or target.get_value()
        if not isinstance(dragged_session_id, str):
            return
        dragged = self.open_tabs.get(dragged_session_id)
        if dragged is None or dragged.detached_window is not None:
            return
        sessions = self.visible_sessions_in_tab_order()
        if len(sessions) <= 1:
            return
        try:
            dragged_index = sessions.index(dragged)
        except ValueError:
            return

        previous_sibling = dragged.tab_label.get_prev_sibling()
        for index, session in enumerate(sessions):
            if session.id == dragged_session_id:
                continue
            width = session.tab_label.get_allocated_width()
            ok, start = session.tab_label.compute_point(
                self.session_tab_bar, Graphene.Point().init(0, 0)
            )
            if not ok or pointer_x < start.x or pointer_x > start.x + width:
                continue

            if index < dragged_index:
                threshold = start.x + width * 0.8
                previous_sibling = session.tab_label.get_prev_sibling() if pointer_x < threshold else session.tab_label
            else:
                threshold = start.x + width * 0.2
                previous_sibling = session.tab_label if pointer_x > threshold else session.tab_label.get_prev_sibling()
            break

        if dragged.tab_label.get_prev_sibling() is previous_sibling:
            return
        self.session_tab_bar.reorder_child_after(dragged.tab_label, previous_sibling)
        self.update_session_tab_states()

    def on_tab_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        session_id: str,
        parent: Gtk.Widget,
    ) -> None:
        session = self.open_tabs.get(session_id)
        if session is None:
            return
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(parent)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("duplicate_tab"), lambda: self.duplicate_tab(popover, session))
        self.add_context_menu_item(menu, self.t("detach_tab"), lambda: self.detach_tab(popover, session))
        self.add_context_menu_item(menu, self.t("rename_tab"), lambda: self.show_rename_tab_dialog(popover, session))
        popover.set_child(menu)
        popover.popup()

    def duplicate_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        if session.server_id is not None:
            server = find_server(self.store.data.servers, session.server_id)
            if server is not None:
                self.open_terminal_tab(server)
            return
        self.on_open_local_terminal(None)

    def detach_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        if session.detached_window is not None:
            return
        self.remove_session_from_main_view(session)
        self.focus_available_session_after_close(session.id)
        window = Gtk.Window(title=session.title, transient_for=self)
        window.set_default_size(860, 520)
        window.set_child(session.page)
        session.detached_window = window
        self.update_session_tab_bar_visibility()
        window.connect("close-request", self.on_detached_window_close, session)
        window.present()

    def on_detached_window_close(self, window: Gtk.Window, session: TerminalSession) -> bool:
        window.set_child(None)
        session.detached_window = None
        if session.id in self.open_tabs:
            self.add_session_to_main_view(session)
        return False

    def show_rename_tab_dialog(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        dialog = Gtk.Dialog(title=self.t("rename_tab"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        entry = Gtk.Entry(text=session.title)
        entry.set_margin_top(12)
        entry.set_margin_bottom(12)
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        entry.connect("activate", lambda _entry: dialog.response(Gtk.ResponseType.OK))
        dialog.get_content_area().append(entry)
        dialog.connect("response", self.on_rename_tab_response, entry, session)
        dialog.present()

    def on_rename_tab_response(
        self, dialog: Gtk.Dialog, response: Gtk.ResponseType, entry: Gtk.Entry, session: TerminalSession
    ) -> None:
        title = entry.get_text().strip()
        if response == Gtk.ResponseType.OK and title:
            session.title = title
            session.title_locked = True
            self.update_session_tab_title(session, title)
        dialog.destroy()

    def on_request_disconnect_session(self, _button: Gtk.Button, session: TerminalSession) -> None:
        if not session.connected:
            return
        if not self.store.data.app.confirm_disconnect:
            self.disconnect_session(session)
            return
        self.confirm_session_action(
            session,
            "Desconectar sesion",
            f"Quieres desconectar {session.title}?",
            "Desconectar",
            lambda: self.disconnect_session(session),
        )

    def disconnect_session(self, session: TerminalSession) -> None:
        if not session.connected:
            return
        session.disconnect_requested = True
        if session.child_pid is not None:
            try:
                os.kill(session.child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError:
                session.terminal.feed(b"No se pudo enviar SIGTERM al proceso ssh.\r\n")
                self.toast_label.set_label(f"No se pudo desconectar {session.title}")
                return
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        session.status_label.set_label(f"Desconectada: {session.title}")
        session.terminal.feed(b"\r\nSesion desconectada.\r\n")
        self.update_session_tab_title(session, f"{session.title} (desconectada)")
        self.toast_label.set_label(f"Sesion desconectada: {session.title}")
        if self.store.data.app.close_tab_on_disconnect:
            self.close_tab(session.id, session.page, disconnect=False)

    def confirm_session_action(
        self,
        session: TerminalSession,
        title: str,
        message: str,
        confirm_label: str,
        on_confirm: Any,
    ) -> None:
        dialog = Gtk.AlertDialog(message=title, detail=message)
        dialog.set_buttons(["Cancelar", confirm_label])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_confirm_session_action, (dialog, session, on_confirm))

    def on_confirm_session_action(
        self,
        _source: Gtk.AlertDialog,
        result: Gio.AsyncResult,
        data: tuple[Gtk.AlertDialog, TerminalSession, Any],
    ) -> None:
        dialog, session, on_confirm = data
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 1:
            on_confirm()

    def on_terminal_exited(
        self,
        _terminal: Vte.Terminal,
        _status: int,
        server: Server,
        session: TerminalSession,
    ) -> None:
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        if session.disconnect_requested:
            session.status_label.set_label(f"Desconectada: {session.title}")
            self.toast_label.set_label(f"Sesion desconectada: {session.title}")
            return
        if self.child_status_successful(_status):
            if self.store.data.app.close_tab_on_ssh_exit:
                self.close_tab(session.id, session.page, disconnect=False)
                self.toast_label.set_label(f"Sesion cerrada: {server.name}")
                return
            session.status_label.set_label(f"Cerrada: {session.title}")
            self.update_session_tab_title(session, f"{session.title} (cerrada)")
            self.toast_label.set_label(f"Sesion cerrada: {server.name}")
            return
        session.status_label.set_label(f"Error: {session.title}")
        self.mark_session_for_reconnect(session, server, f"Fallo de conexion: {server.name}")

    def on_request_close_tab(self, _button: Gtk.Button, session_id: str, page: Gtk.Widget) -> None:
        session = self.open_tabs.get(session_id)
        if session and session.page == page and session.connected:
            if not self.store.data.app.confirm_disconnect:
                self.close_tab(session_id, page, disconnect=True)
                return
            detail = self.t("close_ssh_session_confirm") if session.server_id is not None else self.t("close_local_session_confirm")
            self.confirm_session_action(
                session,
                self.t("close_session_title"),
                detail,
                self.t("close"),
                lambda: self.close_tab(session_id, page, disconnect=True),
            )
            return
        self.close_tab(session_id, page, disconnect=False)

    def close_tab(self, session_id: str, page: Gtk.Widget, disconnect: bool) -> None:
        session = self.open_tabs.get(session_id)
        if disconnect and session and session.page == page and session.connected:
            self.disconnect_session(session)
            session = self.open_tabs.get(session_id)
        if session is None:
            return
        if session.detached_window is not None:
            window = session.detached_window
            session.detached_window = None
            window.set_child(None)
            window.destroy()
        else:
            self.remove_session_from_main_view(session)
        self.open_tabs.pop(session_id, None)
        self.update_session_tab_bar_visibility()
        self.focus_available_session_after_close(session_id)

    def on_app_preferences(self, _button: Gtk.Button) -> None:
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
        for theme_id, label in APP_THEMES.items():
            theme_combo.append(theme_id, label)
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
        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("theme"), theme_combo),
            (self.t("language"), language_combo),
            ("", close_tab_on_disconnect),
            ("", close_tab_on_ssh_exit),
            ("", open_local_terminal_on_startup),
            ("", show_sidebar_on_startup),
            ("", show_session_status_bar),
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
            sudo_password_shortcut, sudo_password_enter
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
    ) -> None:
        if response == Gtk.ResponseType.OK:
            previous_language = self.store.data.app.language
            self.store.update_app_settings(
                theme_combo.get_active_id() or "system",
                language_combo.get_active_id() or detect_system_language(),
                close_tab_on_disconnect.get_active(),
                confirm_disconnect.get_active(),
                confirm_close_app.get_active(),
                sudo_password_shortcut.get_active(),
                sudo_password_enter.get_active(),
                close_tab_on_ssh_exit.get_active(),
                open_local_terminal_on_startup.get_active(),
                show_sidebar_on_startup.get_active(),
                show_session_status_bar.get_active(),
            )
            self.apply_app_theme()
            self.install_tree_styles()
            self.apply_session_status_bar_visibility_to_open_tabs()
            self.set_sidebar_visible(self.store.data.app.show_sidebar_on_startup)
            self.collapse_groups_on_startup = True
            self.group_expanded_state = {group.id: False for group in self.store.data.groups}
            self.group_expanded_state["__ungrouped__"] = False
            self.refresh_list()
            if previous_language != self.store.data.app.language:
                self.toast_label.set_label(self.t("restart_language"))
        dialog.destroy()

    def on_terminal_settings(self, _button: Gtk.Button) -> None:
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
        foreground_button.set_rgba(parse_color(settings.foreground, "#f2f2f2"))
        foreground_button.set_title("Foreground")

        background_button = Gtk.ColorButton()
        background_button.set_rgba(parse_color(settings.background, "#101010"))
        background_button.set_title("Background")

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
        )
        dialog.present()

    def on_prompt_settings(self, _button: Gtk.Button) -> None:
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
        prompt_color_button.set_rgba(parse_color(settings.prompt_color, "#8ae234"))
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
        foreground_button.set_rgba(parse_color(foreground, "#f2f2f2"))
        background_button.set_rgba(parse_color(background, "#101010"))

    def on_prompt_preset_clicked(
        self,
        _button: Gtk.Button,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
        template: str,
        color: str,
    ) -> None:
        prompt_template_entry.set_text(template)
        prompt_color_button.set_rgba(parse_color(color, "#8ae234"))

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
            self.store.update_prompt_settings(
                prompt_enabled.get_active(),
                prompt_template_with_datetime(
                    prompt_template_entry.get_text(), prompt_datetime_combo.get_active_id() or "none"
                ),
                rgba_to_hex(prompt_color_button.get_rgba()),
            )
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
    ) -> None:
        if response == Gtk.ResponseType.OK:
            self.store.update_terminal_settings(
                self.selected_terminal_font_family(font_combo),
                int(font_size_spin.get_value()),
                foreground_button.get_rgba().to_string(),
                background_button.get_rgba().to_string(),
            )
            self.apply_terminal_settings_to_open_tabs()
            self.toast_label.set_label(self.t("terminal_settings_saved"))
        dialog.destroy()

    def show_group_dialog(self, group: Group | None = None) -> None:
        dialog = Gtk.Dialog(title=self.t("edit_group") if group else self.t("new_group"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(360, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        entry = Gtk.Entry()
        entry.set_placeholder_text(self.t("name"))
        parent_combo = Gtk.ComboBoxText()
        parent_combo.append("", self.t("no_parent_group"))
        excluded_ids = group_descendant_ids(self.store.data.groups, group.id) | {group.id} if group else set()
        for candidate, path_label in group_path_labels(self.store.data.groups):
            if candidate.id not in excluded_ids:
                parent_combo.append(candidate.id, path_label)
        parent_combo.set_active_id(group.parent_id if group and group.parent_id not in excluded_ids else "")
        if group:
            entry.set_text(group.name)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.attach(Gtk.Label(label=self.t("name"), xalign=0), 0, 0, 1, 1)
        grid.attach(entry, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=self.t("parent_group"), xalign=0), 0, 1, 1, 1)
        grid.attach(parent_combo, 1, 1, 1, 1)
        entry.set_hexpand(True)
        parent_combo.set_hexpand(True)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.append(grid)

        dialog.connect("response", self.on_group_dialog_response, entry, parent_combo, group)
        dialog.present()

    def on_group_dialog_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        entry: Gtk.Entry,
        parent_combo: Gtk.ComboBoxText,
        group: Group | None,
    ) -> None:
        name = entry.get_text().strip()
        parent_id = parent_combo.get_active_id() or None
        if response == Gtk.ResponseType.OK and name:
            if group:
                self.store.update_group(group.id, name, parent_id)
            else:
                self.store.add_group(name, parent_id)
            self.refresh_list()
        dialog.destroy()

    def build_form_label(self, label_text: str, required: bool = False) -> Gtk.Label:
        label = Gtk.Label()
        label.set_xalign(0)
        if required:
            escaped = GLib.markup_escape_text(label_text)
            label.set_markup(f"{escaped} <span foreground='#c01c28'><b>*</b></span>")
        else:
            label.set_text(label_text)
        return label

    def build_required_hint(self) -> Gtk.Label:
        label = Gtk.Label()
        label.set_xalign(0)
        label.set_markup(
            f"<span size='small' foreground='#c01c28'><i>{GLib.markup_escape_text(self.t('required_field'))}</i></span>"
        )
        return label

    def show_server_dialog(self, server: Server | None = None) -> None:
        dialog = Gtk.Dialog(title=self.t("edit_server") if server else self.t("new_server"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        name_entry = Gtk.Entry()
        host_entry = Gtk.Entry()
        user_entry = Gtk.Entry()
        port_spin = Gtk.SpinButton.new_with_range(1, 65535, 1)
        group_combo = Gtk.ComboBoxText()
        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        public_key_entry = Gtk.Entry()
        for widget in (name_entry, host_entry, user_entry, port_spin, group_combo, password_entry, public_key_entry):
            widget.set_hexpand(True)
            widget.set_size_request(260, -1)

        group_combo.append("", self.t("no_group"))
        for group, path_label in group_path_labels(self.store.data.groups):
            group_combo.append(group.id, path_label)
        group_combo.set_active_id("")

        if server:
            name_entry.set_text(server.name)
            host_entry.set_text(server.host)
            user_entry.set_text(server.user)
            port_spin.set_value(server.port)
            group_combo.set_active_id(server.group_id or "")
            password_entry.set_text(server.password)
            public_key_entry.set_text(server.public_key)
        else:
            port_spin.set_value(22)

        rows: list[tuple[str, Gtk.Widget, bool]] = [
            (self.t("name"), name_entry, True),
            (self.t("host"), host_entry, True),
            (self.t("ssh_user"), user_entry, True),
            (self.t("ssh_port"), port_spin, False),
            (self.t("group"), group_combo, False),
            (self.t("password"), password_entry, False),
            (self.t("public_key"), public_key_entry, False),
        ]
        for index, (label_text, widget, required) in enumerate(rows):
            grid.attach(self.build_form_label(label_text, required), 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)
        grid.attach(self.build_required_hint(), 1, len(rows), 1, 1)

        dialog.get_content_area().append(grid)
        warning = Gtk.Label()
        warning.set_markup(f"<i>{GLib.markup_escape_text(self.t('password_warning'))}</i>")
        warning.set_wrap(True)
        warning.set_xalign(0)
        warning.set_margin_start(16)
        warning.set_margin_end(16)
        warning.set_margin_bottom(14)
        warning.add_css_class("warning")
        dialog.get_content_area().append(warning)
        dialog.connect(
            "response",
            self.on_server_dialog_response,
            {
                "name": name_entry,
                "host": host_entry,
                "user": user_entry,
                "port": port_spin,
                "group": group_combo,
                "password": password_entry,
                "public_key": public_key_entry,
            },
            server,
        )
        dialog.present()

    def on_server_dialog_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        widgets: dict[str, Any],
        server: Server | None,
    ) -> None:
        name = widgets["name"].get_text().strip()
        host = widgets["host"].get_text().strip()
        user = widgets["user"].get_text().strip()
        port = int(widgets["port"].get_value())
        group_id = widgets["group"].get_active_id() or None
        password = widgets["password"].get_text()
        public_key = widgets["public_key"].get_text().strip()

        if response == Gtk.ResponseType.OK:
            if not name or not host or not user:
                self.toast_label.set_label(self.t("server_required_fields"))
                for widget in (widgets["name"], widgets["host"], widgets["user"]):
                    if not widget.get_text().strip():
                        widget.grab_focus()
                        break
                return
            if server:
                self.store.update_server(server.id, name, host, user, port, group_id, password, public_key)
            else:
                self.store.add_server(name, host, user, port, group_id, password, public_key)
            self.refresh_list()
        dialog.destroy()


class TermiaApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)

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
