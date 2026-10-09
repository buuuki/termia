# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Notes domain rules, independent from GTK."""
from __future__ import annotations

from datetime import datetime, timezone

from .models import Note


class NoteError(ValueError):
    """A translation key describing invalid note data or operations."""


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def normalized_note_categories(categories: object, notes: list[Note]) -> list[str]:
    result: list[str] = []
    if isinstance(categories, list):
        for raw_name in categories:
            if not isinstance(raw_name, str):
                continue
            name = raw_name.strip()
            if name and name.casefold() not in {item.casefold() for item in result}:
                result.append(name)
    for note in notes:
        name = note.category.strip()
        if name and name.casefold() not in {item.casefold() for item in result}:
            result.append(name)
    return result


def normalize_note(
    note_id: str,
    title: str,
    content: str,
    category: str = "",
    server_id: str | None = None,
    created_at: str | None = None,
    modified_at: str | None = None,
    *,
    now: str | None = None,
) -> Note:
    note_id = note_id.strip()
    title = title.strip()
    category = category.strip()
    server_id = server_id.strip() if isinstance(server_id, str) else None
    if not content.strip():
        raise NoteError("note_content_required")
    if not note_id:
        raise NoteError("note_id_required")
    if not title:
        raise NoteError("note_title_required")
    if not content:
        raise NoteError("note_content_required")
    timestamp = now or timestamp_now()
    created_at = created_at.strip() if isinstance(created_at, str) else ""
    modified_at = modified_at.strip() if isinstance(modified_at, str) else ""
    return Note(
        id=note_id,
        title=title,
        content=content,
        category=category,
        server_id=server_id or None,
        created_at=created_at or timestamp,
        modified_at=modified_at or timestamp,
    )


def note_matches_query(note: Note, query: str) -> bool:
    query = query.strip().casefold()
    return not query or query in " ".join((note.title, note.content, note.category)).casefold()
