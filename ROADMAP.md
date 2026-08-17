# Roadmap

This document describes the planned direction of Termia. It is not a release
log or a regression checklist; completed changes belong in `CHANGELOG.md`.

## Current Target: 0.6.0-beta.1

The current feature set is frozen while Termia stabilizes the workspace,
session, split-pane, detached-window, notification, and managed-process work
added since `0.5.0-beta.3`. Large new features are postponed until after this
stabilization release.

Before publishing `0.6.0-beta.1`:

- [ ] Exercise large mixed workspaces containing local and SSH panes.
- [ ] Verify previous-session restoration, including titles, split layouts,
      saved connection references, and local working directories.
- [ ] Verify clean shutdown with tabs, nested splits, detached windows, failed
      connections, and pending reconnect states.
- [ ] Confirm that no managed terminal processes remain after Termia closes.
- [ ] Test encrypted, locked, read-only, import/export, history, and migration
      paths without losing user data.
- [ ] Install and upgrade the Debian package on every documented Ubuntu
      version and verify desktop launchers, icons, and application data.
- [ ] Complete the relevant checks in `docs/REGRESSION_CHECKS.md` and keep the
      full automated suite passing.
- [ ] Confirm that debug logging captures actionable lifecycle failures without
      flooding the system journal.
- [ ] Keep README files, translated documentation, in-app version text,
      changelog, Debian metadata, tag, release, and download links consistent.

Publish another `0.6.0-beta.N` when source changes are required after the beta
has been distributed. Packaging-only rebuilds increment only the Debian
revision as defined in `docs/VERSIONING.md`. The 0.6 line is a stabilization
checkpoint, not a commitment to publish stable `0.6.0` immediately afterward.

## 0.7.0-beta: Mature File Transfers

SCP is part of Termia's remote-administration workflow and should be mature
before the first stable release. Improve it without attempting to build a full
graphical SFTP client.

- [ ] Separate transfer command construction, execution state, and GTK
      presentation so each layer can be tested independently.
- [ ] Define explicit pending, preparing, transferring, completed, cancelled,
      and failed states.
- [ ] Report useful progress and errors without exposing passwords, private
      keys, local personal paths, or remote command output unnecessarily.
- [ ] Make cancellation terminate only the managed transfer process and keep
      application shutdown clean.
- [ ] Support reliable retry behavior after a failed or cancelled transfer.
- [ ] Review destination selection and handling of multiple files and
      directories.
- [ ] Cover command construction, state transitions, cancellation, retry, and
      failure paths without requiring a real SSH server in automated tests.
- [ ] Keep the design reusable for a possible future SFTP backend without
      including remote file browsing in this release scope.

This work is expected to justify `0.7.0-beta.1` because it materially expands
transfer behavior and refactors a user-facing subsystem.

## Foundations Before Stable

- [ ] Version the workspace and previous-session snapshot formats and define
      explicit forward migration and safe fallback behavior.
- [ ] Keep SSH command construction and connection-option validation separate
      from GTK presentation and terminal lifecycle code.
- [ ] Expand automated coverage for option combinations, format migrations,
      mixed layouts, transfer state, and failure/reconnect paths.
- [ ] Continue consolidating terminal, prompt, keybinding, and security
      settings around clear sources of truth.

## Later Beta Feature Lines

### Quick Access

- [ ] Add Quick Connect for saved SSH connections, local-terminal profiles,
      and workspaces.
- [ ] Evolve Quick Connect into a keyboard-oriented command palette for common
      Termia actions without duplicating menu behavior.

### OpenSSH Integration

- [ ] Integrate with explicit hosts from `~/.ssh/config` without copying keys
      or sensitive configuration into Termia storage.
- [ ] Prefer OpenSSH itself for resolving aliases, `Include`, identity,
      hostname, user, port, and precedence semantics.
- [ ] Add explicit ProxyJump and bastion-host configuration where Termia needs
      a saved per-connection override.
- [ ] Improve SSH-agent and identity visibility without handling private-key
      material directly.

### Later Remote Administration

- [ ] Add local, remote, and dynamic/SOCKS SSH port forwarding with a clear
      view of active tunnels and managed cleanup.
- [ ] Add reusable global and group-scoped command snippets with prompted
      variables and no implicit remote execution.
- [ ] Consider broadcast input only with explicit pane selection, a persistent
      visual warning, easy cancellation, and safeguards against accidental
      multi-host execution.
- [ ] Improve connection-health states, background activity indicators,
      reconnect policy, and configurable notifications.
- [ ] Consider a CLI for opening saved connections and workspaces from scripts
      and desktop launchers.

## Release Candidate and First Stable Release

Do not assign the first stable release number only because a planned beta line
has finished. Review release readiness after SCP and the core persisted formats
have matured.

Advance from beta to a release candidate when:

- no critical or important reproducible bugs remain open;
- no known crash, data-loss, orphan-process, transfer-cleanup, or security
  regression remains;
- application behavior and persisted formats are frozen for the release;
- automated and manual regression checks pass; and
- only release-blocking fixes, packaging, and documentation changes remain in
  scope.

Publish another release candidate when a fix changes application source or
behavior. Publish stable only after a release candidate has received
representative daily use without an important regression and every release
artifact has been verified. At that review, choose a stable pre-1.0 version or
`1.0.0` according to the compatibility guarantees Termia is ready to make.

## Deliberately Deferred

Termia should remain focused on terminal-based remote administration. A full
SFTP client, RDP/VNC, Kubernetes or Docker GUIs, embedded web browsing, broad
monitoring, and file editing are not immediate roadmap goals. They should be
considered only when they strengthen the core workflow without turning Termia
into an unfocused all-in-one application.
