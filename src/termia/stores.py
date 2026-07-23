# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import fcntl
import json
import os
import re
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .constants import (
    APP_THEMES,
    DEFAULT_PROMPT_COLOR,
    DEFAULT_TERMINAL_BACKGROUND,
    DEFAULT_TERMINAL_FONT_FAMILY,
    DEFAULT_TERMINAL_FOREGROUND,
    DEFAULT_SPLIT_SEPARATOR_COLOR,
    DEFAULT_SPLIT_SEPARATOR_THICKNESS,
    MAX_SPLIT_SEPARATOR_THICKNESS,
    HISTORY_FILE,
    INSTANCE_LOCK_FILE,
    SETTINGS_FILE,
    STATISTICS_FILE,
)
from .config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    CONNECTION_STORAGE_MODES,
    CONNECTION_STORAGE_PLAIN,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
    connection_storage_mode_from_payload,
    decoded_connections_payload,
    read_raw_connections_payload,
    write_connections_file,
)
from .debug import log_lock_failure, log_startup_context, log_store_state
from .i18n import LANGUAGES, detect_system_language
from .migrations import (
    CURRENT_SCHEMA_VERSION,
    migrate_connections_payload,
    migrate_embedded_settings_payload,
    migrate_embedded_statistics_payload,
    migrate_history_event_payload,
    migrate_legacy_terminal_settings,
    migrate_settings_payload,
    migrate_statistics_payload,
)
from .keybindings import normalize_keybindings
from .models import (
    DEFAULT_ANSI_PALETTE,
    AppSettings,
    ConnectionHistoryEntry,
    ConnectionHistoryEvent,
    Group,
    LocalTerminalProfile,
    Server,
    StatisticsSettings,
    StoreData,
    TerminalSettings,
)
from .terminal_config import normalize_split_layout
from .ui_state import TerminalSession


class ReadOnlyStoreError(RuntimeError):
    pass


class InstanceWriteLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None
        self.read_only = False
        self.acquire()

    def acquire(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+", encoding="utf-8")
        except OSError:
            self.read_only = True
            log_lock_failure(self.path, "open-failed")
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            self.read_only = True
            try:
                holder = self.path.read_text(encoding="utf-8").strip() or "unknown"
            except OSError:
                holder = "unknown"
            log_lock_failure(self.path, f"already-locked holder_pid={holder}")
            return
        handle.seek(0)
        handle.truncate(0)
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        self.handle = handle

    def close(self) -> None:
        if self.handle is None:
            return
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.handle.close()
        self.handle = None


class StatisticsStore:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = path
        self.read_only = read_only
        self.data = StatisticsSettings()
        self.recovery_messages: list[str] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Statistics file must contain a JSON object.")
            payload, _ = migrate_statistics_payload(payload)
            fields = StatisticsSettings.__dataclass_fields__
            self.data = StatisticsSettings(**{key: value for key, value in payload.items() if key in fields})
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            backup = backup_invalid_file(self.path, self.read_only)
            self.recovery_messages.append(str(backup or self.path))

    def save(self) -> None:
        if self.read_only:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"schema_version": CURRENT_SCHEMA_VERSION, **asdict(self.data)}, indent=2),
            encoding="utf-8",
        )
        self.path.chmod(0o600)


