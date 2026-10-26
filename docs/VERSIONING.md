# Versioning Policy

Termia uses a release-oriented versioning policy inspired by Semantic
Versioning. Application versions, Debian package revisions, Git tags, and
GitHub releases identify different parts of the release process and must not be
used interchangeably.

## Termia versions

Termia versions use `MAJOR.MINOR.PATCH` with an optional prerelease suffix:

```text
0.6.1-beta
0.6.2-beta
0.7.0-beta
0.7.1-beta
0.9.0-beta
0.9.0-rc.1
0.9.0
1.0.0
```

Before `1.0.0`:

- Increment `PATCH` for maintenance of a published delivery, including while
  it remains in beta. Maintenance contains bug fixes, security fixes and
  supporting tests, packaging and documentation; exclude unrelated features.
  For example, `0.6.0-beta.4` may be followed by `0.6.1-beta`.
- Increment `MINOR` for important features, substantial user-facing changes,
  compatibility changes, or a materially expanded release scope. A new line
  may remain beta, for example `0.7.0-beta`.
- New beta deliveries use `-beta` without a serial. Increment PATCH for a
  maintenance delivery; never replace a published beta with different code.
  Additional unpublished validation builds stay local. Numbered RCs remain
  available when a release-candidate cycle is explicitly approved.
- Release scope and maturity are independent. A patch may remain beta, and
  a later patch may become stable after meeting the stable release criteria.
  For example, `0.7.0-beta`, `0.7.1-beta`, `0.7.2-beta`, then `0.7.3`.
- A pre-1.0 line can become stable when it satisfies the documented release
  criteria. For example, a future `0.9.0-beta` could advance through
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
bug-fix pull request. The release version describes the approved scope since
its published baseline; it need not include unfinished development elsewhere.

Human-readable release titles may use `0.6.1 beta`. Canonical application
versions use `0.6.1-beta`, without a beta serial. A validated delivery may
still be beta; only an explicit readiness decision removes the suffix to
publish `0.6.1`. Existing numbered beta publications retain their identities.

Published versions, tags and package bytes are immutable. Do not rename
`0.6.0-beta.4` to `0.6.0 beta` or replace its assets with corrected code.

## Release development branches

`main` represents the latest published release. New development branches use
`MAJOR.MINOR.PATCH-dev`, for example `0.6.1-dev`, without a `release/` prefix
or a beta/RC suffix. The branch name does not decide publication maturity:
its validated delivery becomes `0.6.1-beta` while beta, or `0.6.1` only after
stable readiness approval. This is a branch convention, not a Python package
version. Changing an About-dialog development marker requires separate
implementation and comparison validation.

Feature and bugfix branches must be based on the active release-development
branch, and their pull requests must target that branch. An explicitly
approved maintenance task may instead use a release-development branch
created from the affected published baseline, excluding pending features.
Before starting it, finish or explicitly pause the current work. Preserve
one active issue/branch and one open PR at a time.

When the release is ready, update the application, changelog, Debian metadata,
and documentation to the exact release version on the development branch. Merge that validated
state into `main`, create the matching annotated tag and GitHub release, and
then create the next `<MAJOR.MINOR.PATCH>-dev` branch from the updated
`main`.

