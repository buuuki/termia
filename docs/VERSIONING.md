# Versioning Policy

Termia uses a release-oriented versioning policy inspired by Semantic
Versioning. Application versions, Debian package revisions, Git tags, and
GitHub releases identify different parts of the release process and must not be
used interchangeably.

## Termia versions

Termia versions use `MAJOR.MINOR.PATCH` with an optional prerelease suffix:

```text
0.5.0-beta.1
0.5.0-beta.2
0.5.1-beta.1
0.6.0-beta.1
0.9.0-beta.1
0.9.0-rc.1
0.9.0
1.0.0
```

Before `1.0.0`:

- While a release remains in prerelease, increment the trailing prerelease
  number for each published iteration of the same planned application version.
  New source changes published after `0.5.0-beta.1` therefore become
  `0.5.0-beta.2`.
- Increment `PATCH` when accumulated fixes and improvements justify a new
  application version without introducing an important new feature set. A new
  prerelease line starts at `.1`, for example `0.5.1-beta.1`.
- Increment `MINOR` for important features, substantial user-facing changes,
  compatibility changes, or a materially expanded release scope. A new line
  starts at `.1`, for example `0.6.0-beta.1`.
- A pre-1.0 line can become stable when it satisfies the documented release
  criteria. For example, a future `0.9.0-beta.1` could advance through
  `0.9.0-rc.1` to stable `0.9.0` without renaming the release to `1.0.0`.
- Reserve `1.0.0` for the first long-term compatibility milestone, when public
  behavior and persisted formats carry explicit compatibility guarantees.
  After `1.0.0`, increment `MAJOR` for incompatible changes to those
  guarantees.

Alpha, beta, and release-candidate versions are prereleases. GitHub releases
for them must be marked as prereleases.

A release candidate is optional. A beta may become the stable release directly
once it meets the release criteria. Publish an `rc` when an additional round
of public validation would be useful.

Version numbers are updated when preparing a release, not in every feature or
bug-fix pull request. The release version must describe all changes accumulated
since the previous release.

## Release development branches

`main` represents the latest published release. Development for the next
prerelease is isolated in one branch named with the target version and a `-dev`
suffix, for example `release/0.6.0-beta.2-dev`. This branch is a workflow
marker, not a published application or Debian package version. The About
dialog may display the development marker so that source checkouts are not
mistaken for the last published release.

Feature and bugfix branches must be based on the active release-development
branch, and their pull requests must target that branch. When the release is
ready, update the application, changelog, Debian metadata, and documentation
to the exact release version on the development branch. Merge that validated
state into `main`, create the matching annotated tag and GitHub release, and
then create the next `release/<next-version>-dev` branch from the updated
`main`.