class ConnectionHistoryStore:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = path
        self.read_only = read_only
        self.events: list[ConnectionHistoryEvent] = []
        self.entries: list[ConnectionHistoryEntry] = []
        self.recovery_messages: list[str] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            for raw_line in self.path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                payload, _ = migrate_history_event_payload(payload)
                fields = ConnectionHistoryEvent.__dataclass_fields__
                event = ConnectionHistoryEvent(**{key: value for key, value in payload.items() if key in fields})
                if not event.event_id:
                    event.event_id = str(uuid4())
                self.events.append(event)
        except OSError:
            self.recovery_messages.append(str(self.path))
            return
        self.rebuild_entries()

    def rebuild_entries(self) -> None:
        grouped: dict[str, ConnectionHistoryEntry] = {}
        for event in self.events:
            entry = grouped.get(event.session_id)
            if entry is None:
                entry = ConnectionHistoryEntry(session_id=event.session_id)
                grouped[event.session_id] = entry
            if event.kind:
                entry.kind = event.kind
            if event.title:
                entry.title = event.title
            if event.server_id:
                entry.server_id = event.server_id
            if event.server_name:
                entry.server_name = event.server_name
            if event.host:
                entry.host = event.host
            if event.port:
                entry.port = event.port
            if event.user:
                entry.user = event.user
            if event.event == "started":
                if event.timestamp:
                    entry.started_at = event.timestamp
                elif event.started_at:
                    entry.started_at = event.started_at
            elif event.event == "ended":
                if event.started_at:
                    entry.started_at = event.started_at
                elif event.timestamp and not entry.started_at:
                    entry.started_at = event.timestamp
                if event.ended_at:
                    entry.ended_at = event.ended_at
                elif event.timestamp:
                    entry.ended_at = event.timestamp
                if event.result:
                    entry.result = event.result
                if event.duration_seconds is not None:
                    entry.duration_seconds = event.duration_seconds
                if event.detail:
                    entry.detail = event.detail
        self.entries = sorted(
            grouped.values(),
            key=self.sort_key,
            reverse=True,
        )

    def sort_key(self, entry: ConnectionHistoryEntry) -> tuple[str, str]:
        return (entry.ended_at or entry.started_at, entry.session_id)

    def append_event(self, event: ConnectionHistoryEvent) -> bool:
        if self.read_only:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(event), ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
            self.path.chmod(0o600)
        except OSError:
            self.recovery_messages.append(str(self.path))
            return False
        self.events.append(event)
        self.rebuild_entries()
        return True

    def clear(self) -> None:
        if self.read_only:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")
            self.path.chmod(0o600)
        except OSError:
            self.recovery_messages.append(str(self.path))
            return
        self.events.clear()
        self.entries.clear()

    def _event_payload(
        self,
        session: TerminalSession,
        kind: str,
        event: str,
        timestamp: str,
        *,
        result: str = "",
        duration_seconds: float | None = None,
        detail: str = "",
    ) -> ConnectionHistoryEvent:
        return ConnectionHistoryEvent(
            event_id=str(uuid4()),
            session_id=session.id,
            kind=kind,
            event=event,
            timestamp=timestamp,
            started_at=session.history_started_at or timestamp,
            ended_at=timestamp if event == "ended" else "",
            result=result,
            duration_seconds=duration_seconds,
            title=session.history_title or session.title,
            server_id=session.server_id or "",
            server_name=session.history_server_name,
            host=session.history_host,
            port=session.history_port,
            user=session.history_user,
            detail=detail,
        )

    def record_start(self, session: TerminalSession, kind: str, *, server: Server | None = None) -> None:
        if self.read_only or session.history_start_recorded:
            return
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        if self.append_event(self._event_payload(session, kind, "started", timestamp)):
            session.history_start_recorded = True
            session.history_kind = kind
            session.history_started_at = timestamp
            session.history_title = session.title
            session.history_server_name = server.name if server is not None else session.title
            session.history_host = server.host if server is not None else ""
            session.history_user = server.user if server is not None else ""
            session.history_port = server.port if server is not None else 0

    def record_end(self, session: TerminalSession, result: str, *, detail: str = "") -> None:
        if self.read_only or session.history_end_recorded or not session.history_start_recorded:
            return
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        duration = max(0.0, time.monotonic() - session.started_at)
        if self.append_event(
            self._event_payload(
                session,
                session.history_kind,
                "ended",
                timestamp,
                result=result,
                duration_seconds=duration,
                detail=detail,
            )
        ):
            session.history_end_recorded = True

    def recent_server_ids(self, limit: int = 10) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        for entry in self.entries:
            if entry.server_id and entry.server_id not in seen:
                seen.add(entry.server_id)
                ids.append(entry.server_id)
            if len(ids) >= limit:
                break
        return ids


