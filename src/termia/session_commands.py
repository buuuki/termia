# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from .models import Server


def build_ssh_command(server: Server, ssh_path: str, *, sshpass_path: str | None = None) -> list[str]:
    command = [ssh_path, "-p", str(server.port)]
    if server.public_key:
        command.extend(["-i", str(Path(server.public_key).expanduser())])
    command.append(f"{server.user}@{server.host}")
    if sshpass_path is not None:
        command = [sshpass_path, "-e", *command]
    return command