For the current cycle, `0.6.0-beta.3` is published and
`release/0.6.0-beta.4-dev` is the active development branch. The next published
release containing source changes from this branch must be `0.6.0-beta.4`.
Release preparation may set source and Debian metadata to `0.6.0-beta.4` and
`0.6.0~beta.4-1` before publication. This does not make a local build an official
release: final validation, explicit publication approval, the annotated tag and
GitHub prerelease must still satisfy the consistency checks below. During this
phase, documentation must distinguish the prepared version from the last
published download. Track the remaining checks in
[issue #386](https://github.com/buuuki/termia/issues/386).

## Release workflow before the first stable version

Until Termia publishes its first stable version, development continues on the
current prerelease line. For example, while `0.6.0` is still in beta, publish
successive iterations as `0.6.0-beta.4`, `0.6.0-beta.5`, and so on. Bug fixes
and other changes intended for that release are included in the next beta
iteration.

Do not start a `0.6.1` patch line while `0.6.0` is still a prerelease. When
`0.6.0` meets the release criteria, publish it without a prerelease suffix.
Only then does `0.6.1` become the next patch version for maintenance.

## Stable release criteria

A stable release is ready for regular use on Termia's documented supported
platforms when all of these conditions are met:

- The feature scope is frozen. If application source changes during final
  validation, publish another beta or release candidate and repeat the
  affected checks.
- No release-blocking issue remains open or unassessed. A release blocker is a
  known defect that can cause data loss or corruption, expose credentials or
  create a security risk, prevent installation, upgrade, or startup on a
  supported platform, or make a core workflow unusable for a meaningful group
  of users without a safe workaround. An unassessed issue with plausible
  blocker impact remains blocking until its impact is understood.
- The complete automated test suite passes, and the relevant manual checks in
  [Regression Checks](REGRESSION_CHECKS.md) pass.
- A clean installation and an upgrade from the previous release are tested on
  every documented supported Ubuntu version. Verify that Termia launches and
  existing user data is preserved.
- Feedback from the prerelease cycle has been reviewed and triaged. There is no
  minimum waiting period; the release can proceed once the criteria are met.
- The [release consistency](#release-consistency) checks below pass for the
  application version, Debian package, changelog, tag, GitHub release, and
  download links.

Known non-blocking issues must be documented, along with a safe workaround
when one is available.

## Patch releases after a stable version

After a stable release, keep its maintenance work separate from development
for the next feature release. For example, after publishing stable `0.6.0`:

- `main` represents the latest stable release.
- `release/0.6.1-dev` is for fixes that will be published as the next patch
  release. It must not accumulate new features intended for `0.7.0`.
- `release/0.7.0-dev` is for the next feature release.

When `release/0.6.1-dev` is validated, merge its release-ready state into
`main` and publish `0.6.1`. If another patch is needed, start
`release/0.6.2-dev` from the updated `main`. Keep `release/0.7.0-dev` separate;
do not merge the entire feature-development branch into `main` to publish a
patch.

Apply a bug fix to the newest development line first when it affects both that
line and the stable release, then backport the fix to the patch line. If a bug
affects only the stable release, fix it on the patch line first and carry the
fix forward to the development line. This keeps both versions corrected while
preserving the separate release scopes.

A patch can be published directly as `0.6.1` after validation. If a public
testing candidate is useful, publish one or more prereleases such as
`0.6.1-beta.1` first; prereleases are optional for patch releases.

## Current beta baseline

The existing `0.5.0-beta` release is treated as the first beta iteration of
`0.5.0`; its historical tag and release are not renamed. The latest published
source release is `0.6.0-beta.3`; the active development branch targets the
next iteration, `0.6.0-beta.4`.

## Debian package versions

Debian package versions use:

```text
[Termia upstream version adapted for Debian]-[Debian revision]
```

Debian's `~` separator ensures prereleases sort before the corresponding stable
version. The mapping is:

| Termia version | Debian package version |
| --- | --- |
| `0.5.0-beta.1` | `0.5.0~beta.1-1` |
| `0.5.0-beta.2` | `0.5.0~beta.2-1` |
| `0.5.0-beta.3` | `0.5.0~beta.3-1` |
| `0.5.1-beta.1` | `0.5.1~beta.1-1` |
| `0.6.0-beta.1` | `0.6.0~beta.1-1` |
| `0.6.0-beta.2` | `0.6.0~beta.2-1` |
| `0.6.0-beta.3` | `0.6.0~beta.3-1` |
| `0.9.0-beta.1` | `0.9.0~beta.1-1` |
| `0.9.0-rc.1` | `0.9.0~rc.1-1` |
| `0.9.0` | `0.9.0-1` |
| `0.5.0` | `0.5.0-1` |

This produces the required upgrade ordering:

```text
0.5.0~beta.1-1 < 0.5.0~beta.2-1 < 0.5.0~beta.3-1 < 0.5.0-1
```

For a release line that includes a release candidate, Debian ordering is:

```text
0.9.0~beta.1-1 < 0.9.0~rc.1-1 < 0.9.0-1
```

The Debian revision starts at `-1` for every Termia application version.
Increment it to `-2`, `-3`, and so on only when rebuilding the same application
source with packaging-only changes, such as dependency metadata, maintainer
scripts, desktop integration, or package installation layout.

If the published package contains new Termia source changes, increment the
Termia prerelease or application version and reset the Debian revision to
`-1`. Do not use the Debian revision to hide application changes.

Python packaging tools may normalize versions such as `0.5.0-beta.2` to the
PEP 440 form `0.5.0b2`. This is an equivalent package-metadata representation,
not a separate Termia release version.

## Release consistency

Before publishing a release, verify that all of the following agree:

1. `src/termia/__init__.py` contains the intended Termia version.
2. `CHANGELOG.md` has a dated section for that version and a fresh
   `Unreleased` section.
3. The first `debian/changelog` entry contains the mapped Debian version.
4. The built package reports that version through
   `dpkg-deb --field <package.deb> Version`.
5. The annotated Git tag is named `v<Termia version>`.
6. The GitHub release uses the same tag and is marked as a prerelease when the
   Termia version contains `alpha`, `beta`, or `rc`.
7. Download links name the exact published asset and do not claim that an older
   package contains newer source changes.

References:

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Debian Policy: Version](https://www.debian.org/doc/debian-policy/ch-controlfields.html#version)
