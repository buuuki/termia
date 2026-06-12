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
from .keybindings import keybinding_matches
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
        enter_keys = {Gdk.KEY_Return, Gdk.KEY_KP_Enter, getattr(Gdk, "KEY_ISO_Enter", Gdk.KEY_Return)}
        if keyval in enter_keys and session.pending_reconnect:
            self.reconnect_session(session)
            return True
        keybindings = self.store.data.app.keybindings
        if keybinding_matches(keybindings.get("copy", ""), keyval, state):
            session.terminal.copy_clipboard_format(Vte.Format.TEXT)
            return True
        if keybinding_matches(keybindings.get("paste", ""), keyval, state):
            session.terminal.paste_clipboard()
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

    def update_session_timer(self, session: TerminalSession) -> bool:
        if not session.connected:
            return GLib.SOURCE_REMOVE
        elapsed = int(time.monotonic() - session.started_at)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        session.timer_label.set_label(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.update_local_session_directory_title(session)
        return GLib.SOURCE_CONTINUE

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

