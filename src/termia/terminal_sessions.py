# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os
import signal
import subprocess
import shlex
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

from .connection_utils import find_local_terminal_profile, find_server
from .file_transfer import FileTransferController
from .keybindings import is_unmodified_function_key, keybinding_matches
from .models import LocalTerminalProfile, Server, Workspace
from .session_commands import build_ssh_command
from .split_panes import SplitPaneController
from .split_connection_search import (
    SplitConnectionChoice,
    build_split_connection_choices,
    filter_split_connection_choices,
)
from .terminal_config import (
    build_local_prompt_shell_command,
    build_terminal_environment,
    split_layout_plan,
)
from .terminal_processes import TerminalProcess, signal_terminal_process, spawn_terminal_process
from .terminal_view import TerminalViewFactory
from .ui_state import TerminalPane, TerminalSession
from .workspace_layout import (
    MAX_WORKSPACE_PANES,
    workspace_layout_is_valid,
    workspace_pane_count,
    workspace_root_pane,
    workspace_tab_layouts,
    workspace_total_pane_count,
)


INITIAL_LOCAL_COMMAND_DELAY_MS = 300
MAX_OPEN_TABS = 40
MAX_TERMINAL_PANES = 16


class TerminalSessionsMixin:
    def on_open_local_terminal(self, _button: Gtk.Button) -> None:
        self.open_local_terminal_profile(None)

    def open_local_terminal_profile(
        self,
        profile: LocalTerminalProfile | None,
        *,
        split_layout: str | None = None,
    ) -> TerminalSession | None:
        title = self.local_terminal_session_title(profile)
        try:
            command = self.build_local_terminal_command(profile)
        except ValueError as exc:
            self.toast_label.set_label(self.t("local_terminal_invalid_arguments").format(error=exc))
            return None
        working_directory = self.local_terminal_profile_working_directory(profile)
        return self.open_process_terminal_tab(
            title,
            command,
            None,
            working_directory=working_directory,
            local_profile_id=profile.id if profile is not None else None,
            title_locked=profile is not None,
            initial_command=profile.command_on_start if profile is not None else "",
            split_layout=split_layout if split_layout is not None else (profile.split_layout if profile is not None else "none"),
        )

    def local_terminal_session_title(self, profile: LocalTerminalProfile | None) -> str:
        if profile is None:
            return self.local_directory_title(Path.home())
        return profile.tab_title.strip() or profile.name.strip() or self.t("local_terminal")

    def local_terminal_profile_working_directory(self, profile: LocalTerminalProfile | None) -> str:
        if profile is None or not profile.working_directory.strip():
            return str(Path.home())
        return str(Path(profile.working_directory).expanduser())

    def default_local_terminal_shell(self) -> str:
        return os.environ.get("SHELL") or GLib.find_program_in_path("bash") or "/bin/sh"

    def build_local_terminal_command(self, profile: LocalTerminalProfile | None) -> list[str]:
        if profile is None:
            shell = self.default_local_terminal_shell()
            command: list[str] = [shell]
            if self.store.data.terminal.prompt_enabled:
                bash_path = GLib.find_program_in_path("bash")
                if bash_path is not None:
                    return build_local_prompt_shell_command(self.store.data.terminal, bash_path)
            return command

        shell = profile.shell.strip() or self.default_local_terminal_shell()
        shell_arguments = shlex.split(profile.arguments) if profile.arguments.strip() else []
        if self.store.data.terminal.prompt_enabled and self.local_terminal_shell_supports_prompt(shell):
            return build_local_prompt_shell_command(
                self.store.data.terminal,
                shell,
                shell_arguments,
            )
        command = [shell, *shell_arguments]
        return command

    def local_terminal_shell_supports_prompt(self, shell: str) -> bool:
        return Path(shell).name == "bash"

    def create_configured_terminal(self) -> Vte.Terminal:
        return TerminalViewFactory(self.resolved_terminal_font_family).create(
            self.store.data.terminal,
            audible_bell=self.store.data.app.audible_bell,
        )

    def build_session_status_bar(
        self,
        *,
        include_margins: bool = False,
    ) -> tuple[Gtk.Box, Gtk.Label, Gtk.Label, Gtk.Button, Gtk.Button]:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.add_css_class("termia-pane-status")
        if include_margins:
            toolbar.set_margin_top(0)
            toolbar.set_margin_bottom(0)
            toolbar.set_margin_start(4)
            toolbar.set_margin_end(4)

        status_label = Gtk.Label(label=self.t("connecting"))
        status_label.set_xalign(0)
        status_label.set_hexpand(True)
        status_label.set_size_request(0, -1)
        status_label.set_ellipsize(Pango.EllipsizeMode.END)
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
        toolbar.append(timer_label)
        toolbar.append(disconnect_button)
        return toolbar, status_label, timer_label, focus_button, disconnect_button

    def build_terminal_pane(self, toolbar: Gtk.Widget, terminal: Vte.Terminal) -> Gtk.Box:
        pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        pane.add_css_class("termia-terminal-pane")
        pane.append(toolbar)
        pane.append(self.wrap_terminal_in_scroller(terminal))
        pane.set_hexpand(True)
        pane.set_vexpand(True)
        return pane

    def build_terminal_page(self, pane: Gtk.Widget) -> Gtk.Box:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.append(pane)
        page.set_hexpand(True)
        page.set_vexpand(True)
        return page

    def create_terminal_session(
        self,
        title: str,
        server_id: str | None,
        *,
        toolbar_margins: bool = False,
        local_profile_id: str | None = None,
        title_locked: bool = False,
    ) -> tuple[TerminalSession, Gtk.Button]:
        session_id = str(uuid4())
        terminal = self.create_configured_terminal()
        toolbar, status_label, timer_label, focus_button, disconnect_button = self.build_session_status_bar(
            include_margins=toolbar_margins
        )
        pane_container = self.build_terminal_pane(toolbar, terminal)
        page = self.build_terminal_page(pane_container)
        tab_label = self.build_tab_label(title, session_id, page)
        session = TerminalSession(
            id=session_id,
            server_id=server_id,
            title=title,
            terminal=terminal,
            page=page,
            tab_label=tab_label,
            status_label=status_label,
            timer_label=timer_label,
            disconnect_button=disconnect_button,
            status_bar=toolbar,
            started_at=time.monotonic(),
            local_profile_id=local_profile_id,
            title_locked=title_locked,
        )
        session.panes[id(terminal)] = TerminalPane(
            id=session_id,
            terminal=terminal,
            container=pane_container,
            status_label=status_label,
            timer_label=timer_label,
            disconnect_button=disconnect_button,
            status_bar=toolbar,
            title=title,
            started_at=session.started_at,
            server_id=server_id,
            local_profile_id=local_profile_id,
        )
        session.active_terminal_ids.add(id(terminal))
        return session, focus_button

    def open_process_terminal_tab(
        self,
        title: str,
        command: list[str],
        server_id: str | None,
        envv: list[str] | None = None,
        working_directory: str | None = None,
        local_profile_id: str | None = None,
        title_locked: bool = False,
        initial_command: str = "",
        split_layout: str = "none",
    ) -> TerminalSession | None:
        if not self.can_open_terminal_tabs():
            return None
        session, focus_button = self.create_terminal_session(
            title,
            server_id,
            local_profile_id=local_profile_id,
            title_locked=title_locked,
        )
        terminal = session.terminal
        focus_button.connect("clicked", self.on_hide_pane_status_bar, session, terminal)
        session.disconnect_button.connect("clicked", self.on_request_disconnect_pane, session, terminal)
        self.configure_terminal_interactions(terminal, session)
        self.session_registry.register(session)
        self.add_session_to_main_view(session)
        self.update_local_session_directory_title(session)
        terminal.grab_focus()
        self.store.record_history_start(session, "local")
        try:
            child_process = spawn_terminal_process(
                terminal,
                working_directory,
                command,
                envv or build_terminal_environment(self.store.data.terminal.ls_colors),
            )
        except GLib.Error as exc:
            message = self.t("local_terminal_start_failed").format(error=exc.message)
            retry_prompt = self.t("local_terminal_retry_prompt")
            terminal.feed(f"{message}\r\n".encode())
            terminal.feed(f"{retry_prompt}\r\n".encode())
            session.status_label.set_label("Error")
            session.connected = False
            session.pending_reconnect = True
            self.sync_root_pane_state(session)
            self.show_pane_reconnect_controls(self.pane_state(session, terminal))
            self.store.record_history_end(session, "failed", detail=exc.message)
            self.update_session_tab_title(session, self.t("tab_error_title").format(title=session.title))
            self.toast_label.set_label(message)
            return session
        session.child_process = child_process
        session.child_pid = child_process.pid
        self.sync_root_pane_state(session)
        self.update_local_session_directory_title(session)
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_process_terminal_exited, session)
        session.status_label.set_label(f"{title} · PID {child_process.pid}")
        self.apply_split_layout(session, split_layout, fallback_working_directory=working_directory)
        if initial_command.strip():
            GLib.timeout_add(INITIAL_LOCAL_COMMAND_DELAY_MS, self.feed_initial_local_command, terminal, initial_command.strip())
        return session

    def feed_initial_local_command(self, terminal: Vte.Terminal, command: str) -> bool:
        terminal.feed_child(f"{command}\n".encode())
        return GLib.SOURCE_REMOVE

    def on_process_terminal_exited(self, terminal: Vte.Terminal, _status: int, session: TerminalSession) -> None:
        self.mark_terminal_inactive(terminal, session)
        pane = self.pane_state(session, terminal)
        self.record_session_duration(session)
        self.save_statistics_now()
        result = "disconnected" if pane.disconnect_requested else (
            "closed" if self.child_status_successful(_status) else "failed"
        )
        self.store.record_history_end(session, result)
        pane.connected = False
        pane.disconnect_button.set_sensitive(False)
        if not pane.disconnect_requested and self.child_status_successful(_status) and session.active_terminal_ids:
            self.remove_terminal_pane_if_split(terminal, session)
            return
        session.connected = bool(session.active_terminal_ids)
        if pane.disconnect_requested:
            session.status_label.set_label(self.t("session_disconnected_status").format(title=session.title))
            return
        if self.child_status_successful(_status):
            if self.should_close_tab_after_terminal_exit(session):
                self.close_tab(session.id, session.page, disconnect=False)
                self.toast_label.set_label(self.t("local_terminal_closed").format(title=session.title))
                return
            self.remove_terminal_pane_if_split(terminal, session)
            session.status_label.set_label(self.t("session_closed_status").format(title=session.title))
            self.update_session_tab_title(session, self.t("tab_closed_title").format(title=session.title))

    def can_open_terminal_tabs(self, requested_tabs: int = 1) -> bool:
        if requested_tabs <= 0:
            return True
        open_tabs = len(self.session_registry.sessions())
        if open_tabs + requested_tabs <= MAX_OPEN_TABS:
            return True
        self.toast_label.set_label(
            self.t("global_tab_limit_exceeded").format(
                limit=MAX_OPEN_TABS,
                open=open_tabs,
                requested=requested_tabs,
            )
        )
        return False

    def open_terminal_tab(
        self,
        server: Server,
        *,
        split_layout: str | None = None,
    ) -> TerminalSession | None:
        if not self.can_open_terminal_tabs():
            return None
        session, focus_button = self.create_terminal_session(server.name, server.id, toolbar_margins=True)
        focus_button.connect("clicked", self.on_hide_pane_status_bar, session, session.terminal)
        session.disconnect_button.connect("clicked", self.on_request_disconnect_pane, session, session.terminal)
        self.configure_terminal_interactions(session.terminal, session)
        self.session_registry.register(session)
        self.add_session_to_main_view(session)

        self.start_ssh_session(
            server,
            session,
            split_layout=split_layout if split_layout is not None else server.split_layout,
        )
        return session

    def duplicate_session(self, session: TerminalSession) -> None:
        if session.server_id is not None:
            server = find_server(self.store.data.servers, session.server_id)
            if server is not None:
                self.open_terminal_tab(server)
            return
        self.on_open_local_terminal(None)

    def open_workspace(self, workspace: Workspace) -> None:
        pane_count = workspace_total_pane_count(workspace.tabs)
        if pane_count > MAX_WORKSPACE_PANES:
            self.toast_label.set_label(
                self.t("workspace_pane_limit_exceeded").format(
                    count=pane_count,
                    limit=MAX_WORKSPACE_PANES,
                )
            )
            return
        layouts = workspace_tab_layouts(workspace.tabs)
        if not self.can_open_terminal_tabs(len(layouts)):
            return
        self.open_workspace_tabs(workspace)

    def open_workspace_tabs(self, workspace: Workspace) -> None:
        opened_tabs = 0
        skipped_tabs = 0
        for layout in workspace_tab_layouts(workspace.tabs):
            if not self.workspace_layout_available(layout):
                skipped_tabs += 1
                continue
            root = workspace_root_pane(layout)
            if root is None:
                skipped_tabs += 1
                continue
            session = self.open_workspace_root(root)
            if session is None:
                skipped_tabs += 1
                continue
            self.restore_workspace_node(session, session.terminal, layout)
            opened_tabs += 1
        if opened_tabs:
            self.toast_label.set_label(
                self.t("workspace_opened").format(name=workspace.name, count=opened_tabs)
            )
        else:
            self.toast_label.set_label(self.t("workspace_no_available_tabs").format(name=workspace.name))
        if opened_tabs and skipped_tabs:
            self.toast_label.set_label(
                self.t("workspace_opened_with_skipped_tabs").format(
                    name=workspace.name,
                    count=opened_tabs,
                    skipped=skipped_tabs,
                )
            )

    def restore_session_snapshot(self, tabs: list[dict[str, object]]) -> None:
        """Reopen the last session from safe connection references."""
        layouts = workspace_tab_layouts(tabs)
        pane_count = workspace_total_pane_count(tabs)
        if pane_count > MAX_WORKSPACE_PANES or not self.can_open_terminal_tabs(len(layouts)):
            return

        opened_tabs = 0
        skipped_tabs = 0
        for layout in layouts:
            if not self.workspace_layout_available(layout):
                skipped_tabs += 1
                continue
            root = workspace_root_pane(layout)
            if root is None:
                skipped_tabs += 1
                continue
            session = self.open_workspace_root(root)
            if session is None:
                skipped_tabs += 1
                continue
            self.restore_workspace_node(session, session.terminal, layout)
            opened_tabs += 1

        if opened_tabs:
            self.toast_label.set_label(self.t("sessions_restored").format(count=opened_tabs))
        else:
            self.toast_label.set_label(self.t("sessions_not_restored"))
        if opened_tabs and skipped_tabs:
            self.toast_label.set_label(
                self.t("sessions_restored_with_skipped").format(
                    count=opened_tabs,
                    skipped=skipped_tabs,
                )
            )

    def workspace_layout_available(self, node: dict[str, object]) -> bool:
        if not workspace_layout_is_valid(node) or workspace_pane_count(node) > MAX_TERMINAL_PANES:
            return False
        if node["type"] == "pane":
            connection_type = node["connection_type"]
            connection_id = node["connection_id"]
            if connection_type == "server":
                return find_server(self.store.data.servers, str(connection_id)) is not None
            return not connection_id or find_local_terminal_profile(
                self.store.data.local_terminals,
                str(connection_id),
            ) is not None
        return self.workspace_layout_available(node["start"]) and self.workspace_layout_available(node["end"])

    def open_workspace_root(self, node: dict[str, object]) -> TerminalSession | None:
        connection_type = node["connection_type"]
        connection_id = str(node["connection_id"])
        if connection_type == "server":
            server = find_server(self.store.data.servers, connection_id)
            return self.open_terminal_tab(server, split_layout="none") if server is not None else None
        profile = find_local_terminal_profile(self.store.data.local_terminals, connection_id) if connection_id else None
        return self.open_local_terminal_profile(profile, split_layout="none")

    def restore_workspace_node(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        node: dict[str, object],
    ) -> None:
        if node["type"] == "pane":
            return
        orientation = node["orientation"]
        direction = "right" if orientation == "horizontal" else "down"
        new_terminal = self.split_terminal_pane(session, terminal, direction)
        if new_terminal is None:
            return
        end = node["end"]
        end_root = workspace_root_pane(end)
        if end_root is None or not self.start_workspace_pane(session, new_terminal, terminal, end_root):
            self.discard_unstarted_split_pane(session, new_terminal)
            return
        paned = self.terminal_pane_container(session, new_terminal).get_parent()
        self.restore_workspace_node(session, terminal, node["start"])
        self.restore_workspace_node(session, new_terminal, end)
        if isinstance(paned, Gtk.Paned):
            self.restore_workspace_split_position(paned, float(node.get("position", 0.5)))

    def start_workspace_pane(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        source_terminal: Vte.Terminal,
        node: dict[str, object],
    ) -> bool:
        connection_type = node["connection_type"]
        connection_id = str(node["connection_id"])
        if connection_type == "server":
            server = find_server(self.store.data.servers, connection_id)
            if server is None:
                return False
            self.start_ssh_split_terminal(session, terminal, server, announce=False)
            return True
        profile = find_local_terminal_profile(self.store.data.local_terminals, connection_id) if connection_id else None
        self.start_local_split_terminal(session, terminal, source_terminal, profile=profile)
        return True

    def restore_workspace_split_position(self, paned: Gtk.Paned, ratio: float, attempts: int = 4) -> None:
        def apply_position() -> bool:
            size = paned.get_width() if paned.get_orientation() == Gtk.Orientation.HORIZONTAL else paned.get_height()
            if size <= 0 and attempts > 0:
                GLib.timeout_add(80, self.restore_workspace_split_position, paned, ratio, attempts - 1)
                return GLib.SOURCE_REMOVE
            if size > 0:
                paned.set_position(round(size * max(0.1, min(ratio, 0.9))))
            return GLib.SOURCE_REMOVE

        GLib.idle_add(apply_position)

    def start_ssh_session(self, server: Server, session: TerminalSession, *, split_layout: str = "none") -> None:
        terminal = session.terminal
        session.started_at = time.monotonic()
        session.duration_recorded = False
        session.disconnect_requested = False
        session.pending_reconnect = False
        session.child_pid = None
        session.child_process = None
        session.connected = True
        session.disconnect_button.set_label(self.t("disconnect"))
        session.disconnect_button.set_sensitive(True)
        session.status_label.set_label(self.t("connecting"))
        self.store.record_history_start(session, "ssh", server)

        ssh_path = GLib.find_program_in_path("ssh")
        if ssh_path is None:
            message = self.t("ssh_missing")
            terminal.feed(f"{message}\r\n".encode())
            session.status_label.set_label(self.t("ssh_missing_status"))
            self.store.record_history_end(session, "failed", detail=message)
            self.mark_session_for_reconnect(session, server, message)
            return

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
                self.store.record_history_end(session, "failed", detail=message)
                self.mark_session_for_reconnect(session, server, message)
                return
            command = build_ssh_command(server, ssh_path, sshpass_path=sshpass_path)
        else:
            command = build_ssh_command(server, ssh_path)
        terminal.feed(f"{self.t('ssh_connecting_command').format(command=' '.join(command))}\r\n\r\n".encode())
        terminal.grab_focus()
        try:
            child_process = spawn_terminal_process(terminal, None, command, envv)
        except GLib.Error as exc:
            message = self.t("ssh_start_failed").format(error=exc.message)
            terminal.feed(f"{message}\r\n".encode())
            session.status_label.set_label("Error")
            self.store.record_history_end(session, "failed", detail=exc.message)
            self.mark_session_for_reconnect(session, server, self.t("ssh_start_failed_toast").format(name=server.name))
            return

        session.child_process = child_process
        session.child_pid = child_process.pid
        self.sync_root_pane_state(session)
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_terminal_exited, server, session)
        self.record_connection(server.id)
        session.status_label.set_label(f"{server.name} · PID {child_process.pid}")
        self.apply_split_layout(session, split_layout, server=server)
        self.toast_label.set_label(self.t("session_opened").format(title=session.title))

    def mark_session_for_reconnect(self, session: TerminalSession, server: Server, toast: str) -> None:
        session.connected = False
        session.pending_reconnect = True
        self.sync_root_pane_state(session)
        self.show_pane_reconnect_controls(self.pane_state(session, session.terminal))
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
        if session.local_profile_id is None:
            self.on_open_local_terminal(None)
            return
        profile = find_local_terminal_profile(self.store.data.local_terminals, session.local_profile_id)
        if profile is None:
            self.on_open_local_terminal(None)
            return
        self.open_local_terminal_profile(profile)

    def mark_pane_for_reconnect(
        self,
        session: TerminalSession,
        pane: TerminalPane,
        toast: str,
    ) -> None:
        pane.connected = False
        pane.pending_reconnect = True
        self.show_pane_reconnect_controls(pane)
        session.active_terminal_ids.discard(id(pane.terminal))
        prompt = f"  {self.t('reconnect_prompt')}  "
        pane.terminal.feed(f"\r\n\x1b[1;30;48;2;255;213;79m{prompt}\x1b[0m\r\n".encode())
        self.toast_label.set_label(toast)

    def show_pane_reconnect_controls(self, pane: TerminalPane) -> None:
        pane.status_bar.set_visible(True)
        pane.disconnect_button.set_label(self.t("close"))
        pane.disconnect_button.set_sensitive(True)

    def reset_pane_connection_attempt(self, pane: TerminalPane) -> None:
        pane.pending_reconnect = False
        pane.disconnect_requested = False
        pane.disconnect_button.set_label(self.t("disconnect"))
        pane.disconnect_button.set_sensitive(True)
        pane.duration_recorded = False
        pane.history_start_recorded = False
        pane.history_end_recorded = False
        pane.history_kind = ""
        pane.history_started_at = ""
        pane.history_title = ""
        pane.history_server_name = ""
        pane.history_host = ""
        pane.history_user = ""
        pane.history_port = 0
        pane.child_pid = None
        pane.child_process = None

    def retry_split_pane(self, session: TerminalSession, terminal: Vte.Terminal) -> None:
        pane = self.pane_state(session, terminal)
        if not pane.pending_reconnect:
            return
        server = (
            find_server(self.store.data.servers, pane.server_id)
            if pane.server_id is not None
            else None
        )
        profile = (
            find_local_terminal_profile(self.store.data.local_terminals, pane.local_profile_id)
            if pane.local_profile_id is not None
            else None
        )
        if pane.server_id is not None and server is None:
            pane.pending_reconnect = False
            self.toast_label.set_label(self.t("server_reconnect_missing"))
            return
        self.reset_pane_connection_attempt(pane)
        session.active_terminal_ids.add(id(terminal))
        if server is not None:
            self.start_ssh_split_terminal(session, terminal, server, announce=True)
        else:
            self.start_local_split_terminal(session, terminal, terminal, profile=profile)

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
        for session in self.session_registry.sessions():
            self.record_session_duration(session)
            for pane in session.panes.values():
                if pane.terminal is not session.terminal:
                    self.record_pane_duration(pane)
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

    def record_session_duration(self, session: TerminalSession) -> None:
        self.record_pane_duration(session)

    def record_pane_duration(self, pane: TerminalSession | TerminalPane) -> None:
        if not self.store.data.app.statistics_enabled:
            return
        if pane.duration_recorded or pane.child_pid is None:
            return
        pane.duration_recorded = True
        duration = max(0.0, time.monotonic() - pane.started_at)
        stats = self.store.data.statistics
        stats.completed_sessions += 1
        stats.duration_total += duration
        stats.duration_min = duration if stats.duration_min is None else min(stats.duration_min, duration)
        stats.duration_max = max(stats.duration_max, duration)
        self.schedule_statistics_save()

    def save_history_before_close(self) -> None:
        for session in self.session_registry.sessions():
            if session.history_start_recorded and not session.history_end_recorded:
                result = "disconnected" if session.disconnect_requested else "closed"
                self.store.record_history_end(session, result)
            for pane in session.panes.values():
                if pane.terminal is session.terminal:
                    continue
                if pane.history_start_recorded and not pane.history_end_recorded:
                    result = "disconnected" if pane.disconnect_requested else "closed"
                    self.store.record_history_end(pane, result)

    def configure_terminal_interactions(self, terminal: Vte.Terminal, session: TerminalSession) -> None:
        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self.on_terminal_key_pressed, session, terminal)
        terminal.add_controller(keys)
        focus = Gtk.EventControllerFocus.new()
        focus.connect("enter", self.on_terminal_focus_enter, session, terminal)
        terminal.add_controller(focus)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_terminal_right_click, session, terminal)
        terminal.add_controller(right_click)

    def on_terminal_focus_enter(
        self,
        _controller: Gtk.EventControllerFocus,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        for pane in session.panes.values():
            pane.status_bar.remove_css_class("active")
        pane = session.pane_for_terminal(terminal)
        if pane is not None:
            pane.status_bar.add_css_class("active")

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
        pane = self.pane_state(session, terminal)
        if keyval in enter_keys and pane.pending_reconnect:
            if terminal is session.terminal:
                if session.server_id is None:
                    self.retry_local_terminal_session(session)
                else:
                    self.reconnect_session(session)
            else:
                self.retry_split_pane(session, terminal)
            return True
        if is_unmodified_function_key(keyval, state):
            return False
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
        if self.store.data.app.send_password_shortcut and keybinding_matches(
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

    def should_show_session_status_bar(self) -> bool:
        return self.store.data.app.show_session_status_bar

    def pane_state(self, session: TerminalSession, terminal: Vte.Terminal) -> TerminalPane:
        pane = session.pane_for_terminal(terminal)
        if pane is None:
            raise ValueError("Terminal pane is not registered in its session")
        return pane

    def sync_root_pane_state(self, session: TerminalSession) -> None:
        pane = session.pane_for_terminal(session.terminal)
        if pane is None:
            return
        pane.title = session.title
        pane.server_id = session.server_id
        pane.local_profile_id = session.local_profile_id
        pane.started_at = session.started_at
        pane.child_pid = session.child_pid
        pane.child_process = session.child_process
        pane.connected = session.connected
        pane.disconnect_requested = session.disconnect_requested
        pane.pending_reconnect = session.pending_reconnect

    def on_hide_pane_status_bar(
        self,
        _button: Gtk.Button,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        pane = self.pane_state(session, terminal)
        self.set_pane_status_bar_visibility(pane, False)
        terminal.grab_focus()

    def set_pane_status_bar_visibility(self, pane: TerminalPane, visible: bool) -> None:
        """Toggle a pane bar without allowing its new width to move a split."""

        parent_getter = getattr(pane.container, "get_parent", None)
        parent = parent_getter() if callable(parent_getter) else None
        ratio: float | None = None
        if isinstance(parent, Gtk.Paned):
            size = parent.get_width() if parent.get_orientation() == Gtk.Orientation.HORIZONTAL else parent.get_height()
            if size > 0:
                ratio = parent.get_position() / size

        pane.status_bar.set_visible(visible)
        if ratio is not None and isinstance(parent, Gtk.Paned):
            self.restore_split_position_after_status_bar_toggle(parent, ratio)

    def restore_split_position_after_status_bar_toggle(self, paned: Gtk.Paned, ratio: float) -> None:
        def restore_position() -> bool:
            size = paned.get_width() if paned.get_orientation() == Gtk.Orientation.HORIZONTAL else paned.get_height()
            if size > 0:
                paned.set_position(round(size * max(0.0, min(ratio, 1.0))))
            return GLib.SOURCE_REMOVE

        GLib.idle_add(restore_position)

    def apply_session_status_bar_visibility_to_open_tabs(self) -> None:
        visible = self.should_show_session_status_bar()
        for session in self.session_registry.sessions():
            for pane in session.panes.values():
                self.set_pane_status_bar_visibility(pane, visible)

    def change_terminal_font_size(self, delta: int) -> None:
        if not self.ensure_writable():
            return
        settings = self.store.data.terminal
        new_size = max(6, min(settings.font_size + delta, 72))
        if new_size == settings.font_size:
            return
        self.store.update_terminal_settings(
            font_family=settings.font_family,
            font_size=new_size,
            foreground=settings.foreground,
            background=settings.background,
            ls_colors=settings.ls_colors,
        )
        self.apply_terminal_settings_to_open_tabs()
        self.toast_label.set_label(self.t("terminal_font_size_changed").format(size=new_size))

    def send_saved_password(self, session: TerminalSession, terminal: Vte.Terminal | None = None) -> None:
        target = terminal or session.terminal
        pane = self.pane_state(session, target)
        server = find_server(self.store.data.servers, pane.server_id) if pane.server_id is not None else None
        if not pane.connected or server is None or not server.password:
            self.toast_label.set_label(self.t("send_password_unavailable"))
            return
        payload = server.password.encode()
        if self.store.data.app.send_password_enter:
            payload += b"\r"
        target.feed_child(payload)
        self.toast_label.set_label(self.t("send_password_sent"))

    def split_terminal_pane(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        direction: str,
    ) -> Vte.Terminal | None:
        if len(session.panes) >= MAX_TERMINAL_PANES:
            self.toast_label.set_label(self.t("split_pane_limit").format(limit=MAX_TERMINAL_PANES))
            return None
        return SplitPaneController(
            self.create_split_terminal,
            self.terminal_pane_container,
            self.replace_terminal_pane,
        ).split_terminal(session, terminal, direction)

    def terminal_pane_container(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> Gtk.Widget | None:
        pane = session.pane_for_terminal(terminal)
        return pane.container if pane is not None else None

    def start_split_child_terminal(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        source_terminal: Vte.Terminal,
        server: Server | None,
        *,
        announce: bool,
        fallback_working_directory: str | None = None,
    ) -> None:
        source_pane = self.pane_state(session, source_terminal)
        selected_server = server
        if selected_server is None and source_pane.server_id is not None:
            selected_server = find_server(self.store.data.servers, source_pane.server_id)
        if selected_server is None:
            profile = (
                find_local_terminal_profile(self.store.data.local_terminals, source_pane.local_profile_id)
                if source_pane.local_profile_id is not None
                else None
            )
            self.start_local_split_terminal(
                session,
                terminal,
                source_terminal,
                fallback_working_directory,
                profile=profile,
            )
            return
        self.start_ssh_split_terminal(session, terminal, selected_server, announce=announce)

    def apply_split_layout(
        self,
        session: TerminalSession,
        layout: str,
        *,
        server: Server | None = None,
        fallback_working_directory: str | None = None,
    ) -> None:
        plan = split_layout_plan(layout)
        if not plan:
            return
        terminals: dict[str, Vte.Terminal] = {"root": session.terminal}
        for target_id, direction, new_id in plan:
            target = terminals.get(target_id)
            if target is None:
                return
            new_terminal = self.split_terminal_pane(session, target, direction)
            if new_terminal is None:
                return
            terminals[new_id] = new_terminal
            self.start_split_child_terminal(
                session,
                new_terminal,
                target,
                server,
                announce=False,
                fallback_working_directory=fallback_working_directory,
            )

    def split_terminal_from_menu(
        self,
        popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
        direction: str,
    ) -> None:
        popover.popdown()
        new_terminal = self.split_terminal_pane(session, terminal, direction)
        if new_terminal is None:
            return
        self.start_split_child_terminal(session, new_terminal, terminal, None, announce=True)

    def show_split_connection_dialog(
        self,
        popover: Gtk.Popover,
        session: TerminalSession,
        source_terminal: Vte.Terminal,
    ) -> None:
        popover.popdown()
        if len(session.panes) >= MAX_TERMINAL_PANES:
            self.toast_label.set_label(self.t("split_pane_limit").format(limit=MAX_TERMINAL_PANES))
            return
        if not self.store.data.servers and not self.store.data.local_terminals:
            self.toast_label.set_label(self.t("split_connection_none_available"))
            return

        dialog = Gtk.Dialog(
            title=self.t("open_connection_in_split"),
            transient_for=self,
            modal=True,
        )
        dialog.set_resizable(True)
        dialog.set_default_size(640, 460)
        _cancel_button, open_button = self.add_dialog_action_buttons(dialog, self.t("open"))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        direction_combo = Gtk.ComboBoxText()
        for direction in ("up", "down", "right", "left"):
            direction_combo.append(direction, self.t(f"split_{direction}"))
        direction_combo.set_active_id("right")

        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text(self.t("search_connections"))
        connection_list = Gtk.ListBox()
        connection_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        connection_list.set_activate_on_single_click(False)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(260)
        scroller.set_vexpand(True)
        scroller.set_child(connection_list)
        connection_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        connection_box.set_hexpand(True)
        connection_box.append(search_entry)
        connection_box.append(scroller)
        choices = build_split_connection_choices(self.store.data.servers, self.store.data.local_terminals)
        state: dict[str, list[SplitConnectionChoice]] = {"choices": choices}
        self.refresh_split_connection_choices(connection_list, state, "", open_button)

        grid.attach(self.build_form_label(self.t("split_direction"), True), 0, 0, 1, 1)
        grid.attach(direction_combo, 1, 0, 1, 1)
        connection_label = self.build_form_label(self.t("connection"), True)
        connection_label.set_valign(Gtk.Align.START)
        grid.attach(connection_label, 0, 1, 1, 1)
        grid.attach(connection_box, 1, 1, 1, 1)
        dialog.get_content_area().append(grid)
        search_entry.connect(
            "search-changed",
            lambda entry: self.refresh_split_connection_choices(
                connection_list,
                state,
                entry.get_text(),
                open_button,
            ),
        )
        search_entry.connect(
            "activate",
            self.on_split_connection_search_activated,
            dialog,
            connection_list,
            state,
        )
        search_keys = Gtk.EventControllerKey.new()
        search_keys.connect("key-pressed", self.on_split_connection_search_key_pressed, connection_list)
        search_entry.add_controller(search_keys)
        connection_list.connect("row-activated", lambda _list, _row: dialog.response(Gtk.ResponseType.OK))
        dialog.connect(
            "response",
            self.on_split_connection_dialog_response,
            session,
            source_terminal,
            direction_combo,
            connection_list,
            state,
        )
        search_entry.grab_focus()
        dialog.present()

    def refresh_split_connection_choices(
        self,
        connection_list: Gtk.ListBox,
        state: dict[str, list[SplitConnectionChoice]],
        query: str,
        open_button: Gtk.Button,
    ) -> None:
        child = connection_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            connection_list.remove(child)
            child = next_child

        visible_choices = filter_split_connection_choices(state["choices"], query)
        state["visible_choices"] = visible_choices
        open_button.set_sensitive(bool(visible_choices))
        if not visible_choices:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=self.t("no_matching_connections"))
            label.set_xalign(0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(8)
            label.set_margin_end(8)
            row.set_child(label)
            row.set_selectable(False)
            connection_list.append(row)
            return

        for choice in visible_choices:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            box.set_margin_start(8)
            box.set_margin_end(8)
            title = Gtk.Label(
                label=(
                    self.t("split_ssh_option").format(name=choice.name)
                    if choice.kind == "server"
                    else self.t("split_local_option").format(name=choice.name)
                )
            )
            title.set_xalign(0)
            box.append(title)
            row.set_child(box)
            connection_list.append(row)
        connection_list.select_row(connection_list.get_row_at_index(0))

    def on_split_connection_search_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
        connection_list: Gtk.ListBox,
    ) -> bool:
        if keyval not in {Gdk.KEY_Up, Gdk.KEY_Down}:
            return False
        selected = connection_list.get_selected_row()
        if selected is None:
            selected = connection_list.get_row_at_index(0)
        if selected is None:
            return True
        target_index = selected.get_index() + (-1 if keyval == Gdk.KEY_Up else 1)
        target = connection_list.get_row_at_index(target_index)
        if target is not None:
            connection_list.select_row(target)
        return True

    def selected_split_connection_id(
        self,
        connection_list: Gtk.ListBox,
        state: dict[str, list[SplitConnectionChoice]],
    ) -> str | None:
        selected_row = connection_list.get_selected_row()
        visible_choices = state.get("visible_choices", [])
        if selected_row is None:
            return None
        selected_index = selected_row.get_index()
        if 0 <= selected_index < len(visible_choices):
            return visible_choices[selected_index].connection_id
        return None

    def on_split_connection_search_activated(
        self,
        _entry: Gtk.SearchEntry,
        dialog: Gtk.Dialog,
        connection_list: Gtk.ListBox,
        state: dict[str, list[SplitConnectionChoice]],
    ) -> None:
        if self.selected_split_connection_id(connection_list, state) is not None:
            dialog.response(Gtk.ResponseType.OK)

    def on_split_connection_dialog_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        session: TerminalSession,
        source_terminal: Vte.Terminal,
        direction_combo: Gtk.ComboBoxText,
        connection_list: Gtk.ListBox,
        state: dict[str, list[SplitConnectionChoice]],
    ) -> None:
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        direction = direction_combo.get_active_id()
        connection_id = self.selected_split_connection_id(connection_list, state)
        if direction is None or connection_id is None:
            dialog.destroy()
            return

        new_terminal = self.split_terminal_pane(session, source_terminal, direction)
        if new_terminal is None:
            dialog.destroy()
            return
        kind, profile_id = connection_id.split(":", 1)
        if kind == "server":
            server = find_server(self.store.data.servers, profile_id)
            if server is not None:
                self.start_ssh_split_terminal(session, new_terminal, server, announce=True)
            else:
                self.discard_unstarted_split_pane(session, new_terminal)
        else:
            profile = find_local_terminal_profile(self.store.data.local_terminals, profile_id)
            if profile is not None:
                self.start_local_split_terminal(
                    session,
                    new_terminal,
                    source_terminal,
                    profile=profile,
                )
            else:
                self.discard_unstarted_split_pane(session, new_terminal)
        dialog.destroy()

    def discard_unstarted_split_pane(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        self.mark_terminal_inactive(terminal, session)
        if terminal in session.split_terminals:
            session.split_terminals.remove(terminal)
        GLib.idle_add(self.remove_split_terminal_pane, terminal, session)

    def create_split_terminal(self, session: TerminalSession) -> Vte.Terminal:
        terminal = self.create_configured_terminal()
        toolbar, status_label, timer_label, focus_button, disconnect_button = self.build_session_status_bar(
            include_margins=True
        )
        container = self.build_terminal_pane(toolbar, terminal)
        source = session.pane_for_terminal(session.terminal)
        pane = TerminalPane(
            id=str(uuid4()),
            terminal=terminal,
            container=container,
            status_label=status_label,
            timer_label=timer_label,
            disconnect_button=disconnect_button,
            status_bar=toolbar,
            title=source.title if source is not None else session.title,
            started_at=time.monotonic(),
            server_id=source.server_id if source is not None else session.server_id,
            local_profile_id=source.local_profile_id if source is not None else session.local_profile_id,
        )
        session.panes[id(terminal)] = pane
        focus_button.connect("clicked", self.on_hide_pane_status_bar, session, terminal)
        disconnect_button.connect("clicked", self.on_request_disconnect_pane, session, terminal)
        self.configure_terminal_interactions(terminal, session)
        session.split_terminals.append(terminal)
        session.active_terminal_ids.add(id(terminal))
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
        fallback_working_directory: str | None = None,
        *,
        profile: LocalTerminalProfile | None = None,
    ) -> None:
        pane = self.pane_state(session, terminal)
        pane.server_id = None
        pane.local_profile_id = profile.id if profile is not None else None
        pane.title = self.local_terminal_session_title(profile)
        pane.started_at = time.monotonic()
        pane.connected = True
        pane.pending_reconnect = False
        pane.disconnect_requested = False
        pane.disconnect_button.set_label(self.t("disconnect"))
        pane.disconnect_button.set_sensitive(True)
        pane.status_label.set_label(self.t("connecting"))
        session.connected = True
        try:
            command = self.build_local_terminal_command(profile)
        except ValueError as exc:
            message = self.t("local_terminal_invalid_arguments").format(error=exc)
            terminal.feed(f"{message}\r\n".encode())
            pane.connected = False
            pane.status_label.set_label("Error")
            self.mark_pane_for_reconnect(session, pane, message)
            return
        working_directory = (
            self.local_terminal_profile_working_directory(profile)
            if profile is not None
            else self.local_terminal_working_directory(source_terminal, fallback_working_directory)
        )
        self.store.record_history_start(pane, "local")
        try:
            child_process = spawn_terminal_process(
                terminal,
                working_directory,
                command,
                build_terminal_environment(self.store.data.terminal.ls_colors),
            )
        except GLib.Error as exc:
            message = self.t("local_terminal_start_failed").format(error=exc.message)
            terminal.feed(f"{message}\r\n".encode())
            pane.connected = False
            pane.status_label.set_label("Error")
            self.store.record_history_end(pane, "failed", detail=exc.message)
            self.mark_pane_for_reconnect(session, pane, message)
            return
        pane.child_pid = child_process.pid
        pane.child_process = child_process
        pane.status_label.set_label(f"{pane.title} · PID {child_process.pid}")
        pane.timeout_id = GLib.timeout_add_seconds(1, self.update_pane_timer, session, terminal)
        session.split_child_pids[id(terminal)] = child_process.pid
        session.split_processes[id(terminal)] = child_process
        terminal.connect("child-exited", self.on_split_terminal_exited, session)
        if profile is not None and profile.command_on_start.strip():
            GLib.timeout_add(
                INITIAL_LOCAL_COMMAND_DELAY_MS,
                self.feed_initial_local_command,
                terminal,
                profile.command_on_start.strip(),
            )

    def start_ssh_split_terminal(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        server: Server,
        *,
        announce: bool = True,
    ) -> None:
        pane = self.pane_state(session, terminal)
        pane.server_id = server.id
        pane.local_profile_id = None
        pane.title = server.name
        pane.started_at = time.monotonic()
        pane.connected = True
        pane.pending_reconnect = False
        pane.disconnect_requested = False
        pane.disconnect_button.set_label(self.t("disconnect"))
        pane.disconnect_button.set_sensitive(True)
        pane.status_label.set_label(self.t("connecting"))
        session.connected = True
        self.store.record_history_start(pane, "ssh", server)
        ssh_path = GLib.find_program_in_path("ssh")
        if ssh_path is None:
            message = self.t("ssh_missing")
            terminal.feed(f"{message}\r\n".encode())
            pane.connected = False
            pane.status_label.set_label(self.t("ssh_missing_status"))
            self.store.record_history_end(pane, "failed", detail=message)
            self.mark_pane_for_reconnect(session, pane, message)
            return

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
                pane.connected = False
                pane.status_label.set_label(self.t("sshpass_missing_status"))
                self.store.record_history_end(pane, "failed", detail=message)
                self.mark_pane_for_reconnect(session, pane, message)
                return
            command = build_ssh_command(server, ssh_path, sshpass_path=sshpass_path)
        else:
            command = build_ssh_command(server, ssh_path)
        terminal.feed(f"{self.t('ssh_connecting_command').format(command=' '.join(command))}\r\n\r\n".encode())
        try:
            child_process = spawn_terminal_process(terminal, None, command, envv)
        except GLib.Error as exc:
            message = self.t("ssh_start_failed").format(error=exc.message)
            terminal.feed(f"{message}\r\n".encode())
            pane.connected = False
            pane.status_label.set_label("Error")
            self.store.record_history_end(pane, "failed", detail=exc.message)
            self.mark_pane_for_reconnect(
                session,
                pane,
                self.t("ssh_start_failed_toast").format(name=server.name),
            )
            return
        pane.child_pid = child_process.pid
        pane.child_process = child_process
        pane.status_label.set_label(f"{server.name} · PID {child_process.pid}")
        pane.timeout_id = GLib.timeout_add_seconds(1, self.update_pane_timer, session, terminal)
        session.split_child_pids[id(terminal)] = child_process.pid
        session.split_processes[id(terminal)] = child_process
        terminal.connect("child-exited", self.on_split_terminal_exited, session)
        self.record_connection(server.id)
        if announce:
            self.toast_label.set_label(self.t("session_opened").format(title=server.name))

    def local_terminal_working_directory(
        self,
        terminal: Vte.Terminal,
        fallback_working_directory: str | None = None,
    ) -> str:
        uri = terminal.get_current_directory_uri()
        if uri:
            parsed = urlparse(uri)
            if parsed.scheme == "file":
                return unquote(parsed.path)
        if fallback_working_directory:
            return fallback_working_directory
        return str(Path.home())

    def on_split_terminal_exited(self, terminal: Vte.Terminal, _status: int, session: TerminalSession) -> None:
        pane = session.pane_for_terminal(terminal)
        session.split_child_pids.pop(id(terminal), None)
        session.split_processes.pop(id(terminal), None)
        self.mark_terminal_inactive(terminal, session)
        if pane is not None:
            self.record_pane_duration(pane)
            result = "disconnected" if pane.disconnect_requested else (
                "closed" if self.child_status_successful(_status) else "failed"
            )
            self.store.record_history_end(pane, result)
            pane.connected = False
            pane.disconnect_button.set_sensitive(False)
            pane.status_label.set_label(
                self.t("session_disconnected_status").format(title=pane.title)
                if pane.disconnect_requested
                else self.t("session_closed_status").format(title=pane.title)
            )
        self.save_statistics_now()
        if (
            pane is not None
            and not pane.disconnect_requested
            and not self.child_status_successful(_status)
        ):
            self.mark_pane_for_reconnect(
                session,
                pane,
                self.t("connection_failed_toast").format(title=pane.title),
            )
            return
        if terminal in session.split_terminals:
            session.split_terminals.remove(terminal)
        if self.should_close_tab_after_terminal_exit(session):
            self.close_tab(session.id, session.page, disconnect=False)
            return
        if not session.active_terminal_ids:
            session.connected = False
            session.disconnect_button.set_sensitive(False)
            session.status_label.set_label(self.t("session_closed_status").format(title=session.title))
            self.update_session_tab_title(session, self.t("tab_closed_title").format(title=session.title))
        GLib.idle_add(self.remove_split_terminal_pane, terminal, session)

    def remove_split_terminal_pane(self, terminal: Vte.Terminal, session: TerminalSession) -> bool:
        pane = session.pane_for_terminal(terminal)
        if pane is None:
            return GLib.SOURCE_REMOVE
        parent = pane.container.get_parent()
        if not isinstance(parent, Gtk.Paned):
            return GLib.SOURCE_REMOVE

        sibling = (
            parent.get_end_child()
            if parent.get_start_child() is pane.container
            else parent.get_start_child()
        )
        if sibling is None:
            return GLib.SOURCE_REMOVE
        self.replace_split_container(parent, sibling)
        session.panes.pop(id(terminal), None)
        if self.should_close_tab_after_terminal_exit(session):
            self.close_tab(session.id, session.page, disconnect=False)
            return GLib.SOURCE_REMOVE
        active_panes = session.active_panes()
        if active_panes:
            active_panes[-1].terminal.grab_focus()
        return GLib.SOURCE_REMOVE

    def remove_terminal_pane_if_split(self, terminal: Vte.Terminal, session: TerminalSession) -> None:
        pane = session.pane_for_terminal(terminal)
        if pane is None:
            return
        parent = pane.container.get_parent()
        if not isinstance(parent, Gtk.Paned):
            return
        GLib.idle_add(self.remove_split_terminal_pane, terminal, session)

    def mark_terminal_inactive(self, terminal: Vte.Terminal, session: TerminalSession) -> None:
        session.active_terminal_ids.discard(id(terminal))

    def should_close_tab_after_terminal_exit(self, session: TerminalSession) -> bool:
        return self.store.data.app.close_tab_on_ssh_exit and not session.active_terminal_ids

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

    def toggle_session_status_bar_from_menu(
        self,
        popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        popover.popdown()
        pane = self.pane_state(session, terminal)
        self.set_pane_status_bar_visibility(pane, not pane.status_bar.get_visible())
        terminal.grab_focus()

    def disconnect_from_terminal_menu(
        self,
        popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        popover.popdown()
        self.on_request_disconnect_pane(None, session, terminal)

    def copy_terminal_selection(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.copy_clipboard_format(Vte.Format.TEXT)

    def paste_terminal_clipboard(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.paste_clipboard()

    def configure_terminal_from_menu(self, popover: Gtk.Popover) -> None:
        popover.popdown()
        self.on_terminal_settings(None)

    def show_session_statistics(
        self,
        popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        popover.popdown()
        pane = self.pane_state(session, terminal)
        server_connections = 0
        if pane.server_id is not None:
            server_connections = self.store.data.statistics.server_connections.get(pane.server_id, 0)
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

    def on_send_files_to_server(self, popover: Gtk.Popover, server: Server) -> None:
        popover.popdown()
        FileTransferController(
            self,
            self.t,
            self.toast_label,
            self.add_dialog_action_button,
            self.has_known_host_key,
        ).open_file_selection(server)

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
        pane = session.pane_for_terminal(session.terminal)
        if pane is not None:
            pane.title = title
        self.update_session_tab_title(session, title)

    def apply_terminal_settings(self, terminal: Vte.Terminal) -> None:
        TerminalViewFactory(self.resolved_terminal_font_family).apply_settings(
            terminal,
            self.store.data.terminal,
            audible_bell=self.store.data.app.audible_bell,
        )

    def apply_terminal_settings_to_open_tabs(self) -> None:
        for session in self.session_registry.sessions():
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

    def update_pane_timer(self, session: TerminalSession, terminal: Vte.Terminal) -> bool:
        pane = session.pane_for_terminal(terminal)
        if pane is None or not pane.connected:
            return GLib.SOURCE_REMOVE
        elapsed = int(time.monotonic() - pane.started_at)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        pane.timer_label.set_label(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        return GLib.SOURCE_CONTINUE

    def terminate_split_processes(self, session: TerminalSession) -> None:
        for process in tuple(session.split_processes.values()):
            self.terminate_terminal_process(process)
        session.split_child_pids.clear()
        session.split_processes.clear()

    def terminate_terminal_process(self, process: TerminalProcess, *, force: bool = False) -> bool:
        signum = signal.SIGKILL if force else signal.SIGTERM
        terminated = signal_terminal_process(process, signum)
        if terminated and not force:
            GLib.timeout_add(500, self.force_terminate_terminal_process, process)
        return terminated

    def force_terminate_terminal_process(self, process: TerminalProcess) -> bool:
        self.terminate_terminal_process(process, force=True)
        return GLib.SOURCE_REMOVE

    def terminate_open_terminal_processes(self, *, force: bool = False) -> None:
        for session in self.session_registry.sessions():
            if session.child_process is not None:
                self.terminate_terminal_process(session.child_process, force=force)
            for process in tuple(session.split_processes.values()):
                self.terminate_terminal_process(process, force=force)

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

    def close_pending_reconnect_pane(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        pane = self.pane_state(session, terminal)
        pane.pending_reconnect = False
        if terminal is not session.terminal:
            self.discard_unstarted_split_pane(session, terminal)
            return
        self.close_tab(session.id, session.page, disconnect=False)

    def on_request_disconnect_pane(
        self,
        _button: Gtk.Button | None,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        pane = self.pane_state(session, terminal)
        if not pane.connected:
            if pane.pending_reconnect:
                self.close_pending_reconnect_pane(session, terminal)
            return
        if not self.store.data.app.confirm_disconnect:
            self.disconnect_pane(session, terminal)
            return
        self.confirm_session_action(
            session,
            self.t("disconnect_session_title"),
            self.t("disconnect_session_detail").format(title=pane.title),
            self.t("disconnect_session_confirm"),
            lambda: self.disconnect_pane(session, terminal),
        )

    def disconnect_pane(self, session: TerminalSession, terminal: Vte.Terminal) -> None:
        pane = self.pane_state(session, terminal)
        if not pane.connected:
            if pane.pending_reconnect:
                self.close_pending_reconnect_pane(session, terminal)
            return
        pane.disconnect_requested = True
        process = pane.child_process
        if process is not None and not self.terminate_terminal_process(process):
            message = self.t("sigterm_failed")
            terminal.feed(f"{message}\r\n".encode())
            self.toast_label.set_label(message)
            pane.disconnect_requested = False
            return
        pane.disconnect_button.set_sensitive(False)
        pane.status_label.set_label(self.t("session_disconnected_status").format(title=pane.title))
        terminal.feed(f"\r\n{self.t('session_disconnected_terminal')}\r\n".encode())
        self.toast_label.set_label(self.t("session_disconnected_toast").format(title=pane.title))
        if process is None:
            self.mark_terminal_inactive(terminal, session)
            pane.connected = False
            self.store.record_history_end(pane, "disconnected")
            self.remove_terminal_pane_if_split(terminal, session)
        if (
            len(session.active_terminal_ids) <= 1
            and self.store.data.app.close_tab_on_disconnect
        ):
            self.close_tab(session.id, session.page, disconnect=False)

    def disconnect_session(self, session: TerminalSession) -> None:
        if not session.connected:
            return
        session.disconnect_requested = True
        for pane in session.panes.values():
            pane.disconnect_requested = True
        if session.child_process is not None and not self.terminate_terminal_process(session.child_process):
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
        terminal: Vte.Terminal,
        _status: int,
        server: Server,
        session: TerminalSession,
    ) -> None:
        self.mark_terminal_inactive(terminal, session)
        pane = self.pane_state(session, terminal)
        self.record_session_duration(session)
        self.save_statistics_now()
        result = "disconnected" if pane.disconnect_requested else (
            "closed" if self.child_status_successful(_status) else "failed"
        )
        self.store.record_history_end(session, result)
        pane.connected = False
        pane.disconnect_button.set_sensitive(False)
        if not pane.disconnect_requested and self.child_status_successful(_status) and session.active_terminal_ids:
            self.remove_terminal_pane_if_split(terminal, session)
            return
        session.connected = bool(session.active_terminal_ids)
        if pane.disconnect_requested:
            session.status_label.set_label(self.t("session_disconnected_status").format(title=session.title))
            self.toast_label.set_label(self.t("session_disconnected_toast").format(title=session.title))
            return
        if self.child_status_successful(_status):
            if self.should_close_tab_after_terminal_exit(session):
                self.close_tab(session.id, session.page, disconnect=False)
                self.toast_label.set_label(self.t("session_closed_toast").format(title=server.name))
                return
            self.remove_terminal_pane_if_split(terminal, session)
            session.status_label.set_label(self.t("session_closed_status").format(title=session.title))
            self.update_session_tab_title(session, self.t("tab_closed_title").format(title=session.title))
            self.toast_label.set_label(self.t("session_closed_toast").format(title=server.name))
            return
        session.status_label.set_label(f"Error: {session.title}")
        self.mark_session_for_reconnect(session, server, self.t("connection_failed_toast").format(title=server.name))
