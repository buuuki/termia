#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

APP_ID="local.termia"
APP_NAME="Termia"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_SCRIPT="${PROJECT_DIR}/run_termia.py"
APP_ICON_SOURCE="${PROJECT_DIR}/src/termia/assets/termia.svg"
DATA_HOME="${XDG_DATA_HOME:-"${HOME}/.local/share"}"
DESKTOP_DIR="${DATA_HOME}/applications"
ICON_DIR="${DATA_HOME}/icons/hicolor/scalable/apps"
DESKTOP_FILE="${DESKTOP_DIR}/${APP_ID}.desktop"
ICON_FILE="${ICON_DIR}/${APP_ID}.svg"

usage() {
  cat <<'EOF'
Usage: ./scripts/termia-setup.sh <install|uninstall>

Commands:
  install    Install missing runtime dependencies, verify them, and add the
             user-local Termia launcher.
  uninstall  Remove only the user-local launcher and icon. Settings,
             connections, statistics, and system packages are preserved.
EOF
}

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
    print("Run ./scripts/termia-setup.sh install to install Termia dependencies.", file=sys.stderr)
    print(
        "Debian/Ubuntu/Linux Mint package hint: sudo apt install python3-gi "
        "gir1.2-gtk-4.0 gir1.2-vte-3.91 python3-yaml python3-cryptography "
        "openssh-client sshpass",
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

try:
    import cryptography
except ImportError:
    fail("Missing Python cryptography package: python3-cryptography is not installed.")

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

confirm_apt_cache_use() {
  local answer
  if [[ ! -t 0 ]]; then
    echo "apt-get update failed and this session cannot ask whether to use the existing APT cache." >&2
    return 1
  fi

  read -r -p "Continue using the existing APT cache to install dependencies? [y/N] " answer
  case "${answer}" in
    y|Y|yes|YES|Yes) return 0 ;;
    *)
      echo "Installation cancelled because the APT package index could not be updated."
      return 1
      ;;
  esac
}

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    if ! sudo apt-get update; then
      echo "Warning: apt-get update failed. This can happen when a configured repository times out." >&2
      confirm_apt_cache_use
    fi
    sudo apt-get install -y \
      python3 \
      python3-gi \
      python3-yaml \
      python3-cryptography \
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
      python3-cryptography \
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
      python-cryptography \
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

ensure_dependencies() {
  if run_checks; then
    echo "Termia runtime dependencies are already available."
    return 0
  fi

  echo "Some Termia runtime dependencies are missing. Installing the required packages."
  install_packages
  run_checks
}

install_desktop_launcher() {
  if [[ ! -f "${APP_SCRIPT}" || ! -f "${APP_ICON_SOURCE}" ]]; then
    echo "Could not find the Termia launcher or icon in ${PROJECT_DIR}." >&2
    return 1
  fi

  mkdir -p "${DESKTOP_DIR}" "${ICON_DIR}"
  cp "${APP_ICON_SOURCE}" "${ICON_FILE}"
  chmod 0644 "${ICON_FILE}"
  printf '%s\n' \
    '[Desktop Entry]' \
    'Type=Application' \
    'Version=1.0' \
    "Name=${APP_NAME}" \
    'Comment=SSH connection manager with embedded terminals' \
    "Exec=python3 \"${APP_SCRIPT}\"" \
    "Path=${PROJECT_DIR}" \
    "Icon=${APP_ID}" \
    'Terminal=false' \
    'Categories=Network;RemoteAccess;GTK;' \
    'StartupNotify=true' \
    "StartupWMClass=${APP_ID}" > "${DESKTOP_FILE}"
  chmod 0644 "${DESKTOP_FILE}"
  refresh_desktop_caches
  echo "Installed launcher: ${DESKTOP_FILE}"
}

refresh_desktop_caches() {
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${DATA_HOME}/icons/hicolor" >/dev/null 2>&1 || true
  fi
}

confirm_install() {
  local answer
  cat <<'EOF'
Termia setup will:
  - install missing runtime packages with the detected system package manager;
  - request sudo privileges when package installation requires them;
  - verify Python, GTK 4, VTE, ssh, and sshpass;
  - install a user-local application launcher and icon.

No settings, connections, statistics, or existing system packages are removed.
Type "no" or press Ctrl-C to cancel. Press Enter to start now, or wait 10 seconds.
EOF
  if [[ ! -t 0 ]]; then
    echo "Starting non-interactive installation."
    return 0
  fi
  if read -r -t 10 -p "> " answer; then
    case "${answer}" in
      no|NO|No|n|N)
        echo "Installation cancelled."
        return 1
        ;;
    esac
  else
    echo
  fi
}

install() {
  confirm_install
  ensure_dependencies
  install_desktop_launcher
  echo "Termia installation completed successfully."
}

uninstall() {
  rm -f "${DESKTOP_FILE}" "${ICON_FILE}"
  refresh_desktop_caches
  echo "Removed launcher: ${DESKTOP_FILE}"
}

case "${1:-}" in
  install)
    install
    ;;
  uninstall)
    uninstall
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
