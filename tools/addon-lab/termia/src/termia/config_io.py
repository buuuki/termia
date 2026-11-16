# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import json
import os
import zlib
from dataclasses import asdict
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .migrations import CURRENT_CONNECTIONS_SCHEMA_VERSION, migrate_connections_payload
from .models import (
    CommandSnippet,
    Group,
    LocalTerminalProfile,
    Server,
    StoreData,
    Workspace,
)
from .snippets import (
    SnippetError,
    normalize_snippet,
    normalized_categories,
    snippet_target_exists,
)
from .workspace_layout import normalized_workspace_tabs

CONNECTION_STORAGE_PLAIN = "plain"
CONNECTION_STORAGE_OBFUSCATED = "obfuscated"
CONNECTION_STORAGE_ENCRYPTED = "encrypted"
CONNECTION_STORAGE_MODES = {CONNECTION_STORAGE_PLAIN, CONNECTION_STORAGE_OBFUSCATED, CONNECTION_STORAGE_ENCRYPTED}
OBFUSCATED_CONNECTIONS_FORMAT = "termia-connections-obfuscated-v1"
ENCRYPTED_CONNECTIONS_FORMAT = "termia-connections-encrypted-v1"
ENCRYPTED_CONNECTIONS_KDF = "pbkdf2-sha256"
ENCRYPTED_CONNECTIONS_CIPHER = "aes-256-gcm"
ENCRYPTED_CONNECTIONS_ITERATIONS = 390_000
MAX_KDF_ITERATIONS = 2_000_000
MAX_DECODED_BYTES = 32 * 1024 * 1024
MAX_STORAGE_BYTES = 48 * 1024 * 1024


class StorageLimitError(ValueError):
    """Policy rejection, never corruption recovery or permission to overwrite."""

    def __init__(self) -> None:
        super().__init__("Storage safety limit exceeded. Original files are unchanged. See the storage recovery guide.")


def check_size(data: bytes, maximum: int) -> bytes:
    if len(data) > maximum:
        raise StorageLimitError()
    return data


def validate_iterations(iterations: object) -> None:
    if type(iterations) is not int or iterations < 100_000:
        raise ValueError("Invalid KDF settings.")
    if iterations > MAX_KDF_ITERATIONS:
        raise StorageLimitError()


def decoded_json_bytes(payload: dict) -> bytes:
    compact = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    check_size(compact, MAX_DECODED_BYTES)
    return compact