class SettingsStore:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = path
        self.read_only = read_only
        self.app = AppSettings()
        self.terminal = TerminalSettings()
        self.recovery_messages: list[str] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Settings file must contain a JSON object.")
            payload, _ = migrate_settings_payload(payload)
            app_payload = payload.get("app", {})
            app_fields = AppSettings.__dataclass_fields__
            self.app = normalize_app_settings(AppSettings(**{key: value for key, value in app_payload.items() if key in app_fields}))
            self.terminal = normalize_terminal_settings(TerminalSettings(**payload.get("terminal", {})))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            backup = backup_invalid_file(self.path, self.read_only)
            self.recovery_messages.append(str(backup or self.path))

    def save(self) -> None:
        if self.read_only:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "app": asdict(self.app),
            "terminal": asdict(self.terminal),
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.path.chmod(0o600)


def backup_invalid_file(path: Path, read_only: bool = False) -> Path | None:
    if not path.exists() or read_only:
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.invalid-{timestamp}")
    suffix = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.invalid-{timestamp}-{suffix}")
        suffix += 1
    try:
        path.replace(backup)
    except OSError:
        return None
    return backup


def normalize_app_settings(app: AppSettings) -> AppSettings:
    app.keybindings = normalize_keybindings(app.keybindings)
    return app


def normalize_terminal_settings(terminal: TerminalSettings) -> TerminalSettings:
    terminal, _ = migrate_legacy_terminal_settings(terminal)
    terminal.split_separator_thickness = max(
        1,
        min(
            terminal.split_separator_thickness or DEFAULT_SPLIT_SEPARATOR_THICKNESS,
            MAX_SPLIT_SEPARATOR_THICKNESS,
        ),
    )
    terminal.split_separator_color = normalize_css_color(
        terminal.split_separator_color,
        DEFAULT_SPLIT_SEPARATOR_COLOR,
    )
    return terminal


def normalize_css_color(value: str, default: str) -> str:
    color = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", color):
        return color
    if re.fullmatch(r"rgba?\([0-9., %]+\)", color):
        return color
    return default


