#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import ast
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PO_DIR = ROOT / "po"
LOCALE_DIR = ROOT / "src" / "termia" / "locale"
DOMAIN = "termia"
LANGUAGES = ("es", "ca")


def parse_po(path: Path) -> dict[str, str]:
    catalog: dict[str, str] = {}
    current: str | None = None
    msgid = ""
    msgstr = ""

    def unquote(value: str) -> str:
        return ast.literal_eval(value.strip())

    def flush() -> None:
        nonlocal msgid, msgstr
        if msgid or msgstr:
            catalog[msgid] = msgstr
        msgid = ""
        msgstr = ""

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if not line:
                flush()
                current = None
            continue
        if line.startswith("msgid "):
            flush()
            current = "msgid"
            msgid = unquote(line[6:])
        elif line.startswith("msgstr "):
            current = "msgstr"
            msgstr = unquote(line[7:])
        elif line.startswith('"'):
            if current == "msgid":
                msgid += unquote(line)
            elif current == "msgstr":
                msgstr += unquote(line)
    flush()
    return catalog


def compile_mo(catalog: dict[str, str]) -> bytes:
    messages = sorted(catalog.items())
    ids = b""
    strings = b""
    offsets: list[tuple[int, int, int, int]] = []

    for msgid, msgstr in messages:
        msgid_bytes = msgid.encode("utf-8")
        msgstr_bytes = msgstr.encode("utf-8")
        offsets.append((len(ids), len(msgid_bytes), len(strings), len(msgstr_bytes)))
        ids += msgid_bytes + b"\0"
        strings += msgstr_bytes + b"\0"

    count = len(messages)
    key_table_offset = 7 * 4
    value_table_offset = key_table_offset + count * 8
    id_offset = value_table_offset + count * 8
    string_offset = id_offset + len(ids)

    output = [
        struct.pack("Iiiiiii", 0x950412DE, 0, count, key_table_offset, value_table_offset, 0, 0)
    ]
    output.extend(
        struct.pack("ii", length, id_offset + offset)
        for offset, length, _string_offset, _string_length in offsets
    )
    output.extend(
        struct.pack("ii", length, string_offset + offset)
        for _id_offset, _id_length, offset, length in offsets
    )
    output.append(ids)
    output.append(strings)
    return b"".join(output)


def main() -> None:
    for language in LANGUAGES:
        po_path = PO_DIR / f"{language}.po"
        mo_path = LOCALE_DIR / language / "LC_MESSAGES" / f"{DOMAIN}.mo"
        mo_path.parent.mkdir(parents=True, exist_ok=True)
        mo_path.write_bytes(compile_mo(parse_po(po_path)))
        print(f"compiled {po_path.relative_to(ROOT)} -> {mo_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
