# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import json
import zlib
from dataclasses import asdict
from pathlib import Path

from .models import Group, Server, StoreData

CONNECTION_STORAGE_PLAIN = "plain"
CONNECTION_STORAGE_OBFUSCATED = "obfuscated"
CONNECTION_STORAGE_MODES = {CONNECTION_STORAGE_PLAIN, CONNECTION_STORAGE_OBFUSCATED}
OBFUSCATED_CONNECTIONS_FORMAT = "termia-connections-obfuscated-v1"


def connections_payload(groups: list[Group], servers: list[Server], storage_mode: str) -> dict[str, object]:
    payload = {
        "groups": [asdict(group) for group in groups],
        "servers": [asdict(server) for server in servers],
    }
    if storage_mode == CONNECTION_STORAGE_OBFUSCATED:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        encoded = base64.b64encode(zlib.compress(raw)).decode("ascii")
        return {
            "format": OBFUSCATED_CONNECTIONS_FORMAT,
            "encoding": "zlib+base64",
            "payload": encoded,
        }
    return payload


def decoded_connections_payload(payload: dict[str, object]) -> dict[str, object]:
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


def connection_storage_mode_from_payload(payload: dict[str, object]) -> str:
    if payload.get("format") == OBFUSCATED_CONNECTIONS_FORMAT:
        return CONNECTION_STORAGE_OBFUSCATED
    return CONNECTION_STORAGE_PLAIN


def read_raw_connections_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Connections file must contain a JSON object.")
    return payload


def read_connections_payload(path: Path) -> dict[str, object]:
    return decoded_connections_payload(read_raw_connections_payload(path))


def write_connections_file(path: Path, groups: list[Group], servers: list[Server], storage_mode: str) -> None:
    mode = storage_mode if storage_mode in CONNECTION_STORAGE_MODES else CONNECTION_STORAGE_PLAIN
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = connections_payload(groups, servers, mode)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    path.chmod(0o600)


def export_connections_file(source: Path, destination: Path) -> None:
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    destination.chmod(0o600)


def load_store_data_from_json(path: Path, current: StoreData) -> StoreData:
    payload = read_connections_payload(path)
    return StoreData(
        groups=[Group(**item) for item in payload.get("groups", [])],
        servers=[Server(**item) for item in payload.get("servers", [])],
        terminal=current.terminal,
        app=current.app,
        statistics=current.statistics,
    )