class ConnectionStore:
    def __init__(
        self,
        path: Path,
        settings_path: Path = SETTINGS_FILE,
        statistics_path: Path = STATISTICS_FILE,
        lock_path: Path = INSTANCE_LOCK_FILE,
        history_path: Path = HISTORY_FILE,
    ) -> None:
        self.path = path
        self.instance_lock = InstanceWriteLock(lock_path)
        self.read_only = self.instance_lock.read_only
        self.settings_store = SettingsStore(settings_path, read_only=self.read_only)
        self.statistics_store = StatisticsStore(statistics_path, read_only=self.read_only)
        self.history_store = ConnectionHistoryStore(history_path, read_only=self.read_only)
        self.recovery_messages: list[str] = [
            *self.settings_store.recovery_messages,
            *self.statistics_store.recovery_messages,
            *self.history_store.recovery_messages,
        ]
        self.encryption_locked = False
        self.encryption_error = ""
        self.master_password: str | None = None
        self.data = StoreData(
            local_terminals=[],
            terminal=self.settings_store.terminal,
            app=self.settings_store.app,
            statistics=self.statistics_store.data,
        )
        log_startup_context(
            lock_path=lock_path,
            data_path=path,
            settings_path=settings_path,
            state_dir=history_path.parent,
        )
        self.load()
        log_store_state(self)

    def load(self) -> None:
        if not self.path.exists():
            self.data = StoreData(
                local_terminals=[],
                terminal=self.settings_store.terminal,
                app=self.settings_store.app,
                statistics=self.statistics_store.data,
            )
            return

        try:
            raw_payload = read_raw_connections_payload(self.path)
            file_storage_mode = connection_storage_mode_from_payload(raw_payload)
            payload = decoded_connections_payload(raw_payload, self.master_password)
            payload, connections_migrated = migrate_connections_payload(payload)
        except MissingMasterPasswordError:
            self.encryption_locked = True
            self.encryption_error = ""
            self.data = StoreData(
                local_terminals=[],
                terminal=self.settings_store.terminal,
                app=self.settings_store.app,
                statistics=self.statistics_store.data,
            )
            self.data.app.connection_storage_mode = CONNECTION_STORAGE_ENCRYPTED
            return
        except InvalidMasterPasswordError as exc:
            self.encryption_locked = True
            self.encryption_error = str(exc)
            self.data = StoreData(
                local_terminals=[],
                terminal=self.settings_store.terminal,
                app=self.settings_store.app,
                statistics=self.statistics_store.data,
            )
            self.data.app.connection_storage_mode = CONNECTION_STORAGE_ENCRYPTED
            return
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            backup = backup_invalid_file(self.path, self.read_only)
            self.recovery_messages.append(str(backup or self.path))
            self.data = StoreData(
                local_terminals=[],
                terminal=self.settings_store.terminal,
                app=self.settings_store.app,
                statistics=self.statistics_store.data,
            )
            return
        self.encryption_locked = False
        self.encryption_error = ""
        legacy_statistics, embedded_statistics_migrated = migrate_embedded_statistics_payload(payload)
        if legacy_statistics and not self.statistics_store.path.exists():
            fields = StatisticsSettings.__dataclass_fields__
            self.statistics_store.data = StatisticsSettings(
                **{key: value for key, value in legacy_statistics.items() if key in fields}
            )
            self.statistics_store.save()

        app = self.settings_store.app
        terminal = self.settings_store.terminal
        settings_migrated = False
        if not self.settings_store.path.exists():
            if "app" in payload or "terminal" in payload:
                embedded_settings, embedded_settings_migrated = migrate_embedded_settings_payload(payload)
                app_payload = embedded_settings.get("app", {})
                app_fields = AppSettings.__dataclass_fields__
                app = normalize_app_settings(AppSettings(**{key: value for key, value in app_payload.items() if key in app_fields}))
                terminal = normalize_terminal_settings(TerminalSettings(**embedded_settings.get("terminal", {})))
                settings_migrated = embedded_settings_migrated
            app.connection_storage_mode = file_storage_mode
            self.settings_store.app = app
            self.settings_store.terminal = terminal
            self.settings_store.save()
            settings_migrated = True

        self.data = StoreData(
            groups=[Group(**item) for item in payload.get("groups", [])],
            servers=[Server(**item) for item in payload.get("servers", [])],
            local_terminals=[LocalTerminalProfile(**item) for item in payload.get("local_terminals", [])],
            terminal=terminal,
            app=app,
            statistics=self.statistics_store.data,
        )
        split_layouts_normalized = self.normalize_split_layouts()
        repaired = self.repair_references()
        if (
            connections_migrated
            or embedded_statistics_migrated
            or "statistics" in payload
            or "app" in payload
            or "terminal" in payload
            or repaired
            or settings_migrated
            or split_layouts_normalized
        ):
            self.save_connections()

    def close(self) -> None:
        self.instance_lock.close()

    def ensure_writable(self) -> None:
        if self.read_only:
            raise ReadOnlyStoreError("This Termia instance is read-only.")
        if self.encryption_locked:
            raise ReadOnlyStoreError("Encrypted connections are locked.")

    def unlock_connections(self, master_password: str) -> bool:
        self.master_password = master_password
        self.load()
        if self.encryption_locked:
            self.master_password = None
            return False
        self.save_settings()
        return True

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

    def normalize_split_layouts(self) -> bool:
        changed = False
        for server in self.data.servers:
            normalized = normalize_split_layout(server.split_layout)
            if normalized != server.split_layout:
                server.split_layout = normalized
                changed = True
        for profile in self.data.local_terminals:
            normalized = normalize_split_layout(profile.split_layout)
            if normalized != profile.split_layout:
                profile.split_layout = normalized
                changed = True
        return changed

    def save_connections(self) -> None:
        if self.read_only or self.encryption_locked:
            return
        write_connections_file(
            self.path,
            self.data.groups,
            self.data.servers,
            self.data.local_terminals,
            self.data.app.connection_storage_mode,
            self.master_password,
        )

    def save_settings(self) -> None:
        if self.read_only:
            return
        self.settings_store.app = self.data.app
        self.settings_store.terminal = self.data.terminal
        self.settings_store.save()

    def save(self) -> None:
        if self.read_only:
            return
        self.save_connections()
        self.save_settings()

    def save_statistics(self) -> None:
        if self.read_only:
            return
        self.statistics_store.data = self.data.statistics
        self.statistics_store.save()

    def clear_history(self) -> None:
        self.ensure_writable()
        self.history_store.clear()

    def record_history_start(self, session: TerminalSession, kind: str, server: Server | None = None) -> None:
        self.history_store.record_start(session, kind, server=server)

    def record_history_end(self, session: TerminalSession, result: str, *, detail: str = "") -> None:
        self.history_store.record_end(session, result, detail=detail)

    def recent_server_ids(self, limit: int = 10) -> list[str]:
        return self.history_store.recent_server_ids(limit)

    def update_connection_storage_mode(self, storage_mode: str, master_password: str | None = None) -> None:
        self.ensure_writable()
        requested = storage_mode if storage_mode in CONNECTION_STORAGE_MODES else CONNECTION_STORAGE_PLAIN
        if requested == CONNECTION_STORAGE_ENCRYPTED:
            if master_password:
                self.master_password = master_password
            if not self.master_password:
                raise MissingMasterPasswordError("Encrypted connections require a master password.")
        else:
            self.master_password = None
        self.data.app.connection_storage_mode = requested
        self.save_settings()
        self.save_connections()

    def add_group(self, name: str, parent_id: str | None = None) -> Group:
        self.ensure_writable()
        group = Group(id=str(uuid4()), name=name.strip(), parent_id=parent_id)
        self.data.groups.append(group)
        self.save_connections()
        return group

    def update_group(self, group_id: str, name: str, parent_id: str | None = None) -> None:
        self.ensure_writable()
        for group in self.data.groups:
            if group.id == group_id:
                group.name = name.strip()
                group.parent_id = parent_id
                break
        self.save_connections()

    def delete_group(self, group_id: str) -> None:
        self.ensure_writable()
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
        favorite: bool = False,
        password: str = "",
        public_key: str = "",
        split_layout: str = "none",
    ) -> Server:
        self.ensure_writable()
        server = Server(
            id=str(uuid4()),
            name=name.strip(),
            host=host.strip(),
            user=user.strip(),
            port=port,
            group_id=group_id,
            favorite=favorite,
            password=password,
            public_key=public_key,
            split_layout=normalize_split_layout(split_layout),
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
        favorite: bool,
        password: str = "",
        public_key: str = "",
        split_layout: str = "none",
    ) -> None:
        self.ensure_writable()
        for server in self.data.servers:
            if server.id == server_id:
                server.name = name.strip()
                server.host = host.strip()
                server.user = user.strip()
                server.port = port
                server.group_id = group_id
                server.favorite = favorite
                server.password = password
                server.public_key = public_key
                server.split_layout = normalize_split_layout(split_layout)
                break
        self.save_connections()

    def update_server_favorite(self, server_id: str, favorite: bool) -> None:
        self.ensure_writable()
        for server in self.data.servers:
            if server.id == server_id:
                server.favorite = favorite
                break
        self.save_connections()

    def delete_server(self, server_id: str) -> None:
        self.ensure_writable()
        self.data.servers = [server for server in self.data.servers if server.id != server_id]
        self.save_connections()

    def add_local_terminal(
        self,
        name: str,
        working_directory: str,
        shell: str,
        arguments: str,
        command_on_start: str,
        tab_title: str,
        split_layout: str = "none",
    ) -> LocalTerminalProfile:
        self.ensure_writable()
        profile = LocalTerminalProfile(
            id=str(uuid4()),
            name=name.strip(),
            working_directory=working_directory.strip(),
            shell=shell.strip(),
            arguments=arguments.strip(),
            command_on_start=command_on_start.strip(),
            tab_title=tab_title.strip(),
            split_layout=normalize_split_layout(split_layout),
        )
        self.data.local_terminals.append(profile)
        self.save_connections()
        return profile

    def update_local_terminal(
        self,
        profile_id: str,
        name: str,
        working_directory: str,
        shell: str,
        arguments: str,
        command_on_start: str,
        tab_title: str,
        split_layout: str = "none",
    ) -> None:
        self.ensure_writable()
        updated = False
        for profile in self.data.local_terminals:
            if profile.id == profile_id:
                profile.name = name.strip()
                profile.working_directory = working_directory.strip()
                profile.shell = shell.strip()
                profile.arguments = arguments.strip()
                profile.command_on_start = command_on_start.strip()
                profile.tab_title = tab_title.strip()
                profile.split_layout = normalize_split_layout(split_layout)
                updated = True
                break
        if updated:
            self.save_connections()

    def delete_local_terminal(self, profile_id: str) -> None:
        self.ensure_writable()
        original_count = len(self.data.local_terminals)
        self.data.local_terminals = [profile for profile in self.data.local_terminals if profile.id != profile_id]
        if len(self.data.local_terminals) != original_count:
            self.save_connections()

    def update_terminal_settings(
        self,
        font_family: str,
        font_size: int,
        foreground: str,
        background: str,
        split_separator_color: str | None = None,
        split_separator_thickness: int | None = None,
        ls_colors: str | None = None,
        prompt_enabled: bool | None = None,
        prompt_template: str | None = None,
        prompt_color: str | None = None,
    ) -> None:
        self.ensure_writable()
        current = self.data.terminal
        self.data.terminal = TerminalSettings(
            font_family=font_family.strip() or DEFAULT_TERMINAL_FONT_FAMILY,
            font_size=max(6, min(font_size, 72)),
            foreground=foreground.strip() or DEFAULT_TERMINAL_FOREGROUND,
            background=background.strip() or DEFAULT_TERMINAL_BACKGROUND,
            split_separator_color=(
                split_separator_color if split_separator_color is not None else current.split_separator_color
            ).strip() or DEFAULT_SPLIT_SEPARATOR_COLOR,
            split_separator_thickness=max(
                1,
                min(
                    split_separator_thickness if split_separator_thickness is not None else current.split_separator_thickness,
                    MAX_SPLIT_SEPARATOR_THICKNESS,
                ),
            ),
            ls_colors=ls_colors if ls_colors is not None else current.ls_colors,
            ansi_palette=current.ansi_palette or DEFAULT_ANSI_PALETTE.copy(),
            prompt_enabled=current.prompt_enabled if prompt_enabled is None else prompt_enabled,
            prompt_template=(prompt_template if prompt_template is not None else current.prompt_template) if (prompt_template if prompt_template is not None else current.prompt_template).strip() else r"\u@\h:\w\$ ",
            prompt_color=(prompt_color if prompt_color is not None else current.prompt_color).strip() or DEFAULT_PROMPT_COLOR,
        )
        self.save_settings()

    def update_prompt_settings(self, enabled: bool, template: str, color: str) -> None:
        self.ensure_writable()
        current = self.data.terminal
        self.data.terminal = TerminalSettings(
            font_family=current.font_family,
            font_size=current.font_size,
            foreground=current.foreground,
            background=current.background,
            split_separator_color=current.split_separator_color,
            split_separator_thickness=current.split_separator_thickness,
            ls_colors=current.ls_colors,
            ansi_palette=current.ansi_palette or DEFAULT_ANSI_PALETTE.copy(),
            prompt_enabled=enabled,
            prompt_template=template if template.strip() else r"\u@\h:\w\$ ",
            prompt_color=color.strip() or DEFAULT_PROMPT_COLOR,
        )
        self.save_settings()

    def update_app_settings(self, app: AppSettings) -> None:
        self.ensure_writable()
        current = self.data.app
        self.data.app = AppSettings(
            theme=app.theme if app.theme in APP_THEMES else "system",
            language=app.language if app.language in LANGUAGES else detect_system_language(),
            close_tab_on_disconnect=app.close_tab_on_disconnect,
            close_tab_on_ssh_exit=app.close_tab_on_ssh_exit,
            open_local_terminal_on_startup=app.open_local_terminal_on_startup,
            show_sidebar_on_startup=app.show_sidebar_on_startup,
            show_session_status_bar=app.show_session_status_bar,
            confirm_disconnect=app.confirm_disconnect,
            confirm_close_app=app.confirm_close_app,
            sudo_password_shortcut=app.sudo_password_shortcut,
            sudo_password_enter=app.sudo_password_enter,
            connection_storage_mode=current.connection_storage_mode,
            statistics_enabled=app.statistics_enabled,
            debug_enabled=app.debug_enabled,
            keybindings=normalize_keybindings(current.keybindings),
        )
        self.save_settings()

    def update_keybindings(self, keybindings: dict[str, str]) -> None:
        self.ensure_writable()
        self.data.app.keybindings = normalize_keybindings(keybindings)
        self.save_settings()
