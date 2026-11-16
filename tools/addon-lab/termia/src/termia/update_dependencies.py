# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Debian requirements and requests to the fixed host-side APT helper. No GTK."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from .update_service import UpdateError, check_cancel

MAX_REQUIREMENTS = 128


@dataclass(frozen=True)
class Requirement:
    package: str
    operator: str = ""
    version: str = ""

    @property
    def label(self) -> str:
        suffix = f" ({self.operator} {self.version})" if self.operator else ""
        return self.package + suffix


@dataclass(frozen=True)
class DependencyPlan:
    required: tuple[tuple[Requirement, ...], ...]
    missing: tuple[str, ...]
    packages: tuple[str, ...]
    assisted_available: bool


def parse_requirements(value: str, *, source: bool = False) -> tuple[tuple[Requirement, ...], ...]:
    """Accept bounded dependency relationships; never shell/package-manager syntax."""
    if len(value) > 65536 or not value.strip():
        raise UpdateError("update_requirements_unavailable")
    groups = []
    for group in value.split(","):
        group = group.strip()
        if source and group in ("${misc:Depends}", "${python3:Depends}"):
            continue
        alternatives = []
        for raw in group.split("|"):
            match = re.fullmatch(
                r"([a-z0-9][a-z0-9+.-]*[a-z0-9])(?::(?:any|native))?"
                r"(?:\s*\((>=|<=|=|<<|>>)\s*([0-9][A-Za-z0-9.+:~\-]*)\))?", raw.strip()
            )
            if not match:
                raise UpdateError("update_requirements_unavailable")
            package, operator, version = match.groups()
            # APT interprets a trailing '-' as removal even without a shell.
            alternatives.append(Requirement(package, operator or "", version or ""))
        groups.append(tuple(alternatives))
    if not groups or sum(map(len, groups)) > MAX_REQUIREMENTS:
        raise UpdateError("update_requirements_unavailable")
    return tuple(groups)


def source_requirements(control: str) -> tuple[tuple[Requirement, ...], ...]:
    if len(control) > 131072:
        raise UpdateError("update_requirements_unavailable")
    matches = []
    for paragraph in re.split(r"\n\s*\n", control):
        fields = {}
        key = None
        for line in paragraph.splitlines():
            if line.startswith((" ", "\t")) and key:
                fields[key] += " " + line.strip()
            elif ":" in line:
                key, value = line.split(":", 1)
                if key in fields:
                    raise UpdateError("update_requirements_unavailable")
                fields[key] = value.strip()
        if fields.get("Package") == "termia":
            value = ", ".join(fields[k] for k in ("Pre-Depends", "Depends") if fields.get(k))
            matches.append(parse_requirements(value, source=True))
    if len(matches) != 1:
        raise UpdateError("update_requirements_unavailable")
    return matches[0]


def requirement_label(group: tuple[Requirement, ...]) -> str:
    return " | ".join(item.label for item in group)


def installed(requirement: Requirement, run, cancel: Event) -> bool:
    try:
        output = run(["/usr/bin/dpkg-query", "-W", "-f=${db:Status-Status}\t${Version}",
                      requirement.package], cancel)
        status, version = output.split("\t", 1)
        if status != "installed":
            return False
        if requirement.operator:
            run(["/usr/bin/dpkg", "--compare-versions", version,
                 requirement.operator, requirement.version], cancel)
        return True
    except UpdateError:
        check_cancel(cancel)
        return False
    except ValueError:
        raise UpdateError("update_dependency_check_failed") from None


# Probe only known runtime imports in a fresh interpreter, never import target code.
PROBES = {
    "python3-gi": ("module", "gi", ""),
    "python3-cryptography": ("module", "cryptography", ""),
    "python3-paramiko": ("module", "paramiko", ""),
    "python3-yaml": ("module", "yaml", ""),
    "gir1.2-gtk-4.0": ("gi", "Gtk", "4.0"),
    "gir1.2-vte-3.91": ("gi", "Vte", "3.91"),
    "gir1.2-gtksource-5": ("gi", "GtkSource", "5"),
}
PROBE_CODE = '''import importlib, json, sys
failed = []
for package, kind, name, version in json.loads(sys.argv[1]):
    try:
        if kind == "gi":
            import gi
            gi.require_version(name, version)
            importlib.import_module("gi.repository." + name)
        else:
            importlib.import_module(name)
    except (ImportError, ValueError, OSError):
        failed.append(package)
print(json.dumps(failed))
'''


def runtime_missing(packages: tuple[str, ...], run, cancel: Event) -> tuple[str, ...]:
    probes = [(p, *PROBES[p]) for p in packages if p in PROBES]
    if not probes:
        return ()
    try:
        output = run([sys.executable, "-I", "-c", PROBE_CODE, json.dumps(probes)], cancel)
        failed = json.loads(output)
        if (not isinstance(failed, list) or any(type(p) is not str or p not in packages for p in failed)):
            raise ValueError()
        return tuple(failed)
    except (ValueError, TypeError):
        raise UpdateError("update_dependency_check_failed") from None


def dependency_plan(required, run, cancel: Event) -> DependencyPlan:
    if not all(Path(p).is_file() for p in ("/usr/bin/dpkg-query", "/usr/bin/dpkg", "/usr/bin/apt-get")):
        raise UpdateError("update_dependency_platform")
    missing = []
    packages = []
    chosen = []
    for group in required:
        check_cancel(cancel)
        available = next((item for item in group if installed(item, run, cancel)), None)
        choice = available or group[0]
        chosen.append(choice.package)
        if available is None:
            missing.append(requirement_label(group))
            packages.append(choice.package)
    for package in runtime_missing(tuple(chosen), run, cancel):
        if package not in packages:
            packages.append(package)
            missing.append(package)
    return DependencyPlan(required, tuple(missing), tuple(packages),
                          Path("/usr/bin/pkexec").is_file())


def run_apt_transaction(arguments: list[str], run, **options) -> None:
    # Snapshot code from the running installation, never from the target release.
    try:
        helper = Path(__file__).with_name("update_apt_helper.py").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise UpdateError("update_installer_missing") from None
    run(["/usr/bin/pkexec", "--disable-internal-agent", "/usr/bin/python3",
         "-I", "-c", helper, *arguments], Event(), applying=True, **options)


def install_dependencies(plan: DependencyPlan, run) -> None:
    if not plan.packages:
        return
    if not plan.assisted_available:
        raise UpdateError("update_installer_missing")
    try:
        run_apt_transaction(["packages", *plan.packages], run)
    except UpdateError:
        raise UpdateError("update_dependencies_install_failed") from None
