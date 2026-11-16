# SPDX-License-Identifier: GPL-3.0-or-later
from functools import cache
import json
from pathlib import Path


@cache
def catalog(language):
    if language not in {"en", "es", "ca"}:
        language = "en"
    path = Path(__file__).resolve().parent / "locales" / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def translator(language):
    english = catalog("en")
    translated = catalog(language)
    return lambda key: translated.get(key, english.get(key, key))
