#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run Termia directly from a source checkout."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from termia.app import main

if __name__ == "__main__":
    raise SystemExit(main())
