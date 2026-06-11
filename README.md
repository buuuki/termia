# Termia

Termia is a GTK 4 SSH connection manager with embedded VTE terminals for
Linux desktops.

Spanish documentation: [docs/README.es.md](docs/README.es.md)
Catalan documentation: [docs/README.ca.md](docs/README.ca.md)

## Features

- Create, edit, move, and delete server groups and nested subgroups.
- Store SSH hosts with a display name, host name or IP, user, port, password,
  and private key path.
- Filter servers and open multiple tabbed sessions to the same host.
- Use embedded, width-sharing tabs and move a tab to a separate window.
- Open embedded local terminal tabs.
- Track aggregate connection, command, keystroke, session-duration, and per-server usage statistics locally.
- Open a statistics dashboard with metric cards, duration summaries, and the most used servers.
- Show or hide the session status bar globally, hide it per session, and restore it from the terminal context menu.
- Configure confirmation prompts for disconnecting sessions and closing Termia.
- Optionally send the saved SSH password to a remote terminal with `Ctrl+P`, with or without `Enter`.
- Configure general options, VTE terminal font/colors, and PS1 prompt settings separately.
- Customize local prompt colors, presets, and time/date prefixes without changing remote shell startup files or commands.
- Use the interface in English, Spanish, or Catalan. The initial language follows the system locale when supported.
- Import and export Termia configuration files.
- Import basic connection and nested group data from Asbru YAML files.

## Usage notes

The `Configuration` menu is split into `General`, `Terminal`, and `Prompt`:

- `General` controls the application theme, language, confirmations, startup behavior, password shortcut behavior, and the session status bar.
- `Terminal` controls the embedded VTE terminal font, size, foreground/background colors, and color palettes.
- `Prompt` customizes local terminal PS1 color, presets, and time/date prefixes. It does not alter SSH commands or modify remote shell startup files.

Each session can show a status bar with its state, PID, elapsed time, a compact hide button, and disconnect. Enable or disable session status bars from `General`; if a session status bar is hidden, right-click inside the terminal and choose `Show session status bar` to restore it. The sidebar has its own header toggle.

## Tested environment

Termia has been tested on Ubuntu 24.04.4 LTS with Linux kernel
6.8.0-117-generic, GNOME 46.0, and Wayland.

## Project layout

```text
run_termia.py                     Source-checkout launcher
src/termia/app.py             Application composition and window setup
src/termia/                Feature modules for storage, dialogs, tabs, terminal sessions, and UI helpers
src/termia/__main__.py        Python module entry point
src/termia/assets/            Desktop and About dialog artwork
scripts/install_dependencies.sh
scripts/install_desktop.sh
scripts/uninstall_desktop.sh
docs/README.es.md             Spanish documentation
docs/README.ca.md             Catalan documentation
SECURITY.md                    Credential storage warning
THIRD_PARTY_NOTICES.md         Runtime dependency licenses
LICENSE                       GPL-3.0-or-later license
```

The GTK implementation is split into focused modules for application composition,
storage, import, dialogs, preferences, sidebar, tabs, terminal sessions, and UI
helpers without changing the launch command.

## Download

Clone the complete repository instead of downloading individual files:

```bash
git clone https://github.com/buuuki/termia.git
cd termia
```

## Install dependencies

Termia uses system GTK and VTE packages. Check an existing installation first:

```bash
chmod +x scripts/install_dependencies.sh
./scripts/install_dependencies.sh --check
```

If the check reports missing dependencies, install them with:

```bash
./scripts/install_dependencies.sh
```

The installer verifies the result after installing. You can also run the check again
at any time:

```bash
./scripts/install_dependencies.sh --check
```

The dependency installer supports Debian, Ubuntu, Linux Mint, Fedora, and Arch Linux
package managers. It also tries to install JetBrains Mono for the default terminal
font; if unavailable, Termia falls back to Ubuntu Mono or Monospace at runtime.
Other Linux distributions require equivalent packages.

If the check reports a missing `Vte 3.91` namespace, the GTK 4 VTE introspection
package is missing. On Debian, Ubuntu, or Linux Mint the package is
`gir1.2-vte-3.91`.

## Run from a clone

```bash
python3 run_termia.py
```

## Install the desktop launcher

```bash
./scripts/install_desktop.sh
```

This installs a user-local launcher at
`~/.local/share/applications/local.termia.desktop` and its icon under
`~/.local/share/icons/hicolor/scalable/apps/`.

Run the installer again after moving the cloned directory because the desktop
entry stores an absolute path to the source-checkout launcher.

Remove the launcher without deleting settings or connections:

```bash
./scripts/uninstall_desktop.sh
```

## User data and security

Termia stores connection data, settings, and statistics outside the repository:

```text
~/.config/termia/connections.json   # groups and servers
~/.config/termia/settings.json      # app and terminal settings
~/.local/state/termia/statistics.json
```

Saved passwords are stored in `connections.json`; the file can be kept as plain text or obfuscated from Security preferences. Obfuscation is not encryption. Exported connection files can also contain passwords. Aggregate usage counters are stored separately in `statistics.json`.

Termia does not store typed text, command contents, or clipboard contents. Statistics
are flushed at most every 30 seconds while typing, when sessions end, and when Termia
closes. See [SECURITY.md](SECURITY.md).

Python may create `__pycache__/` directories next to executed modules. They only
contain generated bytecode, are excluded by `.gitignore`, and must not be
committed or distributed.

## License

Termia is licensed under the [GNU General Public License v3.0 or later](LICENSE).

Runtime dependencies are installed separately by the operating system and are
not vendored in this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development checks

```bash
python3 -m py_compile run_termia.py src/termia/app.py src/termia/asbru_import.py src/termia/config_actions.py src/termia/config_io.py src/termia/connection_dialogs.py src/termia/connection_utils.py src/termia/constants.py src/termia/i18n.py src/termia/main_menu.py src/termia/models.py src/termia/preferences.py src/termia/sidebar.py src/termia/statistics_utils.py src/termia/statistics_view.py src/termia/stores.py src/termia/styles.py src/termia/tabs.py src/termia/terminal_sessions.py src/termia/terminal_config.py src/termia/ui_state.py
bash -n scripts/install_dependencies.sh
bash -n scripts/install_desktop.sh
bash -n scripts/uninstall_desktop.sh
./scripts/install_dependencies.sh --check
```

Review the files included in the first commit:

```bash
git status --short --ignored
git ls-files --others --exclude-standard
```