`0.6.0-beta.4` is published. The active maintenance development branch is
`0.6.1-dev`, created at `075fd73` from the previous development line after
reviewing its pending maintenance, test, diagnostic and policy changes.
The next maintenance target is `0.6.1-beta`, subject to final scope and
validation approval. The former `release/0.6.0-beta.5-dev` branch is retained
as historical state. Future feature work requires a separately approved
scope; do not automatically create or allocate work to `0.7.0`.
Update release metadata only during approved release preparation.
The completed beta.4 review is recorded in
[issue #386](https://github.com/buuuki/termia/issues/386).

## Release workflow before the first stable version

PATCH maintenance is allowed before the first stable release. Prepare urgent
corrections from the published baseline without including unfinished features.
Keep the beta suffix until the delivery meets the stable release criteria;
a numbering change alone is not evidence of readiness.

An illustrative sequence is:

| Canonical version | Meaning |
| --- | --- |
| `0.6.0-beta.4` | Existing published baseline, preserved unchanged |
| `0.6.1-beta` | Maintenance of the 0.6 delivery |
| `0.6.2-beta` | Further maintenance |
| `0.7.0-beta` | Next feature delivery |
| `0.7.1-beta` | Maintenance while still beta |
| `0.7.2-beta` | Further maintenance |
| `0.7.3` | Stable delivery, only after readiness approval |

These are examples, not publication commitments. Publish each maintenance
delivery with its own changelog, annotated tag, prerelease metadata when
applicable, verified artifacts and explicit publication approval.

Carry relevant fixes into future development before its next release.
Preserve commit ancestry needed for Git fast-forward upgrades; validate the
path from the previous published delivery, not just from a development checkout.
Perform maintenance and development work sequentially under the repository's
issue, branch and PR rules.

### Updater transition gate

The development updater selects beta/RC maintenance within the same
MAJOR.MINOR series, including later PATCH versions and stable deliveries.
Development versions are not offered updates. Published beta.4 and earlier
clients retain their original same-MAJOR.MINOR.PATCH filter and will not
automatically discover `0.6.1-beta`; that first transition requires the
release's manual installation instructions.

Before relying on automatic cross-patch updates, implement and test release
selection, package verification and upgrade behavior. Address the installed
older client's behavior explicitly; a fix in the target release cannot
retroactively change the updater performing that first upgrade.

The development Git updater reviews target requirements and offers assisted
APT installation or copyable manual commands before application. Required
packages and runtime bindings must pass verification before the checkout
changes. The .deb adapter uses native APT dependency resolution and verifies
the installed version and requirements afterwards. Unsupported systems keep
manual release guidance; no dependency check may silently pass.
Provide a tested manual path for older clients and complete disposable source
and package upgrade validation before publishing this behavior.

## Stable release criteria

A stable release is ready for regular use on Termia's documented supported
platforms when all of these conditions are met:

- The feature scope is frozen. If application source changes during final
  validation, publish a new beta delivery or release candidate and repeat the
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

## Maintenance branches for beta and stable deliveries

For both beta and stable deliveries, keep maintenance separate from development
for the next feature delivery. The following stable example also applies to
beta deliveries using their canonical version suffixes:

- `main` represents the latest stable release.
- While the latest delivery is beta, `main` instead represents that published
  beta; it must not contain unrelated unpublished feature development.
- `0.6.1-dev` is for fixes that will be published as the next patch
  release. It must not accumulate new features intended for `0.7.0`.
- `0.7.0-dev` is for the next feature release.

After stable readiness approval for `0.6.1-dev`, merge its release-ready state
into `main` and publish `0.6.1`. If another patch is needed, start
`0.6.2-dev` from the updated `main`. Keep `0.7.0-dev` separate;
do not merge the entire feature-development branch into `main` to publish a
patch.

Apply a bug fix to the newest development line first when it affects both that
line and the stable release, then backport the fix to the patch line. If a bug
affects only the stable release, fix it on the patch line first and carry the
fix forward to the development line. This keeps both versions corrected while
preserving the separate release scopes.

A patch can be published directly as `0.6.1` after validation. If a public
testing candidate is useful, publish `0.6.1-beta` first. Further beta code
corrections use a new PATCH; numbered RCs remain available when approved.
A delivery maintained in beta retains its suffix until the stable release
criteria are met and its promotion is explicitly approved.

## Current beta baseline

The existing `0.5.0-beta` release is treated as the first beta iteration of
`0.5.0`; its historical tag and release are not renamed. The latest published
source release is `0.6.0-beta.4`; the active development branch is
`0.6.1-dev`, targeting beta maintenance as described above. Historical release
and branch names remain unchanged. Creating the branch does not change the
application version or authorize release publication.

## Debian package versions

Debian package versions use:

```text
[Termia upstream version adapted for Debian]-[Debian revision]
```

Debian's `~` separator ensures prereleases sort before the corresponding stable
version. Historical numbered beta examples remain valid; new beta deliveries
use the unnumbered form. The mapping is:

| Termia version | Debian package version |
| --- | --- |
| `0.5.0-beta.1` | `0.5.0~beta.1-1` |
| `0.5.0-beta.2` | `0.5.0~beta.2-1` |
| `0.5.0-beta.3` | `0.5.0~beta.3-1` |
| `0.5.1-beta.1` | `0.5.1~beta.1-1` |
| `0.6.0-beta.1` | `0.6.0~beta.1-1` |
| `0.6.0-beta.2` | `0.6.0~beta.2-1` |
| `0.6.0-beta.3` | `0.6.0~beta.3-1` |
| `0.6.0-beta.4` | `0.6.0~beta.4-1` |
| `0.6.1-beta` | `0.6.1~beta-1` |
| `0.7.3` | `0.7.3-1` |
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

Python normalizes `0.6.1-beta` to `0.6.1b0`; this does not add a beta
counter to Termia's canonical version. Before adopting a development display
version or publishing under the new convention, verify development/beta/stable
ordering across Python, Debian and Termia. The current Termia parser accepts
unnumbered beta but defaults its internal serial to 1, unlike Python's 0.
Development versions now compare before beta and are excluded from update
selection. This does not change package metadata or the About development
marker; verify those representations during release preparation. Legacy
numbered beta parsing is retained.

Git forbids `~` in branch and tag names. Keep canonical versions and tags
such as `0.6.1-beta` and `v0.6.1-beta`; use `~` only for the internal
Debian prerelease representation. Public download filenames use periods,
such as `termia_0.6.1.beta-1_all.deb`, under the publication gate below.
The public filename rule is a Termia convention, not a general GitHub ban
on `~` in every context.

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

## Release asset names and publication gate

Debian package versions use `~` for prereleases. Public GitHub download filenames
use a period instead: `0.6.0~beta.4-1` inside the package, but
`termia_0.6.0.beta.4-1_all.deb` as the download name. Keep the local build
filename unchanged. Before uploading, create a separate copy under the public
name and confirm its SHA-256 still matches the approved package. Generate
`SHA256SUMS` against that public filename.

Upload only the approved package and checksums to a draft release. Obtain fresh
metadata and downloads; use an ignored directory such as
`tools/docker-lab/.runtime/release-check`. The example uses the published beta.4;
substitute the approved tag and digest for the release being prepared:

```bash
gh api repos/buuuki/termia/releases/tags/v0.6.0-beta.4 > tools/docker-lab/.runtime/release-check/release.json
gh release download v0.6.0-beta.4 --dir tools/docker-lab/.runtime/release-check
PYTHONPATH=src python3 scripts/check_release_assets.py \
  --release-json tools/docker-lab/.runtime/release-check/release.json \
  --assets tools/docker-lab/.runtime/release-check \
  --sha256 a8f1582fd70eb12510b29522fe164b23e38c0f69850e63a0908de6844fa995b3 \
  --published
```

Create the ignored directory first. Omit `--published` for the mandatory draft
check; it rejects an already published release. Metadata must come from the REST
endpoint, not `gh release view`, whose JSON field names differ.

Do not publish when the command fails. This is a read-only validation gate,
not a publishing wrapper: manual GitHub operations can bypass it. Explicit
publication authorization is still required. After publishing, repeat with fresh
metadata/downloads in a new empty directory and `--published`. The command
does not verify the annotated tag target or replace platform/installation tests;
perform the other release-consistency checks above as well.
