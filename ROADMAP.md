# Roadmap

This document describes the planned direction of Termia. It is not a release
log or a regression checklist; completed changes belong in `CHANGELOG.md`.
Features added during an active prerelease line may be scoped in their tracking
issues even when they were not listed here in advance. For example, the native
SFTP explorer was defined in [issue #269](https://github.com/buuuki/termia/issues/269)
and delivered in `0.6.0-beta.2`; its release details are in `CHANGELOG.md`.

## Current Target: 0.6.0-beta.N

The `0.6.0` prerelease line remains active. Each published beta iteration may
include new features, fixes, and improvements that belong to the current
release scope. Increment the trailing beta number for each published
iteration, as defined in `docs/VERSIONING.md`.

`0.6.0-beta.3` adds reusable command snippets and persistent category
management. It also fixes SSH tabs after normal nonzero shell exits and
documents configuration compatibility. The native SFTP explorer and About-based
updates were already released in beta.2; saved notes (issue #289) are not part
of beta.3. See `CHANGELOG.md` for the complete release details.

After beta.3 is published, create `release/0.6.0-beta.4-dev` from the updated
`main` branch for any further changes in this prerelease line. New feature and
bugfix branches must start from the active release-development branch and target
it with their pull requests. `main` remains the latest published release line.

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

Publish another `0.6.0-beta.N` when source changes are required after the
previous beta has been distributed, including new features within the current
scope. Packaging-only rebuilds increment only the Debian revision as defined
in `docs/VERSIONING.md`.

## Future features (unscheduled)

- Allow users to create and save custom Termia interface themes and personalize
  their colors, including selection and accent colors, independently of the
  desktop GTK theme. Keep terminal color schemes configurable separately.
