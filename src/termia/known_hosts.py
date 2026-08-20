# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Asynchronous SSH known-host inspection."""

from __future__ import annotations

import base64
import binascii
import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib


@dataclass(frozen=True)
class ScannedHostKey:
    host: str
    key_type: str
    key_data: str
    fingerprint: str

    @property
    def known_hosts_line(self) -> str:
        return f"{self.host} {self.key_type} {self.key_data}"


def known_host_name(host: str, port: int) -> str:
    return host if port == 22 else f"[{host}]:{port}"


def parse_scanned_host_keys(output: str, host: str, port: int) -> list[ScannedHostKey]:
    scanned_keys: list[ScannedHostKey] = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[0].startswith("#"):
            continue
        try:
            key_blob = base64.b64decode(fields[2], validate=True)
        except (binascii.Error, ValueError):
            continue
        fingerprint = base64.b64encode(hashlib.sha256(key_blob).digest()).decode().rstrip("=")
        scanned_keys.append(ScannedHostKey(known_host_name(host, port), fields[1], fields[2], f"SHA256:{fingerprint}"))
    return scanned_keys


def parse_scanned_host_key(output: str, host: str, port: int) -> ScannedHostKey | None:
    return next(iter(parse_scanned_host_keys(output, host, port)), None)


def default_known_hosts_files() -> tuple[Path, Path]:
    return (Path.home() / ".ssh" / "known_hosts", Path.home() / ".ssh" / "known_hosts2")


def known_hosts_write_path(known_hosts_files: Iterable[Path] | None = None) -> Path:
    paths = tuple(known_hosts_files or default_known_hosts_files())
    return next((path for path in paths if path.exists()), paths[0])


def append_scanned_host_key(
    scanned_key: ScannedHostKey,
    *,
    known_hosts_files: Iterable[Path] | None = None,
) -> bool:
    return append_scanned_host_keys([scanned_key], known_hosts_files=known_hosts_files)


def append_scanned_host_keys(
    scanned_keys: Iterable[ScannedHostKey],
    *,
    known_hosts_files: Iterable[Path] | None = None,
) -> bool:
    keys = tuple(scanned_keys)
    if not keys:
        return False
    path = known_hosts_write_path(known_hosts_files)
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        is_new = not path.exists()
        with path.open("a", encoding="utf-8") as known_hosts:
            for scanned_key in keys:
                known_hosts.write(scanned_key.known_hosts_line + "\n")
        if is_new:
            path.chmod(0o600)
    except OSError:
        return False
    return True


def scan_host_key_async(host: str, port: int, callback: Callable[[list[ScannedHostKey]], None]) -> None:
    ssh_keyscan = GLib.find_program_in_path("ssh-keyscan")
    if ssh_keyscan is None:
        GLib.idle_add(callback, [])
        return
    command = [ssh_keyscan, "-T", "5", "-p", str(port), host]
    try:
        launcher = Gio.SubprocessLauncher.new(
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
        )
        process = launcher.spawnv(command)
    except GLib.Error:
        GLib.idle_add(callback, [])
        return

    def on_finished(current: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            _ok, stdout, _stderr = current.communicate_utf8_finish(result)
        except GLib.Error:
            callback([])
            return
        callback(parse_scanned_host_keys(stdout or "", host, port) if current.get_successful() else [])

    process.communicate_utf8_async(None, None, on_finished)


def known_host_lookup_commands(
    host: str,
    port: int,
    ssh_keygen: str,
    known_hosts_files: Iterable[Path],
) -> list[list[str]]:
    lookup_hosts = [host] if port == 22 else [f"[{host}]:{port}", host]
    return [
        [ssh_keygen, "-F", lookup_host, "-f", str(path)]
        for path in known_hosts_files
        if path.exists()
        for lookup_host in lookup_hosts
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

    paths = known_hosts_files if known_hosts_files is not None else default_known_hosts_files()
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
