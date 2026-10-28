# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Installation adapters. Commands use argument vectors, never a shell."""
from __future__ import annotations

import codecs
import fcntl
import hashlib
import os
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol

from .update_dependencies import (
    DependencyPlan,
    dependency_plan,
    install_dependencies,
    parse_requirements,
    source_requirements,
)
from .update_output import OutputLines
from .update_service import (
    REPOSITORY,
    Release,
    ReleaseClient,
    UpdateError,
    check_cancel,
)


def command(args: list[str], cancel: Event, *, cwd: Path | None = None,
            applying: bool = False, output: Callable[[str], None] | None = None) -> str:
    check_cancel(cancel)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    # Do not inherit Git overrides from a terminal that launched Termia.
    env = {key: value for key, value in env.items() if not key.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT if output is not None else subprocess.DEVNULL,
                                   text=True, start_new_session=True)
    except OSError:
        raise UpdateError("update_install_failed") from None
    deadline = time.monotonic() + 90
    if output is not None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        lines = OutputLines(output)
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            while ready.get_map():
                for key, _events in ready.select(timeout=0.2):
                    chunk = os.read(key.fd, 4096)
                    if chunk:
                        lines.feed(decoder.decode(chunk))
                    else:
                        ready.unregister(key.fileobj)
                if not applying and (cancel.is_set() or time.monotonic() >= deadline):
                    break
        lines.feed(decoder.decode(b"", final=True))
        lines.finish()
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

    def set_output(self, output: Callable[[str], None]) -> None: ...

    def availability(self, current: str, cancel: Event) -> str: ...
    def prepare(self, release: Release, directory: Path, cancel: Event) -> object: ...
    def dependencies(self, prepared: object, cancel: Event) -> DependencyPlan: ...
    def install_dependencies(self, plan: DependencyPlan) -> None: ...
    def apply(self, prepared: object, release: Release) -> None: ...


class GitInstaller:
    kind = "update_source"

    def __init__(self, root: Path, current: str, run=command):
        self.root, self.current, self.run = root, current, run
        self.original_head = ""
        self.output = None

    def set_output(self, output: Callable[[str], None]) -> None:
        self.output = output

    def git(self, *args: str, cancel: Event | None = None, applying=False) -> str:
        options = {"output": self.output} if self.output is not None and (applying or args[0] == "fetch") else {}
        return self.run(["/usr/bin/git", "-c", "core.hooksPath=/dev/null",
                         "-c", "merge.autoStash=false",
                         "-c", "protocol.file.allow=never", *args],
                        cancel or Event(), cwd=self.root, applying=applying, **options)

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

    def recovery_available(self, release: Release, cancel: Event) -> bool:
        """Recognize the selected release already present in a clean checkout."""
        if self.current.endswith("-dev"):
            return False
        try:
            branch = self.git("rev-parse", "--abbrev-ref", "HEAD", cancel=cancel)
            if branch not in ("main", "HEAD"):
                return False
            if self.git("status", "--porcelain", "--untracked-files=all", cancel=cancel):
                return False
            head = self.git("rev-parse", "HEAD", cancel=cancel)
            target = self.git("rev-parse", f"refs/tags/{release.tag}^{{commit}}", cancel=cancel)
            return head == target
        except UpdateError:
            check_cancel(cancel)
            return False

    def prepare_recovery(self, release: Release, cancel: Event) -> str:
        if not self.recovery_available(release, cancel):
            raise UpdateError("update_checkout_blocked")
        self.current = release.label
        if self.availability(self.current, cancel):
            raise UpdateError("update_checkout_blocked")
        self.original_head = self.git("rev-parse", "HEAD", cancel=cancel)
        return self.original_head

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

    def dependencies(self, prepared: object, cancel: Event) -> DependencyPlan:
        if (self.availability(self.current, cancel)
                or self.git("rev-parse", "HEAD", cancel=cancel) != self.original_head):
            raise UpdateError("update_checkout_blocked")
        required = source_requirements(self.git("show", f"{prepared}:debian/control", cancel=cancel))
        previous = source_requirements(self.git("show", f"{self.original_head}:debian/control", cancel=cancel))
        return dependency_plan(required, previous, self.run, cancel)

    def install_dependencies(self, plan: DependencyPlan) -> None:
        def run(args, cancel, **options):
            if self.output is not None:
                options["output"] = self.output
            return self.run(args, cancel, **options)

        install_dependencies(plan, run)

    def apply(self, prepared: object, release: Release) -> None:
        if (self.availability(self.current, Event())
                or self.git("rev-parse", "HEAD") != self.original_head):
            raise UpdateError("update_checkout_blocked")
        self.git("merge", "--ff-only", "--no-edit", "--no-overwrite-ignore", str(prepared), applying=True)


class DebianInstaller:
    kind = "update_debian"

    def __init__(self, client: ReleaseClient, run=command):
        self.client, self.run = client, run
        self.target_version = ""
        self.output = None

    def set_output(self, output: Callable[[str], None]) -> None:
        self.output = output

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
        self.target_version = values[1]
        # APT's sandbox user must be able to traverse and read the verified package.
        directory.chmod(0o755)
        path.chmod(0o644)
        return path

    def dependencies(self, prepared: object, cancel: Event) -> DependencyPlan:
        path = Path(str(prepared))
        fields = ("Pre-Depends", "Depends")
        required = [self.run(["/usr/bin/dpkg-deb", "--field", str(path), field], cancel)
                    for field in fields]
        previous = [self.run(["/usr/bin/dpkg-query", "-W", f"-f=${{{field}}}", "termia"], cancel)
                    for field in fields]
        return dependency_plan(parse_requirements(", ".join(v for v in required if v)),
                               parse_requirements(", ".join(v for v in previous if v)),
                               self.run, cancel)

    def install_dependencies(self, plan: DependencyPlan) -> None:
        # The verified .deb and its requirements are installed in one APT transaction.
        return None

    def verify_installed(self) -> None:
        output = self.run(["/usr/bin/dpkg-query", "-W", "-f=${db:Status-Status}\t${Version}",
                           "termia"], Event())
        if output != "installed\t" + self.target_version or not self.target_version:
            raise UpdateError("update_verification_failed_after_apply")

    def verify(self, prepared: object, release: Release) -> None:
        path = Path(str(prepared))
        if (not path.is_file() or path.is_symlink() or release.asset is None
                or hashlib.sha256(path.read_bytes()).hexdigest() != release.asset.sha256):
            raise UpdateError("update_untrusted")

    def apply(self, prepared: object, release: Release) -> None:
        path = Path(str(prepared))
        self.verify(prepared, release)
        options = {"output": self.output} if self.output is not None else {}
        self.run(["/usr/bin/pkexec", "--disable-internal-agent", "/usr/bin/apt-get",
                  "--yes", "--no-remove", "-o", "DPkg::Lock::Timeout=15",
                  "install", str(path)], Event(), applying=True, **options)


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
