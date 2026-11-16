# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import shlex
from pathlib import Path

from .models import Server


def build_ssh_command(
    server: Server,
    ssh_path: str,
    *,
    sshpass_path: str | None = None,
    include_startup_command: bool = True,
) -> list[str]:
    command = [ssh_path, "-p", str(server.port)]
    if server.public_key:
        command.extend(["-i", str(Path(server.public_key).expanduser())])
    startup_command = server.command_on_start.strip() if include_startup_command else ""
    if startup_command:
        command.append("-t")
    command.append(f"{server.user}@{server.host}")
    if startup_command:
        command.append(build_ssh_startup_command(startup_command))
    if sshpass_path is not None:
        command = [sshpass_path, "-e", *command]
    return command


def build_ssh_startup_command(command: str) -> str:
    """Run a saved command in the remote login shell, then keep a shell open."""
    startup_script = f'{command.strip()}\nexec "$SHELL" -i'
    login_shell_command = (
        'remote_shell="${SHELL:-/bin/sh}"; '
        'export SHELL="$remote_shell"; '
        f'exec "$remote_shell" -l -i -c {shlex.quote(startup_script)}'
    )
    return f"sh -c {shlex.quote(login_shell_command)}"
