# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistence boundary for notes and categories."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
    StorageLimitError,
    read_storage_json,
)
from .models import Note, NoteCategory
from .notes import normalized_note_categories
from .notes_io import (
    CURRENT_NOTES_SCHEMA_VERSION,
    atomic_write,
    decode_notes_payload,
    notes_from_payload,
    write_notes_file,
)


class NotesFileStore:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = path
        self.read_only = read_only
        self.notes: list[Note] = []
        self.categories: list[NoteCategory] = []
        self.recovery_messages: list[str] = []
        self.encryption_locked = False
        self.encryption_error = ""
        self._backup_before_save = False
        self.resource_limit_error = False

    def load(self, storage_mode: str, password: str | None = None) -> None:
        if self.resource_limit_error:
            return  # A fresh instance is required after an explicit recovery.
        self.encryption_locked = False
        self.encryption_error = ""
        if not self.path.exists():
            self.notes, self.categories = [], []
            return
        try:
            raw = read_storage_json(self.path)
            payload = decode_notes_payload(raw, password, validate=False)
            notes, categories = notes_from_payload(payload)
            self._backup_before_save = payload.get("schema_version", 0) < CURRENT_NOTES_SCHEMA_VERSION
        except StorageLimitError:
            self.resource_limit_error = True
            return
        except MissingMasterPasswordError:
            self.encryption_locked = True
            return
        except InvalidMasterPasswordError as exc:
            self.encryption_locked = True
            self.encryption_error = str(exc)
            return
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            backup = self.backup_invalid_file()
            self.recovery_messages.append(str(backup or self.path))
            self.notes, self.categories = [], []
            return
        self.notes, self.categories = notes, categories
        format_name = raw.get("format")
        actual_mode = (CONNECTION_STORAGE_ENCRYPTED if format_name == "termia-notes-encrypted-v1"
                       else "obfuscated" if format_name == "termia-notes-obfuscated-v1" else "plain")
        if not self.read_only and actual_mode != storage_mode:
            self.save(storage_mode, password)

    def save(self, storage_mode: str, password: str | None = None) -> None:
        if self.read_only or self.resource_limit_error:
            return
        if self._backup_before_save:
            self.backup_current_file()
            self._backup_before_save = False
        write_notes_file(
            self.path,
            self.notes,
            self.categories,
            storage_mode,
            password,
        )

    def backup_invalid_file(self) -> Path | None:
        if not self.path.exists() or self.read_only:
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.name}.invalid-{stamp}")
        suffix = 1
        while backup.exists():
            backup = self.path.with_name(f"{self.path.name}.invalid-{stamp}-{suffix}")
            suffix += 1
        try:
            atomic_write(backup, self.path.read_bytes())
        except OSError:
            return None
        return backup

    def backup_current_file(self) -> Path | None:
        if not self.path.exists():
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.name}.backup-{stamp}")
        suffix = 1
        while backup.exists():
            backup = self.path.with_name(f"{self.path.name}.backup-{stamp}-{suffix}")
            suffix += 1
        atomic_write(backup, self.path.read_bytes())
        return backup

    def replace_data(
        self, notes: list[Note], categories: list[NoteCategory],
    ) -> None:
        self.notes = list(notes)
        self.categories = normalized_note_categories(categories, self.notes)
