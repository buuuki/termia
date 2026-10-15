#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run local unittest modules with private TCP Xvfb and D-Bus services.

Some restricted sandboxes deny AF_UNIX socket creation. The usual xvfb-run and
dbus-run-session wrappers cannot start there, even though loopback TCP works.
"""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time


REPO_ROOT = Path(__file__).resolve().parent.parent
DBUS_CONFIG = """<!DOCTYPE busconfig PUBLIC
  "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
  "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>tcp:host=127.0.0.1,port=0</listen>
  <auth>DBUS_COOKIE_SHA1</auth>
  <apparmor mode="disabled"/>
  <standard_session_servicedirs/>
  <policy context="default">
    <allow send_destination="*"/>
    <allow receive_sender="*"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def start_xvfb(auth_file: Path, env: dict[str, str]) -> tuple[subprocess.Popen[str], str]:
    for _ in range(10):
        display_number = 300 + secrets.randbelow(300)
        display = f"127.0.0.1:{display_number}"
        try:
            with socket.create_connection(("127.0.0.1", 6000 + display_number), timeout=0.2):
                continue
        except OSError:
            pass
        subprocess.run(
            ["xauth", "-f", str(auth_file), "source", "-"],
            check=True,
            input=f"add {display} . {secrets.token_hex(16)}\n",
            text=True,
            stdout=subprocess.DEVNULL,
            env=env,
        )
        process = subprocess.Popen(
            [
                "Xvfb", f":{display_number}", "-screen", "0", "1280x800x24",
                "-listen", "tcp", "-nolisten", "unix", "-auth", str(auth_file),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", 6000 + display_number), timeout=0.2):
                    return process, display
            except OSError:
                time.sleep(0.05)
        stop_process(process)
    raise RuntimeError("Could not start a private Xvfb TCP display")


def start_dbus(config_file: Path, env: dict[str, str]) -> tuple[subprocess.Popen[str], str]:
    process = subprocess.Popen(
        ["dbus-daemon", f"--config-file={config_file}", "--print-address=1", "--nofork"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )
    try:
        ready, _, _ = select.select([process.stdout], [], [], 5)
        if ready:
            address = process.stdout.readline().strip()
            if address.startswith("tcp:"):
                return process, address
        raise RuntimeError("Could not start a private D-Bus TCP session")
    except BaseException:
        stop_process(process)
        raise


def run_tests() -> int:
    missing = [program for program in ("Xvfb", "xauth", "dbus-daemon") if shutil.which(program) is None]
    if missing:
        raise RuntimeError(f"Missing test dependencies: {', '.join(missing)}")

    with tempfile.TemporaryDirectory(prefix="termia-sandbox-tests-") as temporary:
        root = Path(temporary)
        home = root / "home"
        runtime = root / "runtime"
        for directory in (home, runtime, root / "config", root / "data", root / "state", root / "cache"):
            directory.mkdir(mode=0o700)
        auth_file = root / "Xauthority"
        auth_file.touch(mode=0o600)
        config_file = root / "session.conf"
        config_file.write_text(DBUS_CONFIG, encoding="utf-8")

        env = os.environ.copy()
        env.update({
            "HOME": str(home),
            "XDG_RUNTIME_DIR": str(runtime),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "TERMIA_CONFIG_DIR": str(root / "config" / "termia"),
            "TERMIA_STATE_DIR": str(root / "state"),
            "XAUTHORITY": str(auth_file),
            "GDK_BACKEND": "x11",
            "GSK_RENDERER": "cairo",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "GTK_A11Y": "none",
            "NO_AT_BRIDGE": "1",
            "GSETTINGS_BACKEND": "memory",
            "PYTHONPATH": str(REPO_ROOT / "src"),
        })
        env.pop("SSH_AUTH_SOCK", None)

        xvfb = None
        dbus = None
        try:
            xvfb, env["DISPLAY"] = start_xvfb(auth_file, env)
            dbus, env["DBUS_SESSION_BUS_ADDRESS"] = start_dbus(config_file, env)
            unittest_args = sys.argv[1:] or ["discover", "-s", "tests"]
            return subprocess.call(
                [sys.executable, "-m", "unittest", *unittest_args],
                cwd=REPO_ROOT,
                env=env,
            )
        finally:
            stop_process(dbus)
            stop_process(xvfb)


def _terminate(_signum: int, _frame: object) -> None:
    raise SystemExit(143)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _terminate)
    try:
        raise SystemExit(run_tests())
    except RuntimeError as error:
        print(f"sandbox test runner: {error}", file=sys.stderr)
        raise SystemExit(1) from None
