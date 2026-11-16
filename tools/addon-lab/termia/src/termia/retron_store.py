# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent, bounded and atomic Retron profile persistence."""
from __future__ import annotations

import json
import os
import tempfile
import unicodedata
from copy import deepcopy
from pathlib import Path

from .retron_profile import MAX_PROFILE_BYTES, empty_profile, validate_profile

MAX_PRESETS = 32
MAX_STORE_BYTES = 2 * 1024 * 1024


def preset_name(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("retron_name_invalid")
    value = unicodedata.normalize("NFC", value.strip())
    if not value or len(value) > 64 or any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("retron_name_invalid")
    return value


def validate_presets(presets: object) -> dict:
    if not isinstance(presets, dict) or len(presets) > MAX_PRESETS:
        raise ValueError("retron_preset_limit")
    result = {}
    seen = set()
    for name, profile in presets.items():
        normalized = preset_name(name)
        if normalized != name or normalized.casefold() in seen:
            raise ValueError("retron_name_duplicate")
        seen.add(normalized.casefold())
        result[name] = validate_profile(profile)
    return result


class RetronStore:
    def __init__(self, path: Path, can_write):
        self.path = path
        self.can_write = can_write
        self.load_error = False
        self.original_bytes = None
        self.presets = {}
        self.active_name = None
        self.saved_profile = empty_profile()

    def load(self, accent: str = "#55BAC9") -> dict:
        try:
            with self.path.open("rb") as source:
                raw = source.read(MAX_STORE_BYTES + 1)
            self.original_bytes = raw
            if len(raw) > MAX_STORE_BYTES:
                raise ValueError("Retron profile is too large")
            document = json.loads(raw)
            if isinstance(document, dict) and type(document.get("schema_version")) is int and document["schema_version"] == 2:
                if set(document) != {"schema_version", "current", "presets", "active_name"}:
                    raise ValueError("Invalid Retron library")
                result = validate_profile(document["current"])
                presets = validate_presets(document["presets"])
                active = document["active_name"]
                if active is not None and (not isinstance(active, str) or active not in presets or presets[active] != result):
                    raise ValueError("Invalid active Retron preset")
                self.presets = presets
                self.active_name = active
            else:
                if len(raw) > MAX_PROFILE_BYTES:
                    raise ValueError("Legacy Retron profile is too large")
                result = validate_profile(document)
        except FileNotFoundError:
            result = empty_profile(accent)
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
            # Never repair, rename or overwrite unknown/corrupt data on load.
            self.load_error = True
            result = empty_profile(accent)
        self.saved_profile = deepcopy(result)
        return result

    def save(self, profile: dict, *, presets: dict | None = None, active_name: str | None = None) -> None:
        if self.load_error or not self.can_write():
            raise PermissionError("Retron profile is not writable")
        profile = validate_profile(profile)
        presets = validate_presets(self.presets if presets is None else presets)
        if active_name is not None and (active_name not in presets or presets[active_name] != profile):
            raise ValueError("Invalid active Retron preset")
        document = {"schema_version": 2, "current": profile, "presets": presets, "active_name": active_name}
        payload = json.dumps(document, indent=2, allow_nan=False).encode() + b"\n"
        if len(payload) > MAX_STORE_BYTES:
            raise ValueError("Retron profile is too large")
        # Catch changes from outside this instance instead of discarding them.
        try:
            with self.path.open("rb") as source:
                current = source.read(MAX_STORE_BYTES + 1)
        except FileNotFoundError:
            current = None
        if current != self.original_bytes:
            raise OSError("Retron profile changed outside this instance")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=".retron-", delete=False) as target:
                temporary = Path(target.name)
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            if not self.can_write():
                raise PermissionError("Retron profile is not writable")
            os.replace(temporary, self.path)
            temporary = None
            self.original_bytes = payload
            self.saved_profile = deepcopy(profile)
            self.presets = presets
            self.active_name = active_name
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
