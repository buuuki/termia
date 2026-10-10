# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Notes domain rules, independent from GTK."""
from __future__ import annotations

from datetime import datetime, timezone

from .models import Note, NoteCategory


class NoteError(ValueError):
    """A translation key describing invalid note data or operations."""


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def normalized_note_categories(
    categories: object, notes: list[Note],
) -> list[NoteCategory]:
    """Normalize scoped categories and migrate legacy shared name lists."""
    result: list[NoteCategory] = []
    seen: set[tuple[str | None, str]] = set()

    def add(name: object, server_id: object) -> None:
        if not isinstance(name, str):
            return
        clean_name = name.strip()
        clean_server_id = server_id.strip() if isinstance(server_id, str) else None
        if not clean_name:
            return
        key = (clean_server_id or None, clean_name.casefold())
        if key in seen:
            return
        seen.add(key)
        result.append(NoteCategory(clean_name, key[0]))

    if isinstance(categories, list):
        legacy_names = all(isinstance(item, str) for item in categories)
        if legacy_names:
            used_scopes: dict[str, list[str | None]] = {}
            for note in notes:
                name = note.category.strip()
                if not name:
                    continue
                scopes = used_scopes.setdefault(name.casefold(), [])
                scope = note.server_id or None
                if scope not in scopes:
                    scopes.append(scope)
            for name in categories:
                scopes = used_scopes.get(name.strip().casefold()) or [None]
                for scope in scopes:
                    add(name, scope)
        else:
            for item in categories:
                if isinstance(item, NoteCategory):
                    add(item.name, item.server_id)
                elif isinstance(item, dict):
                    add(item.get("name"), item.get("server_id"))

    for note in notes:
        add(note.category, note.server_id)
    return result


def note_category_name(
    categories: list[NoteCategory], name: str, server_id: str | None,
) -> str | None:
    key = name.strip().casefold()
    if not key:
        return ""
    return next(
        (
            category.name for category in categories
            if category.server_id == (server_id or None)
            and category.name.casefold() == key
        ),
        None,
    )


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
