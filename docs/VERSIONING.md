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
1.0.0
```

While Termia remains in beta:

- Increment the trailing prerelease number for each published iteration of the
  same planned application version. New source changes published after
  `0.5.0-beta.1` therefore become `0.5.0-beta.2`.
- Increment `PATCH` when accumulated fixes and improvements justify a new
  application version without introducing an important new feature set. A new
  prerelease line starts at `.1`, for example `0.5.1-beta.1`.
- Increment `MINOR` for important features, substantial user-facing changes,
  compatibility changes, or a materially expanded release scope. A new line
  starts at `.1`, for example `0.6.0-beta.1`.
- Reserve `1.0.0` for the first stable release. After `1.0.0`, increment
  `MAJOR` for incompatible changes to documented behavior, supported data, or
  other public compatibility guarantees.

Alpha, beta, and release-candidate versions are prereleases. GitHub releases
for them must be marked as prereleases.

Version numbers are updated when preparing a release, not in every feature or
bug-fix pull request. The release version must describe all changes accumulated
since the previous release.

## Current beta baseline

The existing `0.5.0-beta` release is treated as the first beta iteration of
`0.5.0`; its historical tag and release are not renamed. The current source
release line is `0.5.0-beta.3`.

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
| `0.5.0` | `0.5.0-1` |

This produces the required upgrade ordering:

```text
0.5.0~beta.1-1 < 0.5.0~beta.2-1 < 0.5.0~beta.3-1 < 0.5.0-1
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
