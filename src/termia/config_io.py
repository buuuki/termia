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

from .models import Group, LocalTerminalProfile, Server, StoreData

CONNECTION_STORAGE_PLAIN = "plain"
CONNECTION_STORAGE_OBFUSCATED = "obfuscated"
CONNECTION_STORAGE_ENCRYPTED = "encrypted"
CONNECTION_STORAGE_MODES = {CONNECTION_STORAGE_PLAIN, CONNECTION_STORAGE_OBFUSCATED, CONNECTION_STORAGE_ENCRYPTED}
OBFUSCATED_CONNECTIONS_FORMAT = "termia-connections-obfuscated-v1"
ENCRYPTED_CONNECTIONS_FORMAT = "termia-connections-encrypted-v1"
ENCRYPTED_CONNECTIONS_KDF = "pbkdf2-sha256"
ENCRYPTED_CONNECTIONS_CIPHER = "aes-256-gcm"
ENCRYPTED_CONNECTIONS_ITERATIONS = 390_000


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
) -> dict[str, object]:
    payload = {
        "groups": [asdict(group) for group in groups],
        "servers": [asdict(server) for server in servers],
        "local_terminals": [asdict(profile) for profile in local_terminals],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
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
        return payload
    encoded = payload.get("payload")
    if not isinstance(encoded, str):
        raise ValueError("Obfuscated connections payload is missing or invalid.")
    try:
        raw = zlib.decompress(base64.b64decode(encoded.encode("ascii")))
        decoded = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not decode obfuscated connections: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ValueError("Decoded obfuscated connections payload is not an object.")
    return decoded


def decrypted_connections_payload(payload: dict[str, object], master_password: str | None) -> dict[str, object]:
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
        salt_bytes = base64.b64decode(salt.encode("ascii"))
        nonce_bytes = base64.b64decode(nonce.encode("ascii"))
        ciphertext = base64.b64decode(encoded.encode("ascii"))
        key = derive_connections_key(master_password, salt_bytes, iterations)
        raw = AESGCM(key).decrypt(nonce_bytes, ciphertext, None)
        decoded = json.loads(raw.decode("utf-8"))
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
    payload = json.loads(path.read_text(encoding="utf-8"))
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
) -> None:
    mode = storage_mode if storage_mode in CONNECTION_STORAGE_MODES else CONNECTION_STORAGE_PLAIN
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = connections_payload(groups, servers, local_terminals, mode, master_password)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    path.chmod(0o600)


def export_connections_file(source: Path, destination: Path) -> None:
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    destination.chmod(0o600)


def load_store_data_from_json(path: Path, current: StoreData, master_password: str | None = None) -> StoreData:
    payload = read_connections_payload(path, master_password)
    return StoreData(
        groups=[Group(**item) for item in payload.get("groups", [])],
        servers=[Server(**item) for item in payload.get("servers", [])],
        local_terminals=[LocalTerminalProfile(**item) for item in payload.get("local_terminals", [])],
        terminal=current.terminal,
        app=current.app,
        statistics=current.statistics,
    )
