# Docker upgrade compatibility validation

Date: 2026-10-20. Tracking: [issue #371](https://github.com/buuuki/termia/issues/371).

This report records local Debian-package and Git-source upgrade trials from
Termia beta.3 to synthetic beta.4 candidates on Ubuntu 24.04 and 26.04. It is
evidence for those paths, not certification of all Termia features, a published
beta.4 release, or a substitute for the [release checklist](REGRESSION_CHECKS.md).

## User-facing upgrade sequence and permissions

For an installation from a Git clone:

1. The **beta.3 updater**, with its original code, fetches the selected release
   tag and fast-forwards an eligible clean checkout. It does not install system
   dependencies and does not invoke sudo. The user must own or have write
   permission to the checkout.
2. Before restarting Termia, run this in the updated checkout:

   ```bash
   scripts/termia-setup.sh install
   ```

3. That is now the **beta.4 setup script**, including the dependency-check fix
   described below. On Ubuntu, missing dependencies trigger `sudo apt-get update`
   and `sudo apt-get install`. Sudo may ask for the user's password. When all
   dependencies are already available, setup does not need sudo. The launcher
   and icon are installed in the user's data directory.
4. Restart Termia after setup succeeds. Starting beta.4 without GtkSourceView 5
   fails; updating the source alone is insufficient when that dependency is absent.

Beta.3 already displays the instruction to run setup after a source update; no
patch to beta.3 is required. The new script must be included in the published
beta.4 source. For Debian installations, the updater instead uses polkit and
APT to install the verified package and resolve its dependencies. Do not run
the Termia application itself with sudo.

## Inputs and isolation

- Sources came from the local `v0.6.0-beta.3` tag and development commit
  `d480662`. A corrected Git candidate additionally contained the three-line
  setup fix tracked by #371.
- Temporary candidate copies used application version `0.6.0-beta.4`; the
  Debian candidate used package version `0.6.0~beta.4-1`. Release version
  metadata in the working repository was not changed for the trials.
- Ubuntu base images were `ubuntu:24.04` and `ubuntu:26.04`, architecture amd64.
  The packages built for Termia were architecture `all` and the same binaries
  were installed on both distributions. Ubuntu 26.04 reported 26.04.1 LTS.
- Fixtures were mounted read-only at `/input`. Build and test repositories
  lived inside the containers under `/work`. No user home, desktop session,
  real configuration, SSH endpoint, credentials or Docker socket was mounted.
- Docker daemon access was authorized outside the restricted execution sandbox.
  Package installation occurred inside containers, never on the developer's host.
- APT used Ubuntu repositories. GitHub release responses and the updater's Git
  transport were simulated locally as described below. No release was published.

These trials did not run the entire Termia suite on either distribution.
The temporary integration harnesses and candidate artifacts are not shipped as
release assets or installed as repository test dependencies.

## Debian package construction

A separate Ubuntu 24.04 build container installed `build-essential`, debhelper,
dh-python, python3-all, python3-setuptools, pybuild-plugin-pyproject and Termia's
declared build dependencies. Sources were exported with `git archive` and copied
into the container. The first build stopped because `build-essential` was
missing; adding that build-tool metapackage resolved the environment issue.

Both versions were built with:

```bash
DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b
```

`nocheck` deliberately skipped the general test suite during packaging; it did
not skip the specific upgrade and startup checks below. The beta.3 package was
rebuilt from its tag, not downloaded from the published release. The beta.4
candidate changed version values only in its temporary source copy, not the
working repository. It was not a fully prepared release.

`dpkg-deb --field` verified Package, Version, Architecture and Depends. The beta.3
package did not depend on GtkSourceView; the beta.4 candidate declared
`gir1.2-gtksource-5`. Packages were transferred out using `docker cp` and mounted
read-only into separate fresh runtime containers.

## Debian updater trial

For each Ubuntu version, the runtime container performed these steps:

1. Install beta.3 through APT, plus `pkexec`, `xvfb`, `xauth` and `dbus-x11` for
   the harness. Verify GtkSourceView GI bindings and library are absent and that
   `gi.require_version("GtkSource", "5")` fails.
2. Import beta.3 and compare its installed `update_service.py` and
   `update_installers.py` bytes with the original tagged sources.
3. Inject a local opener into beta.3's actual `ReleaseClient`. It returns a
   synthetic release response and the candidate's real package bytes for the
   official-format URLs expected by the client. Package size and SHA-256 come
   from the local candidate; no GitHub HTTPS request is made.
4. Verify beta.3 selects the beta.4 prerelease in the same application line,
   excludes a draft, and provides no installable asset when the digest is missing.
5. Use the real Debian installation detection and package preparation code,
   including SHA-256, package identity/version/architecture and upgrade checks.
6. Exercise `DebianInstaller.apply()`. The harness checks the generated command
   and removes only the `pkexec --disable-internal-agent` prefix, executing the
   actual APT `--yes --no-remove` installation as container root. This is not a
   test of interactive polkit authorization.
7. Query installed versions and check that a synthetic configuration-directory
   sentinel retains its bytes. This sentinel is not a test of real settings,
   credential, notes or session migrations.
8. In a new Python process, verify beta.4 imports, create the GtkSource Notes
   editor and check application startup under a private D-Bus session and Xvfb.

On Ubuntu 24.04, the first smoke check covered imports and the Notes editor;
full main-window startup was checked afterwards in a container derived from a
temporary snapshot of the successfully upgraded container. Ubuntu 26.04 ran
the startup check directly after its upgrade.

## Git-source updater trial

Fresh containers installed Git, sudo, beta.3 runtime dependencies, desktop-file
utilities, Xvfb and D-Bus tools, but not GtkSourceView. A local Git bundle
provided the real history from beta.3 through the development baseline.

The harness created a bare fixture repository, made a synthetic beta.4 candidate
commit/tag, and served it with `git daemon` bound only to container loopback.
The candidate was not tagged or committed in the developer's repository. Each
test cloned beta.3 into a separate working checkout, switched to `main`, ran
the beta.3 setup, and imported the unchanged beta.3 updater from that checkout.

For updater fetches only, an injected command runner verified the fixed official
HTTPS URL and substituted the loopback Git daemon URL. Real Git commands still
ran with the updater's hook suppression, file-transport restriction and
fast-forward safeguards. This substitution does not validate public HTTPS
transport, GitHub availability or a published tag.

The checks verified:

- Clean `main` and a detached beta.3 release tag are eligible.
- Modified tracked files, untracked files, feature branches and a development
  version are blocked without deleting or overwriting the fixture changes.
- Changes introduced after preparation block apply and are retained.
- A successful update moves HEAD to the synthetic beta.4 tag with the original
  beta.3 commit as an ancestor, using `--ff-only`; no automatic stash occurs.
- The configured remote was deliberately unusable; the fixed updater source
  was still used. A synthetic post-merge hook was not executed.
- Git updates do not install dependencies. Importing beta.4 before setup failed
  for missing GtkSource, as expected. Beta.3's existing success text instructs
  the user to run `scripts/termia-setup.sh install`.
- After the corrected beta.4 setup, GtkSourceView is installed, the application
  and Notes editor start in a fresh process, and the Git working tree is clean.

### Defect discovered and corrected

The initial Git trial failed on both distributions after source advancement.
Setup printed a missing GtkSource error, then incorrectly reported that runtime
dependencies were already available and installation had completed. Beta.4
still could not start.

`ensure_dependencies()` calls `run_checks()` in an `if`. Bash does not apply
errexit within that condition's function body. Without explicit propagation,
later successful commands masked an earlier mandatory-check failure. The fix
adds `|| return` to the Python/GI, SSH and sshpass checks. It leaves dependency
lists, privilege handling and optional font fallback unchanged.

Five committed regression tests in [test_setup_script.py](../tests/test_setup_script.py)
exercise the real shell functions with synthetic command stubs. The suite
exposed the defect in the original implementation and passed with the fix. Tests cover
conditional error propagation, dependencies already available, installation
and rechecking, package-manager failure and failed post-install verification.
The corrected Git integration trial then passed on both Ubuntu versions.

## Startup checks and observed results

The temporary smoke harness used a private display and session bus:

```bash
dbus-run-session -- xvfb-run -a python3 /input/smoke.py
```

Here `/input/smoke.py` was a temporary harness, not a repository command. For
source trials it used the updated checkout's `src` directory on `PYTHONPATH`.
It verified beta.4's version, a `GtkSource.View` with line numbers, and a visible
main window from `TermiaApp`, then quit. Software-rendering/accessibility
environment settings belonged only to the harness. Accessibility and EGL/DRI3
warnings observed in virtual displays did not prevent these checks.

| Scenario | Ubuntu 24.04 | Ubuntu 26.04 |
|---|---|---|
| Debian: beta.3 without GtkSourceView → beta.4 candidate via APT | Passed | Passed |
| Git: original candidate setup after source advancement | Failed: missing dependency masked | Failed: missing dependency masked |
| Git: corrected candidate setup installs GtkSourceView | Passed | Passed |
| Git checkout guards, successful fast-forward and hook suppression | Passed | Passed |
| Updated main window and native Notes editor in virtual display | Passed | Passed |
| GtkSourceView GI/library version installed | 5.12.0-1build1 | 5.18.0-3 |

The Debian trials used package version `0.6.0~beta.4-1`; Git trials used a
synthetic beta.4 tag. The candidates are not official release artifacts.

## Repeating the checks safely

The focused, versioned regression check is:

```bash
python3 scripts/run_sandbox_tests.py tests.test_setup_script
bash -n scripts/termia-setup.sh
```

For integration reruns, recreate the fixtures and temporary harness implementing
the steps above. Use a separate builder and fresh runtime containers for each
distribution and installation path. Never preinstall GtkSourceView into the
runtime baseline, mount real configurations or reuse the developer's checkout
as the writable fixture. For a corrected Git trial, include the setup fix in
the temporary candidate before tagging it. Do not run setup on the host as a
test. Obtain authorization before Docker/package operations.

The initial broken and corrected Git trials are intentionally separate results;
do not hide the missing-dependency failure by installing it before testing setup.
Containers and the one temporary snapshot image were removed after inspecting
their exit status. Preexisting containers and base images were retained.
Temporary local harnesses and artifacts were retained for immediate reruns but
are not guaranteed to survive system cleanup. This report and the regression
tests, not temporary paths or container identifiers, are the durable record.

## Remaining release-time checks

- Check the actual published tag, version metadata and final Debian artifact,
  including its GitHub-provided SHA-256 digest and real HTTPS download.
- Ensure the final beta.4 source contains the setup fix and remains a descendant
  of beta.3; repeat affected trials if final source or packaging changes.
- Validate interactive polkit and sudo authorization as an ordinary user on a
  supported desktop or VM. Trials ran as root inside containers.
- These results do not validate GPU acceleration, Wayland/window-manager focus,
  remote SSH/SFTP behavior, all user-data migrations, Fedora/Arch installation,
  or the entire application regression suite on each Ubuntu version.

No credentials, personal paths, private infrastructure, user configuration or
unrelated Docker inventory are included in this report.
