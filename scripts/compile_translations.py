#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import ast
import argparse
import gettext
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PO_DIR = ROOT / "po"
LOCALE_DIR = ROOT / "src" / "termia" / "locale"
DOMAIN = "termia"
LANGUAGES = ("es", "ca")


def message_items() -> list[tuple[str, str]]:
    source = (ROOT / "src" / "termia" / "i18n.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignment = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "MESSAGES" for target in node.targets)
    )
    messages = ast.literal_eval(assignment)
    if not isinstance(messages, dict) or not all(isinstance(value, str) for value in messages.values()):
        raise ValueError("MESSAGES must be a dictionary of strings.")
    return list(messages.items())


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_field(name: str, value: str) -> list[str]:
    if "\n" not in value:
        return [f'{name} {quote(value)}']
    lines = [f'{name} ""']
    for part in value.splitlines(keepends=True):
        lines.append(quote(part))
    return lines


def render_catalog(items: list[tuple[str, str]], translations: dict[str, str] | None = None) -> str:
    translations = translations or {}
    lines = [
        "# Termia translation template",
        "# Copyright (C) 2026 Jordi Pons",
        "# This file is distributed under the same license as the Termia package.",
        "#",
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: termia\\n"',
        '"POT-Creation-Date: 2026-07-22 00:00+0000\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        '"Language: \\n"',
        "",
    ]
    seen: set[str] = set()
    for key, message in items:
        if message in seen:
            continue
        seen.add(message)
        keys = [item_key for item_key, item_message in items if item_message == message]
        lines.extend(f"#: src/termia/i18n.py:{item_key}" for item_key in keys)
        lines.extend(render_field("msgid", message))
        lines.extend(render_field("msgstr", translations.get(message, "")))
        lines.append("")
    return "\n".join(lines)


def extract_pot() -> None:
    (PO_DIR / "termia.pot").write_text(render_catalog(message_items()), encoding="utf-8")


def check_catalogs() -> None:
    items = message_items()
    expected = {message for _key, message in items}
    pot = parse_po(PO_DIR / "termia.pot")
    if set(pot) - {""} != expected:
        raise ValueError("po/termia.pot is out of sync with MESSAGES.")
    for language in LANGUAGES:
        po_path = PO_DIR / f"{language}.po"
        catalog = parse_po(po_path)
        if set(catalog) - {""} != expected:
            raise ValueError(f"{po_path.relative_to(ROOT)} is out of sync with MESSAGES.")
        untranslated = [message for message in expected if not catalog.get(message)]
        if untranslated:
            raise ValueError(f"{po_path.relative_to(ROOT)} has untranslated messages: {untranslated}")
        mo_path = LOCALE_DIR / language / "LC_MESSAGES" / f"{DOMAIN}.mo"
        with mo_path.open("rb") as handle:
            mo_catalog = gettext.GNUTranslations(handle)._catalog
        if set(mo_catalog) - {""} != expected:
            raise ValueError(f"{mo_path.relative_to(ROOT)} is out of sync with {po_path.relative_to(ROOT)}.")
    print(f"translation catalogs are synchronized ({len(expected)} messages)")


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


def compile_catalogs() -> None:
    for language in LANGUAGES:
        po_path = PO_DIR / f"{language}.po"
        mo_path = LOCALE_DIR / language / "LC_MESSAGES" / f"{DOMAIN}.mo"
        mo_path.parent.mkdir(parents=True, exist_ok=True)
        mo_path.write_bytes(compile_mo(parse_po(po_path)))
        print(f"compiled {po_path.relative_to(ROOT)} -> {mo_path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile and validate Termia translations.")
    parser.add_argument("--extract", action="store_true", help="regenerate po/termia.pot from MESSAGES")
    parser.add_argument("--check", action="store_true", help="validate POT, PO, and MO catalogs")
    args = parser.parse_args()
    if args.extract:
        extract_pot()
        print("extracted po/termia.pot from src/termia/i18n.py")
    if not args.extract and not args.check:
        compile_catalogs()
        return
    if args.check:
        check_catalogs()


if __name__ == "__main__":
    main()
