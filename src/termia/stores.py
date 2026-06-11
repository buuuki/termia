# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .constants import APP_THEMES, LEGACY_ANSI_PALETTE, SETTINGS_FILE, STATISTICS_FILE
from .i18n import LANGUAGES, detect_system_language
from .models import (
    DEFAULT_ANSI_PALETTE,
    AppSettings,
    Group,
    Server,
    StatisticsSettings,
    StoreData,
    TerminalSettings,
)


class StatisticsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = StatisticsSettings()
        self.load()

    def load(self) -> None:
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.data = StatisticsSettings(**payload)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(self.data), indent=2), encoding="utf-8")
        self.path.chmod(0o600)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.app = AppSettings()
        self.terminal = TerminalSettings()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        app_payload = payload.get("app", {})
        app_fields = AppSettings.__dataclass_fields__
        self.app = AppSettings(**{key: value for key, value in app_payload.items() if key in app_fields})
        self.terminal = normalize_terminal_settings(TerminalSettings(**payload.get("terminal", {})))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "app": asdict(self.app),
            "terminal": asdict(self.terminal),
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.path.chmod(0o600)


def normalize_terminal_settings(terminal: TerminalSettings) -> TerminalSettings:
    if (
        terminal.font_family == "Ubuntu Mono"
        and terminal.font_size == 13
        and terminal.foreground == "#839496"
        and terminal.background == "#002b36"
    ):
        terminal.font_family = "JetBrains Mono"
        terminal.foreground = "#eeeeec"
        terminal.background = "#2e3436"
    if terminal.ansi_palette == LEGACY_ANSI_PALETTE:
        terminal.ansi_palette = DEFAULT_ANSI_PALETTE.copy()
    return terminal


