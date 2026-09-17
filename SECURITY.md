# Security

## Stored credentials

Termia stores configured SSH passwords in:

```text
~/.config/termia/connections.json
```

The connection file can be kept as plain text, obfuscated, or encrypted from
`Security` preferences. Obfuscation only reduces accidental readability of the
file; encrypted storage uses a master password and asks for it each time Termia
starts. If the master password is lost, Termia cannot recover the encrypted
connection data. The file is written with permissions `0600`, but you should
still not publish, commit, or share it. Prefer SSH keys where possible.

Exported configuration files can also contain passwords. Treat them as sensitive
files, even when the local connection file uses obfuscated storage.

The configured password shortcut, `Ctrl+P` by default, sends the saved SSH
password directly to the active remote terminal process, with an optional trailing
`Enter`. It does not use the clipboard. Enable it only on trusted desktops and
use it only when the terminal is waiting for a password.

## Local statistics

Termia stores aggregate connection, Enter-key command, keystroke, and session-duration
counters in `~/.local/state/termia/statistics.json`. It does not store typed text,
command contents, or clipboard contents, and it does not transmit these counters.
Statistics are flushed at most every 30 seconds while typing, when sessions end, and
when Termia closes.

## Application updates

Update checks are explicit and contact the public GitHub Releases API. GitHub
receives the normal network request (including the client IP), but Termia sends
no saved configuration, SSH endpoints or credentials. Network responses have
size/time limits. Downloads accept HTTPS only and restrict redirects to GitHub's
official release-asset host. The SHA-256 digest comes from the official API over
TLS; this detects corrupt/substituted bytes but is not an independent publisher
signature and does not protect against compromise of the official repository.

Debian packages require a matching digest, package name, application version,
architecture and an upgrade over the installed package. The desktop polkit agent
handles administrator authentication; Termia never collects that password.
APT resolves dependencies and refuses removals. Already-running installations
are not killed when the UI closes. Temporary packages are removed afterwards;
the updater retains a per-user lock across profiles until the operation ends.

Git updates only fast-forward clean release checkouts to a tag fetched from the
fixed official HTTPS repository. They never reset, stash or force-push. Git hooks
are disabled for updater commands. Git configuration is trusted local state;
do not run a checkout supplied by an untrusted third party. The fetched tag may
remain after cancellation, but the working tree is not changed by preparation.

## Reporting a vulnerability

Do not include credentials, private keys, exported configurations, or server
addresses in public issue reports. Contact the repository maintainer privately
for vulnerabilities that could expose user data.
