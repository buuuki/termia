# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Asynchronous SSH known-host inspection."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib


def known_host_lookup_commands(
    host: str,
    port: int,
    ssh_keygen: str,
    known_hosts_files: Iterable[Path],
) -> list[list[str]]:
    lookup_host = f"[{host}]:{port}" if port != 22 else host
    return [
        [ssh_keygen, "-F", lookup_host, "-f", str(path)]
        for path in known_hosts_files
        if path.exists()
    ]


def inspect_known_host_async(
    host: str,
    port: int,
    callback: Callable[[bool], None],
    *,
    known_hosts_files: Iterable[Path] | None = None,
) -> None:
    """Report whether *host* is known without blocking the GTK main loop."""
    ssh_keygen = GLib.find_program_in_path("ssh-keygen")
    if ssh_keygen is None:
        GLib.idle_add(callback, False)
        return

    paths = known_hosts_files
    if paths is None:
        paths = (Path.home() / ".ssh" / "known_hosts", Path.home() / ".ssh" / "known_hosts2")
    commands = iter(known_host_lookup_commands(host, port, ssh_keygen, paths))

    def run_next() -> None:
        try:
            command = next(commands)
        except StopIteration:
            callback(False)
            return
        try:
            launcher = Gio.SubprocessLauncher.new(
                Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE
            )
            process = launcher.spawnv(command)
        except GLib.Error:
            run_next()
            return

        def on_finished(current: Gio.Subprocess, result: Gio.AsyncResult) -> None:
            try:
                current.wait_finish(result)
            except GLib.Error:
                run_next()
                return
            if current.get_successful():
                callback(True)
                return
            run_next()

        process.wait_async(None, on_finished)

    run_next()
