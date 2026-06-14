# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from uuid import uuid4

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte

from .connection_utils import find_server
from .keybindings import keybinding_label, keybinding_matches
from .models import DEFAULT_ANSI_PALETTE, Server
from .terminal_config import (
    build_local_prompt_shell_command,
    build_terminal_environment,
    parse_color,
)
from .ui_state import TerminalSession


class TerminalSessionsMixin:
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
            message = self.t("local_terminal_start_failed").format(error=exc.message)
            retry_prompt = self.t("local_terminal_retry_prompt")
            terminal.feed(f"{message}\r\n{retry_prompt}\r\n".encode())
            status_label.set_label("Error")
            session.connected = False
            session.pending_reconnect = True
            disconnect_button.set_sensitive(False)
            self.update_session_tab_title(session, self.t("tab_error_title").format(title=session.title))
            self.toast_label.set_label(message)
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
            session.status_label.set_label(self.t("session_disconnected_status").format(title=session.title))
            return
        if self.child_status_successful(_status) and self.store.data.app.close_tab_on_ssh_exit:
            self.close_tab(session.id, session.page, disconnect=False)
            self.toast_label.set_label(self.t("local_terminal_closed").format(title=session.title))
            return
        session.status_label.set_label(self.t("session_closed_status").format(title=session.title))
        self.update_session_tab_title(session, self.t("tab_closed_title").format(title=session.title))

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
            message = self.t("ssh_missing")
            terminal.feed(f"{message}\r\n".encode())
            session.status_label.set_label(self.t("ssh_missing_status"))
            self.mark_session_for_reconnect(session, server, message)
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
                message = self.t("sshpass_missing")
                terminal.feed(f"{message}\r\n".encode())
                session.status_label.set_label(self.t("sshpass_missing_status"))
                self.mark_session_for_reconnect(session, server, message)
                return
            command = [sshpass_path, "-e", *command]
        terminal.feed(f"{self.t('ssh_connecting_command').format(command=' '.join(command))}\r\n\r\n".encode())
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
            message = self.t("ssh_start_failed").format(error=exc.message)
            terminal.feed(f"{message}\r\n".encode())
            session.status_label.set_label("Error")
            self.mark_session_for_reconnect(session, server, self.t("ssh_start_failed_toast").format(name=server.name))
            return

        session.child_pid = child_pid
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_terminal_exited, server, session)
        self.record_connection(server.id)
        session.status_label.set_label(f"{server.name} · PID {child_pid}")
        self.toast_label.set_label(self.t("session_opened").format(title=session.title))

    def mark_session_for_reconnect(self, session: TerminalSession, server: Server, toast: str) -> None:
        session.connected = False
        session.pending_reconnect = True
        session.disconnect_button.set_sensitive(False)
        self.toast_label.set_label(toast)
        prompt = f"  {self.t('reconnect_prompt')}  "
        session.terminal.feed(f"\r\n\x1b[1;30;48;2;255;213;79m{prompt}\x1b[0m\r\n".encode())
        self.update_session_tab_title(session, self.t("tab_error_title").format(title=session.title))

    def reconnect_session(self, session: TerminalSession) -> None:
        if not session.pending_reconnect or session.server_id is None:
            return
        server = find_server(self.store.data.servers, session.server_id)
        if server is None:
            session.pending_reconnect = False
            self.toast_label.set_label(self.t("server_reconnect_missing"))
            return
        session.pending_reconnect = False
        self.close_tab(session.id, session.page, disconnect=False)
        self.open_terminal_tab(server)

    def retry_local_terminal_session(self, session: TerminalSession) -> None:
        if not session.pending_reconnect or session.server_id is not None:
            return
        session.pending_reconnect = False
        self.close_tab(session.id, session.page, disconnect=False)
        self.on_open_local_terminal(None)

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
        if self.store.data.app.statistics_enabled and self.stats_save_id is None:
            self.stats_save_id = GLib.timeout_add_seconds(30, self.flush_statistics)

    def save_statistics_before_close(self) -> None:
        if not self.store.data.app.statistics_enabled:
            if self.stats_save_id is not None:
                GLib.source_remove(self.stats_save_id)
                self.stats_save_id = None
            return
        for session in tuple(self.open_tabs.values()):
            self.record_session_duration(session)
        if self.stats_save_id is not None:
            GLib.source_remove(self.stats_save_id)
            self.stats_save_id = None
        self.store.save_statistics()

    def flush_statistics(self) -> bool:
        self.stats_save_id = None
        if not self.store.data.app.statistics_enabled:
            return GLib.SOURCE_REMOVE
        self.store.save_statistics()
        return GLib.SOURCE_REMOVE

    def save_statistics_now(self) -> None:
        if self.stats_save_id is not None:
            GLib.source_remove(self.stats_save_id)
            self.stats_save_id = None
        if not self.store.data.app.statistics_enabled:
            return
        self.store.save_statistics()

    def record_connection(self, server_id: str) -> None:
        if not self.store.data.app.statistics_enabled:
            return
        stats = self.store.data.statistics
        stats.connections += 1
        stats.server_connections[server_id] = stats.server_connections.get(server_id, 0) + 1
        self.run_connections += 1
        self.schedule_statistics_save()
        self.refresh_statistics_menu()

    def record_session_duration(self, session: TerminalSession) -> None:
        if not self.store.data.app.statistics_enabled:
            return
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
        keys.connect("key-pressed", self.on_terminal_key_pressed, session, terminal)
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
        terminal: Vte.Terminal,
    ) -> bool:
        enter_keys = {Gdk.KEY_Return, Gdk.KEY_KP_Enter, getattr(Gdk, "KEY_ISO_Enter", Gdk.KEY_Return)}
        if keyval in enter_keys and session.pending_reconnect:
            if session.server_id is None:
                self.retry_local_terminal_session(session)
            else:
                self.reconnect_session(session)
            return True
        keybindings = self.store.data.app.keybindings
        if keybinding_matches(keybindings.get("copy", ""), keyval, state):
            terminal.copy_clipboard_format(Vte.Format.TEXT)
            return True
        if keybinding_matches(keybindings.get("paste", ""), keyval, state):
            terminal.paste_clipboard()
            return True
        if keybinding_matches(keybindings.get("previous_tab", ""), keyval, state):
            self.move_terminal_tab_focus(session, -1)
            return True
        if keybinding_matches(keybindings.get("next_tab", ""), keyval, state):
            self.move_terminal_tab_focus(session, 1)
            return True
        if keybinding_matches(keybindings.get("font_increase", ""), keyval, state):
            self.change_terminal_font_size(1)
            return True
        if keybinding_matches(keybindings.get("font_decrease", ""), keyval, state):
            self.change_terminal_font_size(-1)
            return True
        if self.store.data.app.sudo_password_shortcut and keybinding_matches(
            keybindings.get("send_password", ""), keyval, state
        ):
            self.send_saved_password(session, terminal)
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
        if not self.ensure_writable():
            return
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

    def send_saved_password(self, session: TerminalSession, terminal: Vte.Terminal | None = None) -> None:
        server = find_server(self.store.data.servers, session.server_id) if session.server_id is not None else None
        if not session.connected or server is None or not server.password:
            self.toast_label.set_label(self.t("sudo_password_unavailable"))
            return
        payload = server.password.encode()
        if self.store.data.app.sudo_password_enter:
            payload += b"\r"
        (terminal or session.terminal).feed_child(payload)
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
        popover.set_autohide(True)
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
        active_submenu: dict[str, Gtk.Popover | None] = {"popover": None}
        popover.connect("closed", lambda *_args: self.close_active_terminal_submenu(active_submenu))
        self.add_context_menu_item(menu, self.t("disconnect"), lambda: self.disconnect_from_terminal_menu(popover, session))
        if not session.status_bar.get_visible():
            self.add_context_menu_item(
                menu, self.t("show_session_status_bar"), lambda: self.show_session_status_bar_from_menu(popover, session)
            )
        self.add_terminal_shortcut_menu_item(
            menu,
            self.t("copy"),
            self.store.data.app.keybindings.get("copy", ""),
            lambda: self.copy_terminal_selection(popover, terminal),
        )
        self.add_terminal_shortcut_menu_item(
            menu,
            self.t("paste"),
            self.store.data.app.keybindings.get("paste", ""),
            lambda: self.paste_terminal_clipboard(popover, terminal),
        )
        self.add_context_menu_item(menu, self.t("configure_terminal"), lambda: self.configure_terminal_from_menu(popover))
        self.add_context_menu_item(menu, self.t("session_statistics"), lambda: self.show_session_statistics(popover, session))
        self.add_context_menu_separator(menu)
        self.add_terminal_split_menu(menu, popover, session, terminal, active_submenu)
        self.add_terminal_tab_menu(menu, popover, session, active_submenu)
        popover.set_child(menu)
        popover.popup()

    def add_terminal_shortcut_menu_item(
        self,
        menu: Gtk.ListBox,
        label_text: str,
        accelerator: str,
        callback: Any,
    ) -> None:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_hexpand(True)
        shortcut = Gtk.Label(label=keybinding_label(accelerator, self.t("keybinding_disabled")))
        shortcut.add_css_class("dim-label")
        shortcut.set_xalign(1)
        box.append(label)
        box.append(shortcut)
        row.set_child(box)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", lambda *_args: callback())
        row.add_controller(click)
        menu.append(row)

    def add_terminal_split_menu(
        self,
        menu: Gtk.ListBox,
        parent_popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
        active_submenu: dict[str, Gtk.Popover | None],
    ) -> None:
        submenu_items = [
            (self.t("split_up"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "up")),
            (self.t("split_down"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "down")),
            (self.t("split_right"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "right")),
            (self.t("split_left"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "left")),
        ]
        self.add_terminal_nested_menu(menu, self.t("split"), submenu_items, active_submenu)

    def add_terminal_tab_menu(
        self,
        menu: Gtk.ListBox,
        parent_popover: Gtk.Popover,
        session: TerminalSession,
        active_submenu: dict[str, Gtk.Popover | None],
    ) -> None:
        submenu_items = [
            (self.t("rename_tab"), lambda: self.show_rename_tab_dialog(parent_popover, session)),
            (self.t("duplicate_tab"), lambda: self.duplicate_tab(parent_popover, session)),
            (self.t("new_tab"), lambda: self.new_tab_from_terminal_menu(parent_popover)),
            (self.t("close_tab"), lambda: self.close_tab_from_terminal_menu(parent_popover, session)),
        ]
        self.add_terminal_nested_menu(menu, self.t("tab"), submenu_items, active_submenu)

    def add_terminal_nested_menu(
        self,
        menu: Gtk.ListBox,
        label_text: str,
        submenu_items: list[tuple[str, Any]],
        active_submenu: dict[str, Gtk.Popover | None],
    ) -> None:
        # All terminal context-menu submenus must go through this helper so
        # hover/open/close behavior stays consistent when new submenus are added.
        row = Gtk.ListBoxRow()
        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label_box.set_margin_top(8)
        label_box.set_margin_bottom(8)
        label_box.set_margin_start(12)
        label_box.set_margin_end(12)
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_hexpand(True)
        arrow = Gtk.Label(label=">")
        arrow.add_css_class("dim-label")
        label_box.append(label)
        label_box.append(arrow)
        row.set_child(label_box)

        submenu = Gtk.Popover()
        submenu.add_css_class("termia-menu-popover")
        submenu.set_has_arrow(False)
        submenu.set_autohide(False)
        submenu.set_position(Gtk.PositionType.RIGHT)
        submenu.set_parent(row)
        submenu_box = Gtk.ListBox()
        submenu_box.add_css_class("termia-menu-panel")
        submenu_box.set_selection_mode(Gtk.SelectionMode.NONE)
        submenu_box.set_margin_top(6)
        submenu_box.set_margin_bottom(6)
        submenu_box.set_margin_start(6)
        submenu_box.set_margin_end(6)
        for item_label, callback in submenu_items:
            self.add_context_menu_item(submenu_box, item_label, callback)
        submenu.set_child(submenu_box)

        row_motion = Gtk.EventControllerMotion.new()
        row_motion.connect("motion", lambda *_args: self.set_terminal_submenu_row_hover(active_submenu, submenu, True))
        row_motion.connect("leave", lambda *_args: self.set_terminal_submenu_row_hover(active_submenu, submenu, False))
        row.add_controller(row_motion)

        submenu_motion = Gtk.EventControllerMotion.new()
        submenu_motion.connect("motion", lambda *_args: self.set_terminal_submenu_panel_hover(active_submenu, submenu, True))
        submenu_motion.connect("leave", lambda *_args: self.set_terminal_submenu_panel_hover(active_submenu, submenu, False))
        submenu_box.add_controller(submenu_motion)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", lambda *_args: self.set_terminal_submenu_row_hover(active_submenu, submenu, True))
        row.add_controller(click)

        menu.append(row)

    def close_active_terminal_submenu(self, active_submenu: dict[str, Gtk.Popover | None]) -> None:
        close_id = active_submenu.get("close_id")
        if close_id is not None:
            GLib.source_remove(close_id)
            active_submenu["close_id"] = None
        submenu = active_submenu.get("popover")
        if submenu is not None:
            submenu.popdown()
        active_submenu["popover"] = None
        active_submenu["row_hover"] = False
        active_submenu["panel_hover"] = False

    def popup_terminal_submenu(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
    ) -> None:
        close_id = active_submenu.get("close_id")
        if close_id is not None:
            GLib.source_remove(close_id)
            active_submenu["close_id"] = None
        current = active_submenu.get("popover")
        if current is not submenu:
            if current is not None:
                current.popdown()
            active_submenu["popover"] = submenu
            active_submenu["row_hover"] = False
            active_submenu["panel_hover"] = False
        submenu.popup()

    def set_terminal_submenu_row_hover(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
        hovered: bool,
    ) -> None:
        if hovered:
            self.popup_terminal_submenu(active_submenu, submenu)
            active_submenu["row_hover"] = True
            return
        if active_submenu.get("popover") is submenu:
            active_submenu["row_hover"] = False
            self.schedule_terminal_submenu_close(active_submenu, submenu)

    def set_terminal_submenu_panel_hover(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
        hovered: bool,
    ) -> None:
        if hovered:
            self.popup_terminal_submenu(active_submenu, submenu)
            active_submenu["panel_hover"] = True
            return
        if active_submenu.get("popover") is submenu:
            active_submenu["panel_hover"] = False
            self.schedule_terminal_submenu_close(active_submenu, submenu)

    def schedule_terminal_submenu_close(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
    ) -> None:
        close_id = active_submenu.get("close_id")
        if close_id is not None:
            GLib.source_remove(close_id)
        active_submenu["close_id"] = GLib.timeout_add(
            120,
            self.close_terminal_submenu_if_inactive,
            active_submenu,
            submenu,
        )

    def close_terminal_submenu_if_inactive(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
    ) -> bool:
        active_submenu["close_id"] = None
        if active_submenu.get("popover") is not submenu:
            return GLib.SOURCE_REMOVE
        if active_submenu.get("row_hover") or active_submenu.get("panel_hover"):
            return GLib.SOURCE_REMOVE
        submenu.popdown()
        active_submenu["popover"] = None
        active_submenu["row_hover"] = False
        active_submenu["panel_hover"] = False
        return GLib.SOURCE_REMOVE

    def split_terminal_from_menu(
        self,
        popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
        direction: str,
    ) -> None:
        popover.popdown()
        target = terminal.get_parent()
        if not isinstance(target, Gtk.Widget):
            return

        new_terminal = self.create_split_terminal(session)
        new_scroller = self.wrap_terminal_in_scroller(new_terminal)
        orientation = Gtk.Orientation.HORIZONTAL if direction in {"left", "right"} else Gtk.Orientation.VERTICAL
        paned = Gtk.Paned(orientation=orientation)
        paned.add_css_class("termia-split-pane")
        paned.set_wide_handle(False)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)

        if not self.replace_terminal_pane(target, paned):
            session.split_terminals.remove(new_terminal)
            return

        if direction in {"left", "up"}:
            paned.set_start_child(new_scroller)
            paned.set_end_child(target)
        else:
            paned.set_start_child(target)
            paned.set_end_child(new_scroller)

        def center_split() -> bool:
            size = paned.get_width() if orientation == Gtk.Orientation.HORIZONTAL else paned.get_height()
            if size > 0:
                paned.set_position(size // 2)
            new_terminal.grab_focus()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(80, center_split)
        if session.server_id is None:
            self.start_local_split_terminal(session, new_terminal, terminal)
            return
        server = find_server(self.store.data.servers, session.server_id)
        if server is not None:
            self.start_ssh_split_terminal(session, new_terminal, server)

    def create_split_terminal(self, session: TerminalSession) -> Vte.Terminal:
        terminal = Vte.Terminal()
        terminal.set_hexpand(True)
        terminal.set_vexpand(True)
        terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.ON)
        terminal.set_scrollback_lines(10000)
        self.apply_terminal_settings(terminal)
        self.configure_terminal_interactions(terminal, session)
        session.split_terminals.append(terminal)
        return terminal

    def wrap_terminal_in_scroller(self, terminal: Vte.Terminal) -> Gtk.ScrolledWindow:
        scroller = Gtk.ScrolledWindow()
        scroller.set_child(terminal)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        return scroller

    def replace_terminal_pane(self, old_child: Gtk.Widget, replacement: Gtk.Widget) -> bool:
        parent = old_child.get_parent()
        if isinstance(parent, Gtk.Paned):
            if parent.get_start_child() is old_child:
                parent.set_start_child(None)
                parent.set_start_child(replacement)
                return True
            if parent.get_end_child() is old_child:
                parent.set_end_child(None)
                parent.set_end_child(replacement)
                return True
            return False
        if isinstance(parent, Gtk.Box):
            parent.remove(old_child)
            parent.append(replacement)
            return True
        return False

    def start_local_split_terminal(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        source_terminal: Vte.Terminal,
    ) -> None:
        shell = os.environ.get("SHELL") or GLib.find_program_in_path("bash") or "/bin/sh"
        command = [shell]
        if self.store.data.terminal.prompt_enabled:
            bash_path = GLib.find_program_in_path("bash")
            if bash_path is not None:
                command = build_local_prompt_shell_command(self.store.data.terminal, bash_path)
        working_directory = self.local_terminal_working_directory(source_terminal)
        try:
            _ok, child_pid = terminal.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                working_directory,
                command,
                build_terminal_environment(self.store.data.terminal.ls_colors),
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                None,
            )
        except GLib.Error as exc:
            message = self.t("local_terminal_start_failed").format(error=exc.message)
            terminal.feed(f"{message}\r\n".encode())
            self.toast_label.set_label(message)
            return
        session.split_child_pids[id(terminal)] = child_pid
        terminal.connect("child-exited", self.on_split_terminal_exited, session)

    def start_ssh_split_terminal(self, session: TerminalSession, terminal: Vte.Terminal, server: Server) -> None:
        ssh_path = GLib.find_program_in_path("ssh")
        if ssh_path is None:
            message = self.t("ssh_missing")
            terminal.feed(f"{message}\r\n".encode())
            self.toast_label.set_label(message)
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
                message = self.t("sshpass_missing")
                terminal.feed(f"{message}\r\n".encode())
                self.toast_label.set_label(message)
                return
            command = [sshpass_path, "-e", *command]
        terminal.feed(f"{self.t('ssh_connecting_command').format(command=' '.join(command))}\r\n\r\n".encode())
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
            message = self.t("ssh_start_failed").format(error=exc.message)
            terminal.feed(f"{message}\r\n".encode())
            self.toast_label.set_label(self.t("ssh_start_failed_toast").format(name=server.name))
            return
        session.split_child_pids[id(terminal)] = child_pid
        terminal.connect("child-exited", self.on_split_terminal_exited, session)
        self.record_connection(server.id)
        self.toast_label.set_label(self.t("session_opened").format(title=server.name))

    def local_terminal_working_directory(self, terminal: Vte.Terminal) -> str:
        uri = terminal.get_current_directory_uri()
        if uri:
            parsed = urlparse(uri)
            if parsed.scheme == "file":
                return unquote(parsed.path)
        return str(Path.home())

    def on_split_terminal_exited(self, terminal: Vte.Terminal, _status: int, session: TerminalSession) -> None:
        session.split_child_pids.pop(id(terminal), None)
        if terminal in session.split_terminals:
            session.split_terminals.remove(terminal)
        GLib.idle_add(self.remove_split_terminal_pane, terminal, session)

    def remove_split_terminal_pane(self, terminal: Vte.Terminal, session: TerminalSession) -> bool:
        scroller = terminal.get_parent()
        if not isinstance(scroller, Gtk.ScrolledWindow):
            return GLib.SOURCE_REMOVE
        parent = scroller.get_parent()
        if not isinstance(parent, Gtk.Paned):
            return GLib.SOURCE_REMOVE

        sibling = parent.get_end_child() if parent.get_start_child() is scroller else parent.get_start_child()
        if sibling is None:
            return GLib.SOURCE_REMOVE
        self.replace_split_container(parent, sibling)
        if session.split_terminals:
            session.split_terminals[-1].grab_focus()
        else:
            session.terminal.grab_focus()
        return GLib.SOURCE_REMOVE

    def replace_split_container(self, paned: Gtk.Paned, replacement: Gtk.Widget) -> bool:
        parent = paned.get_parent()
        paned.set_start_child(None)
        paned.set_end_child(None)
        if isinstance(parent, Gtk.Paned):
            if parent.get_start_child() is paned:
                parent.set_start_child(None)
                parent.set_start_child(replacement)
                return True
            if parent.get_end_child() is paned:
                parent.set_end_child(None)
                parent.set_end_child(replacement)
                return True
            return False
        if isinstance(parent, Gtk.Box):
            parent.remove(paned)
            parent.append(replacement)
            return True
        return False

    def new_tab_from_terminal_menu(self, popover: Gtk.Popover) -> None:
        popover.popdown()
        self.on_open_local_terminal(None)

    def close_tab_from_terminal_menu(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        self.on_request_close_tab(None, session.id, session.page)

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
        label = Gtk.Label(label=f"{self.t('server_connections')}: {server_connections}")
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
            for terminal in session.split_terminals:
                self.apply_terminal_settings(terminal)

    def update_session_timer(self, session: TerminalSession) -> bool:
        if not session.connected:
            return GLib.SOURCE_REMOVE
        elapsed = int(time.monotonic() - session.started_at)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        session.timer_label.set_label(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.update_local_session_directory_title(session)
        return GLib.SOURCE_CONTINUE

    def terminate_split_processes(self, session: TerminalSession) -> None:
        for child_pid in tuple(session.split_child_pids.values()):
            try:
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError:
                pass
        session.split_child_pids.clear()

    def on_request_disconnect_session(self, _button: Gtk.Button, session: TerminalSession) -> None:
        if not session.connected:
            return
        if not self.store.data.app.confirm_disconnect:
            self.disconnect_session(session)
            return
        self.confirm_session_action(
            session,
            self.t("disconnect_session_title"),
            self.t("disconnect_session_detail").format(title=session.title),
            self.t("disconnect_session_confirm"),
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
                message = self.t("sigterm_failed")
                session.terminal.feed(f"{message}\r\n".encode())
                self.toast_label.set_label(message)
                return
        self.terminate_split_processes(session)
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        session.status_label.set_label(self.t("session_disconnected_status").format(title=session.title))
        session.terminal.feed(f"\r\n{self.t('session_disconnected_terminal')}\r\n".encode())
        self.update_session_tab_title(session, self.t("tab_disconnected_title").format(title=session.title))
        self.toast_label.set_label(self.t("session_disconnected_toast").format(title=session.title))
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
        dialog.set_buttons([self.t("cancel"), confirm_label])
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
            session.status_label.set_label(self.t("session_disconnected_status").format(title=session.title))
            self.toast_label.set_label(self.t("session_disconnected_toast").format(title=session.title))
            return
        if self.child_status_successful(_status):
            if self.store.data.app.close_tab_on_ssh_exit:
                self.close_tab(session.id, session.page, disconnect=False)
                self.toast_label.set_label(self.t("session_closed_toast").format(title=server.name))
                return
            session.status_label.set_label(self.t("session_closed_status").format(title=session.title))
            self.update_session_tab_title(session, self.t("tab_closed_title").format(title=session.title))
            self.toast_label.set_label(self.t("session_closed_toast").format(title=server.name))
            return
        session.status_label.set_label(f"Error: {session.title}")
        self.mark_session_for_reconnect(session, server, self.t("connection_failed_toast").format(title=server.name))

