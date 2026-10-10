# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned and protected persistence for the separate notes file."""
from __future__ import annotations

import base64
import json
import os
import tempfile
import zlib
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    CONNECTION_STORAGE_MODES,
    CONNECTION_STORAGE_OBFUSCATED,
    CONNECTION_STORAGE_PLAIN,
    ENCRYPTED_CONNECTIONS_CIPHER,
    ENCRYPTED_CONNECTIONS_ITERATIONS,
    ENCRYPTED_CONNECTIONS_KDF,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
    derive_connections_key,
)
from .models import Note, NoteCategory
from .notes import normalize_note, normalized_note_categories

CURRENT_NOTES_SCHEMA_VERSION = 2
NOTES_OBFUSCATED_FORMAT = "termia-notes-obfuscated-v1"
NOTES_ENCRYPTED_FORMAT = "termia-notes-encrypted-v1"
NOTES_EXPORT_FORMAT = "termia-notes-export-v1"
NOTES_EXPORT_ENCRYPTED_FORMAT = "termia-notes-export-encrypted-v1"


def notes_payload(
    notes: list[Note], categories: list[NoteCategory],
) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_NOTES_SCHEMA_VERSION,
        "categories": [
            asdict(category)
            for category in normalized_note_categories(categories, notes)
        ],
        "notes": [asdict(note) for note in notes],
    }


def encode_notes_payload(
    payload: dict[str, Any], storage_mode: str, password: str | None = None,
) -> dict[str, Any]:
    mode = storage_mode if storage_mode in CONNECTION_STORAGE_MODES else CONNECTION_STORAGE_PLAIN
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if mode == CONNECTION_STORAGE_OBFUSCATED:
        return {
            "format": NOTES_OBFUSCATED_FORMAT,
            "encoding": "zlib+base64",
            "payload": base64.b64encode(zlib.compress(raw)).decode("ascii"),
        }
    if mode == CONNECTION_STORAGE_ENCRYPTED:
        return _encrypted_envelope(raw, password, NOTES_ENCRYPTED_FORMAT)
    return payload


def encode_notes_export(
    notes: list[Note], categories: list[NoteCategory], password: str | None = None,
) -> dict[str, Any]:
    payload = notes_payload(notes, categories)
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if password:
        return _encrypted_envelope(raw, password, NOTES_EXPORT_ENCRYPTED_FORMAT)
    return {"format": NOTES_EXPORT_FORMAT, **payload}


def _encrypted_envelope(raw: bytes, password: str | None, format_name: str) -> dict[str, Any]:
    if not password:
        raise MissingMasterPasswordError("Encrypted notes require a password.")
    salt, nonce = os.urandom(16), os.urandom(12)
    key = derive_connections_key(password, salt, ENCRYPTED_CONNECTIONS_ITERATIONS)
    ciphertext = AESGCM(key).encrypt(nonce, raw, None)
    return {
        "format": format_name,
        "cipher": ENCRYPTED_CONNECTIONS_CIPHER,
        "kdf": ENCRYPTED_CONNECTIONS_KDF,
        "iterations": ENCRYPTED_CONNECTIONS_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "payload": base64.b64encode(ciphertext).decode("ascii"),
    }


