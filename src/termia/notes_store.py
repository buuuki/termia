# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistence boundary for notes and categories."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config_io import CONNECTION_STORAGE_ENCRYPTED
from .config_io import InvalidMasterPasswordError, MissingMasterPasswordError
from .models import Note, NoteCategory
from .notes_io import (
    atomic_write,
    read_notes_file,
    write_notes_file,
)
from .notes import normalized_note_categories


class NotesFileStore:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = path
        self.read_only = read_only
        self.notes: list[Note] = []
        self.categories: list[NoteCategory] = []
        self.recovery_messages: list[str] = []
        self.encryption_locked = False
        self.encryption_error = ""

    def load(self, storage_mode: str, password: str | None = None) -> None:
        self.encryption_locked = False
        self.encryption_error = ""
        if not self.path.exists():
            self.notes, self.categories = [], []
            return
        try:
            notes, categories = read_notes_file(self.path, password)
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
        actual_mode = self.detect_storage_mode()
        if not self.read_only and actual_mode != storage_mode:
            self.save(storage_mode, password)

    def save(self, storage_mode: str, password: str | None = None) -> None:
        if self.read_only:
            return
        write_notes_file(
            self.path,
            self.notes,
            self.categories,
            storage_mode,
            password,
        )

    def detect_storage_mode(self) -> str:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "plain"
        format_name = payload.get("format") if isinstance(payload, dict) else None
        if format_name == "termia-notes-encrypted-v1":
            return CONNECTION_STORAGE_ENCRYPTED
        if format_name == "termia-notes-obfuscated-v1":
            return "obfuscated"
        return "plain"

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
