# Termia

Termia is a GTK 4 terminal workspace and SSH connection manager for Linux.
It brings local and remote sessions, saved workspaces, and file transfers
together in embedded VTE terminals.

![Termia showing multiple embedded SSH terminal sessions](img/termia-screenshot.png)

[Español](docs/README.es.md) · [Català](docs/README.ca.md) · [Roadmap](ROADMAP.md)

## Features

- Local and SSH terminals with tabs, split panes, and detachable windows.
- Connections organized in nested groups, favorites, and recent connections.
- Saved workspaces and optional restoration of the previous session.
- SCP uploads and a native SFTP file explorer with transfers and cancellation.
- Reusable command snippets with categories, scope, variables, and shortcuts;
  commands are previewed before sending them.
- Personal and server-linked notes with autosave, categories, and import/export.
- Local connection storage with optional master-password encryption.
- Termia configuration import/export and connection import from Ásbrú YAML.
- Connection history and optional Statistics and SFTP add-ons.
- Configurable appearance, keybindings, and English, Spanish, and Catalan UI.

## Release status

The candidate is **0.6.1-beta**, not yet published. The latest published release
is [0.6.0-beta.4](https://github.com/buuuki/termia/releases/tag/v0.6.0-beta.4).
Changes are listed in [CHANGELOG.md](CHANGELOG.md); release preparation is
tracked in [#452](https://github.com/buuuki/termia/issues/452).

## Install on Ubuntu 24.04 or newer

The following download will become available when 0.6.1-beta is published:
[termia_0.6.1.beta-1_all.deb](https://github.com/buuuki/termia/releases/download/v0.6.1-beta/termia_0.6.1.beta-1_all.deb).

```bash
sudo apt install ./termia_0.6.1.beta-1_all.deb
```

APT installs the required dependencies, desktop launcher, and icon.
Launch **Termia** from the applications menu or run `termia`.

### Run from source

```bash
git clone https://github.com/buuuki/termia.git
cd termia
./scripts/termia-setup.sh install
python3 run_termia.py
```

The setup script checks runtime dependencies and installs a user-local launcher.
It supports Debian/Ubuntu/Linux Mint, Fedora, and Arch package managers.
Restart Termia only after setup succeeds; rerun setup if you move the checkout.
Use `./scripts/termia-setup.sh uninstall` to remove its launcher while keeping data.

### Runtime requirements

Python 3.10+, GTK 4, GtkSourceView 5, and the GTK 4 VTE namespace `Vte 3.91`.
Validation uses Ubuntu 24.04 and 26.04 laboratories. Ubuntu 22.04 and earlier
do not provide the required GTK 4 VTE runtime.

## Updates

**Beta.3 and beta.4 require a manual first upgrade to 0.6.1-beta.**
Back up your profile, close Termia, and install the new .deb over the old one.
There is no need to uninstall first.

For a clean source checkout, after the release tag is published:

```bash
git status --short
git fetch https://github.com/buuuki/termia.git tag v0.6.1-beta
git merge --ff-only v0.6.1-beta
./scripts/termia-setup.sh install
```

Stop if the first command lists local changes or the merge cannot fast-forward.
Complete setup before restarting; see
[storage compatibility](docs/STORAGE_MIGRATIONS.md) before downgrading.

From 0.6.1-beta, **About → Check for updates** detects newer beta/RC maintenance
within the same MAJOR.MINOR series, including later stable releases.
Stable installations are offered stable releases only.

The updater verifies downloads and reviews dependencies before installation.
Supported Git and Debian installations can use native administrator authorization
for required packages. Automatic Git updates require a clean release checkout on
main or its release tag; development branches and local changes need manual updates.
Unsupported cases retain the official release link. Let an installation finish,
then restart Termia; it does not update Debian-only rebuilds of the same app version.

## Help and isolated testing

Open **Help** from the main menu for workflows and your configured shortcuts.
The optional Statistics and SFTP add-ons are managed from **Add-ons**; changes
take effect after restarting and disabling them preserves their saved data.

To try a checkout using an empty profile, or a separate copy of your current data:

```bash
./scripts/run_test_instance.sh --fresh
./scripts/run_test_instance.sh --copy-current-config review
```

The first command creates a fresh profile; the second copies your current data.
Neither changes your usual profile. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for development checks and diagnostics.

## Data and security

Configuration and notes are stored under `~/.config/termia/`; history and
statistics are under `~/.local/state/termia/`. Back them up before upgrading.
Saved credentials and exports may contain readable passwords unless encrypted.
Obfuscation is not encryption, and a lost master password cannot be recovered.

SSH startup commands run whenever their saved connection starts; treat them as
executable configuration. Termia does not keep a history of terminal commands,
output, or keystrokes. See [SECURITY.md](SECURITY.md) for storage, exports,
and update security.

The SFTP backend supports saved endpoints, SSH-agent/default keys, or passwords;
OpenSSH aliases, ProxyJump, hardware-key providers, and interactive MFA are not
supported. Existing destinations are not overwritten, and partial files or
directories may remain after a cancelled or failed transfer. Verify unknown
host fingerprints before accepting them; changed host keys are refused.

## Build a Debian package

From the repository root on Ubuntu 24.04+ or a compatible Debian system:

```bash
sudo apt build-dep .
dpkg-buildpackage -us -uc -b
```

The package is created in the parent directory as
`termia_0.6.1~beta-1_all.deb`. It is separate from the official release asset.

## Documentation

- [Contributing and validation](CONTRIBUTING.md)
- [Docker laboratories](tools/docker-lab/README.md)
- [Versioning](docs/VERSIONING.md) and [storage migrations](docs/STORAGE_MIGRATIONS.md)
- [Architecture](docs/architecture/overview.md)

## License

[GNU GPL v3.0 or later](LICENSE). Runtime dependencies are provided separately
by the operating system; see [third-party notices](THIRD_PARTY_NOTICES.md).