def decode_notes_payload(raw_payload: dict[str, Any], password: str | None = None) -> dict[str, Any]:
    format_name = raw_payload.get("format")
    if format_name in {NOTES_ENCRYPTED_FORMAT, NOTES_EXPORT_ENCRYPTED_FORMAT}:
        payload = _decrypt_envelope(raw_payload, password)
    elif format_name == NOTES_OBFUSCATED_FORMAT:
        encoded = raw_payload.get("payload")
        if not isinstance(encoded, str):
            raise ValueError("Obfuscated notes payload is invalid.")
        try:
            payload = json.loads(zlib.decompress(base64.b64decode(encoded)).decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Could not decode obfuscated notes.") from exc
    elif format_name == NOTES_EXPORT_FORMAT:
        payload = {key: value for key, value in raw_payload.items() if key != "format"}
    elif format_name is None:
        payload = raw_payload
    else:
        raise ValueError("Unsupported notes file format.")
    if not isinstance(payload, dict):
        raise ValueError("Notes payload must contain a JSON object.")
    return validate_notes_payload(payload)


def _decrypt_envelope(payload: dict[str, Any], password: str | None) -> dict[str, Any]:
    if not password:
        raise MissingMasterPasswordError("Encrypted notes require a password.")
    if payload.get("cipher") != ENCRYPTED_CONNECTIONS_CIPHER or payload.get("kdf") != ENCRYPTED_CONNECTIONS_KDF:
        raise ValueError("Encrypted notes use an unsupported format.")
    salt, nonce, encoded = payload.get("salt"), payload.get("nonce"), payload.get("payload")
    iterations = payload.get("iterations")
    if not all(isinstance(item, str) for item in (salt, nonce, encoded)):
        raise ValueError("Encrypted notes payload is incomplete.")
    if not isinstance(iterations, int) or iterations < 100_000:
        raise ValueError("Encrypted notes use invalid KDF settings.")
    try:
        key = derive_connections_key(
            password, base64.b64decode(salt), iterations,
        )
        raw = AESGCM(key).decrypt(base64.b64decode(nonce), base64.b64decode(encoded), None)
        decoded = json.loads(raw.decode("utf-8"))
    except InvalidTag as exc:
        raise InvalidMasterPasswordError("Could not decrypt notes with this password.") from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Could not decode encrypted notes.") from exc
    if not isinstance(decoded, dict):
        raise ValueError("Decrypted notes payload must be a JSON object.")
    return decoded


def validate_notes_payload(payload: dict[str, Any]) -> dict[str, Any]:
    version = payload.get("schema_version", 0)
    if not isinstance(version, int) or version < 0 or version > CURRENT_NOTES_SCHEMA_VERSION:
        raise ValueError("Notes file uses an unsupported schema version.")
    raw_notes = payload.get("notes", [])
    raw_categories = payload.get("categories", [])
    if not isinstance(raw_notes, list) or not isinstance(raw_categories, list):
        raise ValueError("Notes and categories must be lists.")
    notes: list[Note] = []
    ids: set[str] = set()
    for item in raw_notes:
        if not isinstance(item, dict):
            raise ValueError("A note entry is invalid.")
        try:
            note = normalize_note(
                item.get("id", "") if isinstance(item.get("id", ""), str) else "",
                item.get("title", "") if isinstance(item.get("title", ""), str) else "",
                item.get("content", "") if isinstance(item.get("content", ""), str) else "",
                item.get("category", "") if isinstance(item.get("category", ""), str) else "",
                item.get("server_id") if isinstance(item.get("server_id"), str) else None,
                item.get("created_at") if isinstance(item.get("created_at"), str) else None,
                item.get("modified_at") if isinstance(item.get("modified_at"), str) else None,
            )
        except ValueError as exc:
            raise ValueError("A note entry is invalid or incomplete.") from exc
        if note.id in ids:
            raise ValueError("Notes file contains duplicate note IDs.")
        ids.add(note.id)
        notes.append(note)
    if version < 2:
        if any(not isinstance(item, str) for item in raw_categories):
            raise ValueError("Legacy note categories must be names.")
        legacy_keys = [item.strip().casefold() for item in raw_categories]
        if any(not item for item in legacy_keys) or len(set(legacy_keys)) != len(legacy_keys):
            raise ValueError("Notes file contains invalid or duplicate categories.")
    categories = normalized_note_categories(raw_categories, notes)
    if version >= 2:
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str)
            or (item.get("server_id") is not None and not isinstance(item.get("server_id"), str))
            for item in raw_categories
        ):
            raise ValueError("Scoped note categories are invalid.")
        raw_keys = [
            (
                (item.get("server_id") or None), item["name"].strip().casefold(),
            )
            for item in raw_categories
        ]
        if any(not name for _scope, name in raw_keys) or len(set(raw_keys)) != len(raw_keys):
            raise ValueError("Notes file contains invalid or duplicate categories.")
    canonical = {
        (category.server_id, category.name.casefold()): category.name
        for category in categories
    }
    for note in notes:
        if note.category:
            note.category = canonical[(note.server_id, note.category.casefold())]
    return {
        "schema_version": CURRENT_NOTES_SCHEMA_VERSION,
        "categories": [asdict(category) for category in categories],
        "notes": [asdict(note) for note in notes],
    }


def notes_from_payload(
    payload: dict[str, Any],
) -> tuple[list[Note], list[NoteCategory]]:
    validated = validate_notes_payload(payload)
    notes = [Note(**item) for item in validated["notes"]]
    return notes, [NoteCategory(**item) for item in validated["categories"]]


def read_notes_file(
    path: Path, password: str | None = None,
) -> tuple[list[Note], list[NoteCategory]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Notes file must contain a JSON object.")
    return notes_from_payload(decode_notes_payload(payload, password))


def write_notes_file(
    path: Path,
    notes: list[Note],
    categories: list[NoteCategory],
    storage_mode: str,
    password: str | None = None,
) -> None:
    encoded = encode_notes_payload(notes_payload(notes, categories), storage_mode, password)
    atomic_write(path, json.dumps(encoded, indent=2, ensure_ascii=False).encode("utf-8"))


def export_notes_file(
    path: Path, notes: list[Note], categories: list[NoteCategory],
    password: str | None = None,
) -> None:
    encoded = encode_notes_export(notes, categories, password)
    atomic_write(path, json.dumps(encoded, indent=2, ensure_ascii=False).encode("utf-8"))


def import_notes_file(
    path: Path, password: str | None = None,
) -> tuple[list[Note], list[NoteCategory]]:
    return read_notes_file(path, password)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
