# Security

## Stored credentials

Termia stores configured SSH passwords in:

```text
~/.config/termia/connections.json
```

The connection file can be kept as plain text or obfuscated from `Security`
preferences. Obfuscation only reduces accidental readability of the file; it is
not encryption and is not a replacement for a secret store. The file is written
with permissions `0600`, but you should still not publish, commit, or share it.
Prefer SSH keys where possible.

Exported configuration files can also contain passwords. Treat them as sensitive
files, even when the local connection file uses obfuscated storage.

The optional `Ctrl+P` shortcut sends the saved SSH password directly to the
active remote terminal process, with an optional trailing `Enter`. It does not use
the clipboard. Enable it only on trusted desktops and use it only when the terminal
is waiting for a password.

## Local statistics

Termia stores aggregate connection, Enter-key command, keystroke, and session-duration
counters in `~/.local/state/termia/statistics.json`. It does not store typed text,
command contents, or clipboard contents, and it does not transmit these counters.
Statistics are flushed at most every 30 seconds while typing, when sessions end, and
when Termia closes.

## Reporting a vulnerability

Do not include credentials, private keys, exported configurations, or server
addresses in public issue reports. Contact the repository maintainer privately
for vulnerabilities that could expose user data.