class ConnectionStore:
    def __init__(
        self,
        path: Path,
        settings_path: Path = SETTINGS_FILE,
        statistics_path: Path = STATISTICS_FILE,
    ) -> None:
        self.path = path
        self.settings_store = SettingsStore(settings_path)
        self.statistics_store = StatisticsStore(statistics_path)
        self.data = StoreData(
            terminal=self.settings_store.terminal,
            app=self.settings_store.app,
            statistics=self.statistics_store.data,
        )
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.data = StoreData(
                terminal=self.settings_store.terminal,
                app=self.settings_store.app,
                statistics=self.statistics_store.data,
            )
            return

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        legacy_statistics = payload.get("statistics")
        if legacy_statistics and not self.statistics_store.path.exists():
            self.statistics_store.data = StatisticsSettings(**legacy_statistics)
            self.statistics_store.save()

        app = self.settings_store.app
        terminal = self.settings_store.terminal
        settings_migrated = False
        if not self.settings_store.path.exists() and ("app" in payload or "terminal" in payload):
            app_payload = payload.get("app", {})
            app_fields = AppSettings.__dataclass_fields__
            app = AppSettings(**{key: value for key, value in app_payload.items() if key in app_fields})
            terminal = normalize_terminal_settings(TerminalSettings(**payload.get("terminal", {})))
            self.settings_store.app = app
            self.settings_store.terminal = terminal
            self.settings_store.save()
            settings_migrated = True

        self.data = StoreData(
            groups=[Group(**item) for item in payload.get("groups", [])],
            servers=[Server(**item) for item in payload.get("servers", [])],
            terminal=terminal,
            app=app,
            statistics=self.statistics_store.data,
        )
        repaired = self.repair_references()
        if "statistics" in payload or "app" in payload or "terminal" in payload or repaired or settings_migrated:
            self.save_connections()

    def repair_references(self) -> bool:
        group_ids = {group.id for group in self.data.groups}
        repaired = False
        for group in self.data.groups:
            if group.parent_id is not None and group.parent_id not in group_ids:
                group.parent_id = None
                repaired = True
        for server in self.data.servers:
            if server.group_id is not None and server.group_id not in group_ids:
                server.group_id = None
                repaired = True
        return repaired

    def save_connections(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "groups": [asdict(group) for group in self.data.groups],
            "servers": [asdict(server) for server in self.data.servers],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.path.chmod(0o600)

    def save_settings(self) -> None:
        self.settings_store.app = self.data.app
        self.settings_store.terminal = self.data.terminal
        self.settings_store.save()

    def save(self) -> None:
        self.save_connections()
        self.save_settings()

    def save_statistics(self) -> None:
        self.statistics_store.data = self.data.statistics
        self.statistics_store.save()

    def add_group(self, name: str, parent_id: str | None = None) -> Group:
        group = Group(id=str(uuid4()), name=name.strip(), parent_id=parent_id)
        self.data.groups.append(group)
        self.save_connections()
        return group

    def update_group(self, group_id: str, name: str, parent_id: str | None = None) -> None:
        for group in self.data.groups:
            if group.id == group_id:
                group.name = name.strip()
                group.parent_id = parent_id
                break
        self.save_connections()

    def delete_group(self, group_id: str) -> None:
        group_ids = {group_id}
        pending = [group_id]
        while pending:
            parent_id = pending.pop()
            child_ids = [
                group.id for group in self.data.groups
                if group.parent_id == parent_id and group.id not in group_ids
            ]
            group_ids.update(child_ids)
            pending.extend(child_ids)
        self.data.groups = [group for group in self.data.groups if group.id not in group_ids]
        self.data.servers = [server for server in self.data.servers if server.group_id not in group_ids]
        self.save_connections()

    def add_server(
        self,
        name: str,
        host: str,
        user: str,
        port: int,
        group_id: str | None,
        password: str = "",
        public_key: str = "",
    ) -> Server:
        server = Server(
            id=str(uuid4()),
            name=name.strip(),
            host=host.strip(),
            user=user.strip(),
            port=port,
            group_id=group_id,
            password=password,
            public_key=public_key,
        )
        self.data.servers.append(server)
        self.save_connections()
        return server

    def update_server(
        self,
        server_id: str,
        name: str,
        host: str,
        user: str,
        port: int,
        group_id: str | None,
        password: str = "",
        public_key: str = "",
    ) -> None:
        for server in self.data.servers:
            if server.id == server_id:
                server.name = name.strip()
                server.host = host.strip()
                server.user = user.strip()
                server.port = port
                server.group_id = group_id
                server.password = password
                server.public_key = public_key
                break
        self.save_connections()

    def delete_server(self, server_id: str) -> None:
        self.data.servers = [server for server in self.data.servers if server.id != server_id]
        self.save_connections()

    def update_terminal_settings(
        self,
        font_family: str,
        font_size: int,
        foreground: str,
        background: str,
        ls_colors: str | None = None,
        prompt_enabled: bool | None = None,
        prompt_template: str | None = None,
        prompt_color: str | None = None,
    ) -> None:
        current = self.data.terminal
        self.data.terminal = TerminalSettings(
            font_family=font_family.strip() or "Monospace",
            font_size=max(6, min(font_size, 72)),
            foreground=foreground.strip() or "#f2f2f2",
            background=background.strip() or "#101010",
            ls_colors=ls_colors if ls_colors is not None else current.ls_colors,
            ansi_palette=current.ansi_palette or DEFAULT_ANSI_PALETTE.copy(),
            prompt_enabled=current.prompt_enabled if prompt_enabled is None else prompt_enabled,
            prompt_template=(prompt_template if prompt_template is not None else current.prompt_template) if (prompt_template if prompt_template is not None else current.prompt_template).strip() else r"\u@\h:\w\$ ",
            prompt_color=(prompt_color if prompt_color is not None else current.prompt_color).strip() or "#8ae234",
        )
        self.save_settings()

    def update_prompt_settings(self, enabled: bool, template: str, color: str) -> None:
        current = self.data.terminal
        self.data.terminal = TerminalSettings(
            font_family=current.font_family,
            font_size=current.font_size,
            foreground=current.foreground,
            background=current.background,
            ls_colors=current.ls_colors,
            ansi_palette=current.ansi_palette or DEFAULT_ANSI_PALETTE.copy(),
            prompt_enabled=enabled,
            prompt_template=template if template.strip() else r"\u@\h:\w\$ ",
            prompt_color=color.strip() or "#8ae234",
        )
        self.save_settings()

    def update_app_settings(
        self, theme: str, language: str, close_tab_on_disconnect: bool,
        confirm_disconnect: bool, confirm_close_app: bool,
        sudo_password_shortcut: bool, sudo_password_enter: bool, close_tab_on_ssh_exit: bool,
        open_local_terminal_on_startup: bool, show_sidebar_on_startup: bool, show_session_status_bar: bool,
    ) -> None:
        self.data.app = AppSettings(
            theme=theme if theme in APP_THEMES else "system",
            language=language if language in LANGUAGES else detect_system_language(),
            close_tab_on_disconnect=close_tab_on_disconnect,
            close_tab_on_ssh_exit=close_tab_on_ssh_exit,
            open_local_terminal_on_startup=open_local_terminal_on_startup,
            show_sidebar_on_startup=show_sidebar_on_startup,
            show_session_status_bar=show_session_status_bar,
            confirm_disconnect=confirm_disconnect,
            confirm_close_app=confirm_close_app,
            sudo_password_shortcut=sudo_password_shortcut,
            sudo_password_enter=sudo_password_enter,
        )
        self.save_settings()
