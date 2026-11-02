# Roadmap

This document describes the planned direction of Termia. It is not a release
log or a regression checklist; completed changes belong in `CHANGELOG.md`.
Features added during an active prerelease line may be scoped in their tracking
issues even when they were not listed here in advance. For example, the native
SFTP explorer was defined in [issue #269](https://github.com/buuuki/termia/issues/269)
and delivered in `0.6.0-beta.2`; its release details are in `CHANGELOG.md`.

## Current delivery: 0.6.1-beta maintenance

Source version: `0.6.1-beta`; Debian package: `0.6.1~beta-1`. This delivery
collects maintenance since `0.6.0-beta.4`, including the updater, GTK dialogs,
focused cleanup and UI corrections. See [CHANGELOG.md](CHANGELOG.md).
Preparation is tracked in [#452](https://github.com/buuuki/termia/issues/452)
and publication in [#454](https://github.com/buuuki/termia/issues/454).

Termia remains in beta. Maintenance may increment PATCH while retaining beta
status; new feature deliveries increment MINOR. New beta deliveries use
`-beta` without a serial; new development branches use `X.Y.Z-dev` without
a `release/` prefix or a maturity suffix. Numbered RCs remain optional.
See `docs/VERSIONING.md` for the maintenance and transition gates.

## Development after publication

Use `0.6.1-dev` until `v0.6.1-beta` is published. Then create `0.6.2-dev` from
the updated `main` for further maintenance. New issue branches and PRs use that
active development line. Future features and stable promotion require separate
scope and readiness approval.

Retain `0.6.1-dev` and `release/0.6.0-beta.5-dev` as historical branches unless
cleanup is approved. Creating a development branch does not change versions.
`main` remains the latest published release line.

The `0.6.1-beta` updater supports cross-PATCH beta maintenance and dependency
review/installation. Beta.3 and beta.4 require a manual first upgrade, documented
in the README. Fresh public asset/tag/digest verification is required at
publication; historical laboratory fixtures do not replace that check.

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
