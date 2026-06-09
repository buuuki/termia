#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/install_dependencies.sh [--check|--help]

Without arguments, install Termia runtime dependencies for the detected Linux
package manager and verify the result.

Options:
  --check   Verify dependencies without installing anything.
  --help    Show this help message.
EOF
}

# Verify the Python introspection bindings required by the GTK application.
check_python_modules() {
  python3 - <<'PY_CHECK'
import sys

PACKAGE_HINTS = {
    "Gtk": "gir1.2-gtk-4.0",
    "Gdk": "gir1.2-gtk-4.0",
    "Pango": "gir1.2-pango-1.0",
    "Vte": "gir1.2-vte-3.91",
}


def fail(message):
    print(message, file=sys.stderr)
    print("Run ./scripts/install_dependencies.sh to install Termia dependencies.", file=sys.stderr)
    print(
        "Debian/Ubuntu/Linux Mint package hint: sudo apt install python3-gi "
        "gir1.2-gtk-4.0 gir1.2-vte-3.91 python3-yaml openssh-client sshpass",
        file=sys.stderr,
    )
    print("Termia requires GTK 4 VTE (Vte 3.91); Vte 2.91 is not enough.", file=sys.stderr)
    sys.exit(1)


try:
    import gi
except ImportError:
    fail("Missing Python GObject bindings: python3-gi / python3-gobject is not installed.")

requirements = [
    ("Gtk", "4.0"),
    ("Gdk", "4.0"),
    ("Pango", "1.0"),
    ("Vte", "3.91"),
]
for namespace, version in requirements:
    try:
        gi.require_version(namespace, version)
    except ValueError:
        fail(
            f"Missing GObject namespace {namespace} {version}. "
            f"Install package: {PACKAGE_HINTS.get(namespace, 'distribution-specific package')}."
        )

try:
    from gi.repository import Gtk, Gdk, Pango, Vte
except (ImportError, ValueError) as exc:
    fail(f"Could not load GTK/VTE bindings: {exc}")

print("Python/GTK dependencies OK")
PY_CHECK
}

check_command() {
  local command_name="$1"
  local package_hint="$2"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Missing command: ${command_name}. Install package: ${package_hint}." >&2
    return 1
  fi
}

check_terminal_font() {
  if ! command -v fc-list >/dev/null 2>&1; then
    echo "fontconfig is not available; Termia will use the runtime font fallback if JetBrains Mono is missing."
    return 0
  fi
  if fc-list : family | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -Fxq "JetBrains Mono"; then
    echo "JetBrains Mono font OK"
  else
    echo "JetBrains Mono font not found; Termia will fall back to Ubuntu Mono or Monospace."
  fi
}

run_checks() {
  check_python_modules
  check_command ssh openssh-client
  check_command sshpass sshpass
  echo "ssh and sshpass clients OK"
  check_terminal_font
}

install_optional_font_package() {
  local package_name="$1"
  shift
  if ! "$@"; then
    echo "Could not install optional font package: ${package_name}. Termia will use the runtime font fallback." >&2
  fi
}

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y \
      python3 \
      python3-gi \
      python3-yaml \
      gir1.2-gtk-4.0 \
      gir1.2-vte-3.91 \
      openssh-client \
      sshpass \
      desktop-file-utils
    install_optional_font_package fonts-jetbrains-mono sudo apt-get install -y fonts-jetbrains-mono
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y \
      python3 \
      python3-gobject \
      python3-pyyaml \
      gtk4 \
      vte291-gtk4 \
      openssh-clients \
      sshpass \
      desktop-file-utils
    install_optional_font_package jetbrains-mono-fonts sudo dnf install -y jetbrains-mono-fonts
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed \
      python \
      python-gobject \
      python-yaml \
      gtk4 \
      vte4 \
      openssh \
      sshpass \
      desktop-file-utils
    install_optional_font_package ttf-jetbrains-mono sudo pacman -S --needed ttf-jetbrains-mono
  else
    echo "Could not detect apt-get, dnf, or pacman." >&2
    echo "Install manually: Python 3, PyGObject, GTK 4, VTE GTK 4, openssh-client, sshpass, and desktop-file-utils." >&2
    exit 1
  fi
}

case "${1:-}" in
  "")
    install_packages
    run_checks
    echo "Dependencies installed successfully"
    ;;
  --check)
    run_checks
    ;;
  --help|-h)
    usage
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
esac
