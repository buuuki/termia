# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone host-side APT helper. Executed by isolated system Python via pkexec."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_PACKAGE = 100 * 1024 * 1024
MAX_PACKAGES = 128


def apt_operations(targets: list[str], run) -> int:
    refreshed = run(["/usr/bin/apt-get", "-o", "APT::Update::Error-Mode=any", "update"],
                    check=False)
    if refreshed.returncode:
        return refreshed.returncode
    installed = run(["/usr/bin/apt-get", "--yes", "--no-remove", "-o",
                     "DPkg::Lock::Timeout=15", "install", *targets], check=False)
    return installed.returncode


def stage_package(source: Path, target: Path, digest: str, size: int) -> None:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(source, flags)
    with os.fdopen(descriptor, "rb") as incoming:
        info = os.fstat(incoming.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != size:
            raise ValueError("invalid-package-file")
        actual = hashlib.sha256()
        copied = 0
        with target.open("xb") as outgoing:
            while chunk := incoming.read(1024 * 1024):
                copied += len(chunk)
                if copied > size:
                    raise ValueError("package-size-changed")
                actual.update(chunk)
                outgoing.write(chunk)
        if copied != size or actual.hexdigest() != digest:
            raise ValueError("package-verification-failed")
    target.chmod(0o644)


def transaction(arguments: list[str], run=None) -> int:
    run = run or subprocess.run
    if not arguments:
        raise ValueError("missing-mode")
    mode, *values = arguments
    if mode == "packages":
        if (not 0 < len(values) <= MAX_PACKAGES
                or any(re.fullmatch(r"[a-z0-9][a-z0-9+.-]*[a-z0-9]", name) is None
                       for name in values)):
            raise ValueError("invalid-package-names")
        return apt_operations(values, run)
    if mode != "debian" or len(values) != 3:
        raise ValueError("invalid-mode")
    digest, raw_size, filename = values
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid-digest")
    size = int(raw_size)
    if not 0 < size <= MAX_PACKAGE:
        raise ValueError("invalid-size")
    with tempfile.TemporaryDirectory(prefix="termia-apt-") as directory:
        staged = Path(directory) / "termia.deb"
        stage_package(Path(filename), staged, digest, size)
        # The helper owns the directory; _apt needs read/traverse access only.
        Path(directory).chmod(0o755)
        return apt_operations([str(staged)], run)


def main(arguments: list[str] | None = None) -> int:
    if os.geteuid() != 0:
        print("termia-apt:error=requires-root", file=sys.stderr)
        return 77
    os.umask(0o077)
    try:
        return transaction(sys.argv[1:] if arguments is None else arguments)
    except (OSError, ValueError):
        print("termia-apt:error=invalid-transaction", file=sys.stderr)
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
