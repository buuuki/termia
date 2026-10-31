# Roadmap

This document describes the planned direction of Termia. It is not a release
log or a regression checklist; completed changes belong in `CHANGELOG.md`.
Features added during an active prerelease line may be scoped in their tracking
issues even when they were not listed here in advance. For example, the native
SFTP explorer was defined in [issue #269](https://github.com/buuuki/termia/issues/269)
and delivered in `0.6.0-beta.2`; its release details are in `CHANGELOG.md`.

## Current Target: 0.6.1-beta maintenance

Termia remains in beta. Maintenance may increment PATCH while retaining beta
status; new feature deliveries increment MINOR. New beta deliveries use
`-beta` without a serial; new development branches use `X.Y.Z-dev` without
a `release/` prefix or a maturity suffix. Numbered RCs remain optional.
See `docs/VERSIONING.md` for the maintenance and transition gates.

`0.6.0-beta.4` is published; its release review is recorded in
[issue #386](https://github.com/buuuki/termia/issues/386). It adds saved Notes,
master-password changes, snippet shortcuts, SSH startup commands and optional
built-in tools, together with GTK interaction, process/transfer lifecycle and
memory fixes. It also includes the Docker/VM laboratories.
See `CHANGELOG.md` for the detailed changes; this is still a beta,
not an RC or stable release.

The next maintenance target is `0.6.1-beta`, subject to final scope and
validation approval. The active development branch is `0.6.1-dev`, created
at commit `075fd73` from the previous development line. It preserves the
maintenance, test, diagnostic and policy changes reviewed after beta.4.
New issue branches start from it and their PRs target it.

The previous branch, `release/0.6.0-beta.5-dev`, is retained as historical
state, not an active development target. No application/package version has
changed and no release has been published by this branch transition.
`main` remains the latest published release line.

Review pending development before allocating it to maintenance or a future
feature delivery. The development updater now supports cross-PATCH beta
maintenance and dependency review/installation; installed beta.4 clients retain
the older behavior. End-to-end upgrade and release validation remain required.
Remain in beta until the release-readiness criteria are satisfied.

`0.6.0-beta.2` was published after completing the following checks:

- [x] Exercise large mixed workspaces containing local and SSH panes.
- [x] Verify previous-session restoration, including titles, split layouts,
      saved connection references, and local working directories.
- [x] Verify clean shutdown with tabs, nested splits, detached windows, failed
      connections, and pending reconnect states.
- [x] Confirm that no managed terminal processes remain after Termia closes.
- [x] Test encrypted, locked, read-only, import/export, history, and migration
      paths without losing user data.
- [x] Install and upgrade the Debian package on every documented Ubuntu
      version and verify desktop launchers, icons, and application data.
- [x] Complete the relevant checks in `docs/REGRESSION_CHECKS.md` and keep the
      full automated suite passing.
- [x] Confirm that debug logging captures actionable lifecycle failures without
      flooding the system journal.
- [x] Keep README files, translated documentation, in-app version text,
      changelog, Debian metadata, tag, release, and download links consistent.

Publish isolated corrections as PATCH maintenance and reserve MINOR changes
for new feature deliveries. Preserve the beta suffix when readiness has not
been established. Packaging-only rebuilds increment only the Debian revision,
as defined in `docs/VERSIONING.md`.

## Future features (unscheduled)

- Allow users to create and save custom Termia interface themes and personalize
  their colors, including selection and accent colors, independently of the
  desktop GTK theme. Keep terminal color schemes configurable separately.
