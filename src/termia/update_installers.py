# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Installation adapters. Commands use argument vectors, never a shell."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
from threading import Event
import time
from typing import Protocol

from .update_service import Release, ReleaseClient, UpdateError, check_cancel, REPOSITORY


def command(args: list[str], cancel: Event, *, cwd: Path | None = None,
            applying: bool = False) -> str:
    check_cancel(cancel)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    # Do not inherit Git overrides from a terminal that launched Termia.
    env = {key: value for key, value in env.items() if not key.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, start_new_session=True)
    except OSError:
        raise UpdateError("update_install_failed") from None
    deadline = time.monotonic() + 90
    while True:
        try:
            output, _ = process.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if not applying and (cancel.is_set() or time.monotonic() >= deadline):
                # The child is unreaped, so its isolated group identity cannot be reused.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                except ProcessLookupError:
                    process.communicate()
                check_cancel(cancel)
                raise UpdateError("update_install_failed")
    if process.returncode:
        raise UpdateError("update_install_failed")
    return output.strip()


@contextmanager
def update_lock():
    """Serialize updater jobs across isolated configuration profiles."""
    path = Path(tempfile.gettempdir()) / f"termia-update-{os.getuid()}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
            raise UpdateError("update_busy")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UpdateError("update_busy") from None
        yield
    finally:
        os.close(fd)  # Do not unlink: another process may already hold this inode.


class Installer(Protocol):
    kind: str

    def availability(self, current: str, cancel: Event) -> str: ...
    def prepare(self, release: Release, directory: Path, cancel: Event) -> object: ...
    def apply(self, prepared: object, release: Release) -> None: ...


class GitInstaller:
    kind = "update_source"

    def __init__(self, root: Path, current: str, run=command):
        self.root, self.current, self.run = root, current, run
        self.original_head = ""

    def git(self, *args: str, cancel: Event | None = None, applying=False) -> str:
        return self.run(["/usr/bin/git", "-c", "core.hooksPath=/dev/null",
                         "-c", "merge.autoStash=false",
                         "-c", "protocol.file.allow=never", *args],
                        cancel or Event(), cwd=self.root, applying=applying)

    def availability(self, current: str, cancel: Event) -> str:
        if current.endswith("-dev"):
            return "update_checkout_blocked"
        try:
            branch = self.git("rev-parse", "--abbrev-ref", "HEAD", cancel=cancel)
            if branch not in ("main", "HEAD"):
                return "update_checkout_blocked"
            if self.git("status", "--porcelain", "--untracked-files=all", cancel=cancel):
                return "update_checkout_blocked"
            head = self.git("rev-parse", "HEAD", cancel=cancel)
            tag = self.git("rev-parse", f"refs/tags/v{current}^{{commit}}", cancel=cancel)
            if head != tag:
                return "update_checkout_blocked"
            return ""
        except UpdateError:
            check_cancel(cancel)
            return "update_checkout_blocked"

    def prepare(self, release: Release, directory: Path, cancel: Event) -> str:
        if self.availability(self.current, cancel):
            raise UpdateError("update_checkout_blocked")
        self.original_head = self.git("rev-parse", "HEAD", cancel=cancel)
        # Fetch the chosen release from the fixed official URL, never configured remotes.
        self.git("fetch", "--no-tags", "--no-recurse-submodules", REPOSITORY + ".git",
                 f"refs/tags/{release.tag}:refs/tags/{release.tag}", cancel=cancel)
        target = self.git("rev-parse", "FETCH_HEAD^{commit}", cancel=cancel)
        self.git("merge-base", "--is-ancestor", self.original_head, target, cancel=cancel)
        return target

    def apply(self, prepared: object, release: Release) -> None:
        if (self.availability(self.current, Event())
                or self.git("rev-parse", "HEAD") != self.original_head):
            raise UpdateError("update_checkout_blocked")
        self.git("merge", "--ff-only", "--no-edit", "--no-overwrite-ignore", str(prepared), applying=True)


class DebianInstaller:
    kind = "update_debian"

    def __init__(self, client: ReleaseClient, run=command):
        self.client, self.run = client, run

    def availability(self, current: str, cancel: Event) -> str:
        if not all(Path(path).is_file() for path in ("/usr/bin/pkexec", "/usr/bin/apt-get", "/usr/bin/dpkg-deb")):
            return "update_installer_missing"
        return ""

    def prepare(self, release: Release, directory: Path, cancel: Event) -> Path:
        if release.asset is None:
            raise UpdateError("update_no_verified_asset")
        path = directory / "termia.deb"
        self.client.download(release.asset, path, cancel)
        values = [self.run(["/usr/bin/dpkg-deb", "--field", str(path), field], cancel)
                  for field in ("Package", "Version", "Architecture")]
        expected = release.label.replace("-", "~", 1)
        if (values[0] != "termia" or values[2] != "all"
                or not re.fullmatch(re.escape(expected) + r"-[1-9][0-9]*", values[1])):
            raise UpdateError("update_untrusted")
        installed = self.run(["/usr/bin/dpkg-query", "-W", "-f=${Version}", "termia"], cancel)
        self.run(["/usr/bin/dpkg", "--compare-versions", values[1], "gt", installed], cancel)
        # APT's sandbox user must be able to traverse and read the verified package.
        directory.chmod(0o755)
        path.chmod(0o644)
        return path

    def apply(self, prepared: object, release: Release) -> None:
        path = Path(str(prepared))
        # Recheck the downloaded bytes immediately before privilege escalation.
        if release.asset is None or hashlib.sha256(path.read_bytes()).hexdigest() != release.asset.sha256:
            raise UpdateError("update_untrusted")
        self.run(["/usr/bin/pkexec", "--disable-internal-agent", "/usr/bin/apt-get",
                  "--yes", "--no-remove", "-o", "DPkg::Lock::Timeout=15",
                  "install", str(path)], Event(), applying=True)


@dataclass(frozen=True)
class Installation:
    adapter: Installer | None
    reason: str


def detect_installation(current: str, client: ReleaseClient, cancel: Event,
                        module: Path | None = None, run=command) -> Installation:
    module = (module or Path(__file__)).resolve()
    root = module.parent.parent.parent
    if (root / ".git").exists() and (root / "run_termia.py").is_file():
        adapter = GitInstaller(root, current, run)
        return Installation(adapter, adapter.availability(current, cancel))
    try:
        owner = run(["/usr/bin/dpkg-query", "-S", str(module)], cancel)
        if owner != f"termia: {module}":
            return Installation(None, "update_unknown_installation")
        adapter = DebianInstaller(client, run)
        return Installation(adapter, adapter.availability(current, cancel))
    except UpdateError:
        check_cancel(cancel)
        return Installation(None, "update_unknown_installation")