def storage_json_bytes(payload: dict) -> bytes:
    return check_size(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"), MAX_STORAGE_BYTES)


def read_storage_bytes(path: Path) -> bytes:
    with path.open("rb") as stream:
        return check_size(stream.read(MAX_STORAGE_BYTES + 1), MAX_STORAGE_BYTES)


def read_storage_json(path: Path) -> dict:
    payload = json.loads(read_storage_bytes(path))
    if not isinstance(payload, dict):
        raise TypeError("Storage file must contain a JSON object.")
    return payload


def bounded_decompress(data: bytes) -> bytes:
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(data, MAX_DECODED_BYTES + 1)
    except zlib.error as exc:
        raise ValueError("Invalid compressed storage payload.") from exc
    check_size(raw, MAX_DECODED_BYTES)
    if decoder.unconsumed_tail:
        raise StorageLimitError()
    if not decoder.eof or decoder.unused_data:
        raise ValueError("Invalid compressed storage payload.")
    return raw


def encrypted_fields(payload: dict) -> tuple[bytes, bytes, bytes]:
    validate_iterations(payload.get("iterations"))
    fields = [payload.get(name) for name in ("salt", "nonce", "payload")]
    if not all(isinstance(value, str) for value in fields):
        raise ValueError("Encrypted storage fields are missing.")
    salt, nonce, encoded = fields
    # Check before decoding/deriving, including when no password was supplied.
    if len(salt) > 24 or len(nonce) > 16 or len(encoded) > 4 * ((MAX_DECODED_BYTES + 18) // 3):
        raise StorageLimitError()
    salt_bytes, nonce_bytes, ciphertext = [base64.b64decode(value, validate=True) for value in fields]
    check_size(ciphertext, MAX_DECODED_BYTES + 16)  # AES-GCM authentication tag.
    if len(salt_bytes) != 16 or len(nonce_bytes) != 12:
        raise ValueError("Invalid encrypted storage salt or nonce.")
    return salt_bytes, nonce_bytes, ciphertext


class MissingMasterPasswordError(ValueError):
    pass


class InvalidMasterPasswordError(ValueError):
    pass


def connections_payload(
    groups: list[Group],
    servers: list[Server],
    local_terminals: list[LocalTerminalProfile],
    storage_mode: str,
    master_password: str | None = None,
    workspaces: list[Workspace] | None = None,
    snippets: list[CommandSnippet] | None = None,
    snippet_categories: list[str] | None = None,
) -> dict[str, object]:
    payload = {
        "schema_version": CURRENT_CONNECTIONS_SCHEMA_VERSION,
        "groups": [asdict(group) for group in groups],
        "servers": [asdict(server) for server in servers],
        "local_terminals": [asdict(profile) for profile in local_terminals],
        "workspaces": [asdict(workspace) for workspace in workspaces or []],
        "snippets": [asdict(snippet) for snippet in snippets or []],
        "snippet_categories": normalized_categories(snippet_categories, snippets or []),
    }
    raw = decoded_json_bytes(payload)
    if storage_mode == CONNECTION_STORAGE_OBFUSCATED:
        encoded = base64.b64encode(zlib.compress(raw)).decode("ascii")
        return {
            "format": OBFUSCATED_CONNECTIONS_FORMAT,
            "encoding": "zlib+base64",
            "payload": encoded,
        }
    if storage_mode == CONNECTION_STORAGE_ENCRYPTED:
        if not master_password:
            raise MissingMasterPasswordError("Encrypted connections require a master password.")
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = derive_connections_key(master_password, salt, ENCRYPTED_CONNECTIONS_ITERATIONS)
        ciphertext = AESGCM(key).encrypt(nonce, raw, None)
        return {
            "format": ENCRYPTED_CONNECTIONS_FORMAT,
            "cipher": ENCRYPTED_CONNECTIONS_CIPHER,
            "kdf": ENCRYPTED_CONNECTIONS_KDF,
            "iterations": ENCRYPTED_CONNECTIONS_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "payload": base64.b64encode(ciphertext).decode("ascii"),
        }
    return payload


def derive_connections_key(master_password: str, salt: bytes, iterations: int) -> bytes:
    validate_iterations(iterations)
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    ).derive(master_password.encode("utf-8"))


def decoded_connections_payload(payload: dict[str, object], master_password: str | None = None) -> dict[str, object]:
    if payload.get("format") == ENCRYPTED_CONNECTIONS_FORMAT:
        return decrypted_connections_payload(payload, master_password)
    if payload.get("format") != OBFUSCATED_CONNECTIONS_FORMAT:
        decoded_json_bytes(payload)
        return payload
    encoded = payload.get("payload")
    if not isinstance(encoded, str):
        raise ValueError("Obfuscated connections payload is missing or invalid.")
    try:
        if len(encoded) > MAX_STORAGE_BYTES:
            raise StorageLimitError()
        raw = bounded_decompress(base64.b64decode(encoded.encode("ascii"), validate=True))
        decoded = json.loads(raw.decode("utf-8"))
    except StorageLimitError:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not decode obfuscated connections: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ValueError("Decoded obfuscated connections payload is not an object.")
    return decoded


def decrypted_connections_payload(payload: dict[str, object], master_password: str | None) -> dict[str, object]:
    salt_bytes, nonce_bytes, ciphertext = encrypted_fields(payload)
    if not master_password:
        raise MissingMasterPasswordError("Encrypted connections require a master password.")
    if payload.get("cipher") != ENCRYPTED_CONNECTIONS_CIPHER or payload.get("kdf") != ENCRYPTED_CONNECTIONS_KDF:
        raise ValueError("Encrypted connections payload uses an unsupported format.")
    salt = payload.get("salt")
    nonce = payload.get("nonce")
    encoded = payload.get("payload")
    iterations = payload.get("iterations")
    if not isinstance(salt, str) or not isinstance(nonce, str) or not isinstance(encoded, str):
        raise ValueError("Encrypted connections payload is missing required fields.")
    if not isinstance(iterations, int) or iterations < 100_000:
        raise ValueError("Encrypted connections payload uses invalid KDF settings.")
    try:
        key = derive_connections_key(master_password, salt_bytes, iterations)
        raw = AESGCM(key).decrypt(nonce_bytes, ciphertext, None)
        check_size(raw, MAX_DECODED_BYTES)
        decoded = json.loads(raw.decode("utf-8"))
    except StorageLimitError:
        raise
    except InvalidTag as exc:
        raise InvalidMasterPasswordError("Could not decrypt connections with this master password.") from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not decode encrypted connections: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ValueError("Decoded encrypted connections payload is not an object.")
    return decoded


def connection_storage_mode_from_payload(payload: dict[str, object]) -> str:
    if payload.get("format") == ENCRYPTED_CONNECTIONS_FORMAT:
        return CONNECTION_STORAGE_ENCRYPTED
    if payload.get("format") == OBFUSCATED_CONNECTIONS_FORMAT:
        return CONNECTION_STORAGE_OBFUSCATED
    return CONNECTION_STORAGE_PLAIN


def read_raw_connections_payload(path: Path) -> dict[str, object]:
    payload = read_storage_json(path)
    if not isinstance(payload, dict):
        raise ValueError("Connections file must contain a JSON object.")
    return payload


def read_connections_payload(path: Path, master_password: str | None = None) -> dict[str, object]:
    return decoded_connections_payload(read_raw_connections_payload(path), master_password)


def write_connections_file(
    path: Path,
    groups: list[Group],
    servers: list[Server],
    local_terminals: list[LocalTerminalProfile],
    storage_mode: str,
    master_password: str | None = None,
    workspaces: list[Workspace] | None = None,
    snippets: list[CommandSnippet] | None = None,
    snippet_categories: list[str] | None = None,
) -> None:
    mode = storage_mode if storage_mode in CONNECTION_STORAGE_MODES else CONNECTION_STORAGE_PLAIN
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = connections_payload(
        groups, servers, local_terminals, mode, master_password,
        workspaces, snippets, snippet_categories,
    )
    data = storage_json_bytes(payload)
    path.write_bytes(data)
    path.chmod(0o600)


def export_connections_file(source: Path, destination: Path) -> None:
    destination.write_bytes(read_storage_bytes(source))
    destination.chmod(0o600)


def load_store_data_from_json(path: Path, current: StoreData, master_password: str | None = None) -> StoreData:
    payload, _ = migrate_connections_payload(read_connections_payload(path, master_password))
    groups = [Group(**item) for item in payload.get("groups", [])]
    servers = [Server(**item) for item in payload.get("servers", [])]
    snippets = snippets_from_payload(payload.get("snippets", []), groups, servers)
    return StoreData(
        groups=groups,
        servers=servers,
        local_terminals=[LocalTerminalProfile(**item) for item in payload.get("local_terminals", [])],
        workspaces=workspaces_from_payload(payload.get("workspaces", [])),
        snippets=snippets,
        snippet_categories=normalized_categories(payload.get("snippet_categories"), snippets),
        notes=current.notes,
        note_categories=current.note_categories,
        terminal=current.terminal,
        app=current.app,
        statistics=current.statistics,
    )


def snippets_from_payload(
    payload: object,
    groups: list[Group] | None = None,
    servers: list[Server] | None = None,
) -> list[CommandSnippet]:
    if not isinstance(payload, list):
        return []
    snippets: list[CommandSnippet] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        values = (item.get("id"), item.get("name"), item.get("content"))
        if not all(isinstance(value, str) and value for value in values):
            continue
        try:
            snippet = normalize_snippet(
                item["id"], item["name"], item["content"],
                item.get("category", "") if isinstance(item.get("category", ""), str) else "",
                item.get("scope", "global") if isinstance(item.get("scope", "global"), str) else "global",
                item.get("target_id", "") if isinstance(item.get("target_id", ""), str) else "",
                allow_legacy_name=True,
            )
            if (groups is not None and servers is not None
                    and not snippet_target_exists(snippet, groups, servers)):
                continue
            snippets.append(snippet)
        except SnippetError:
            continue
    return snippets


def workspaces_from_payload(payload: object) -> list[Workspace]:
    if not isinstance(payload, list):
        return []
    workspaces: list[Workspace] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        workspace_id = item.get("id")
        name = item.get("name")
        tabs = item.get("tabs", [])
        if (
            not isinstance(workspace_id, str)
            or not workspace_id
            or not isinstance(name, str)
            or not name.strip()
            or not isinstance(tabs, list)
        ):
            continue
        workspaces.append(
            Workspace(
                id=workspace_id,
                name=name,
                tabs=normalized_workspace_tabs(tabs),
            )
        )
    return workspaces
