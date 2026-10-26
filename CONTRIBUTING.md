# Contributing to Termia

Thanks for considering a contribution to Termia. This project is a Python GTK 4
terminal workspace and SSH connection manager with embedded VTE terminals, so
changes often affect desktop UI behavior, terminal behavior, local
configuration, file transfers, or credential-adjacent workflows.

## Before You Start

- Check existing issues and pull requests to avoid duplicate work.
- For larger changes, open or comment on an issue first so the intended behavior is clear.
- Keep changes focused. Avoid mixing unrelated refactors, formatting churn, and feature work in the same pull request.
- Never include real passwords, private keys, exported user configs, or local runtime data in commits.

## Development Setup

Install or verify system dependencies from a clone:

```bash
./scripts/termia-setup.sh install
```

The setup command verifies the GTK/VTE runtime dependencies and installs the
user-local launcher. It does not modify repository files.

Run setup after source updates and before restarting, especially when a release
adds system dependencies. Missing mandatory checks must propagate failure even
when `run_checks()` is called as a Bash conditional; do not rely on errexit
inside that condition. See [Docker upgrade validation](docs/DOCKER_UPGRADE_VALIDATION.md)
for the beta.3-to-beta.4 trials, privilege boundaries and release-time checks.

Run Termia from the checkout with:

```bash
python3 run_termia.py
```

## Branches and Commits

- Start feature and bugfix work from the active release-development branch,
  currently `0.6.1-dev`. Use an up-to-date `main` branch only
  for release preparation or work that explicitly targets the published-release
  line.
- Use descriptive branch names, preferably tied to an issue, for example `feature/14-shortcuts-configuration` or `fix/reconnect-status-message`.
- Write focused commit messages that describe the behavior change.
- Reference issues when appropriate with `Closes #<issue>` in the pull request description, not necessarily in every commit.

The `main` branch represents the latest published release. During an active
prerelease cycle, new development branches use `X.Y.Z-dev`, for example
`0.6.1-dev`, without `release/`, `beta` or `rc` in the name. A validated
delivery is published as `0.6.1-beta`, or `0.6.1` after stable readiness
approval. New beta versions have no serial. Feature and bugfix branches are
based on the approved active development branch and pull requests target it.
Once the release is validated, prepare the exact release version on the
development branch, merge it into `main`, tag and
publish the release, and create the next development branch from the updated
`main`.

PATCH maintenance is allowed while a delivery remains beta. Keep it separate
from future features, retaining the beta suffix until readiness is approved.
An explicitly approved maintenance task may use a release-development branch
from the published baseline, as described in [Versioning](docs/VERSIONING.md).
Handle maintenance and future development sequentially; do not work on
multiple issues/branches or publish multiple open PRs concurrently.

The active development branch is `0.6.1-dev`; the previous
`release/0.6.0-beta.5-dev` branch is retained as historical state.
Further branch changes, release metadata and updater support require separate
approval. This transition does not enable cross-patch updates or install
system dependencies.

## Code Guidelines

- Follow the existing module boundaries and GTK/VTE patterns.
- Review [the current `TermiaWindow` mixin contracts](docs/WINDOW_MIXIN_CONTRACTS.md)
  before moving behavior between window mixins or extracting a controller.
- Keep terminal lifecycle and keyboard behavior close to `src/termia/terminal_sessions.py` unless a change clearly belongs elsewhere.
- Keep preferences UI and persistence changes aligned between `src/termia/preferences.py`, `src/termia/stores.py`, and `src/termia/models.py`.
- Keep user-facing strings in `src/termia/i18n.py` and update English, Spanish, and Catalan together.
- If documented behavior changes, update `README.md` and the localized docs in `docs/` when relevant.
- Keep CSS scoped to Termia classes where practical and avoid unintended GTK/VTE overrides.

## Validation

For an isolated browser desktop and SSH/memory/lifecycle diagnostics, see the
Docker laboratory guides in [English](tools/docker-lab/README.md),
[Spanish](tools/docker-lab/README.es.md) and [Catalan](tools/docker-lab/README.ca.md).
Docker is optional for normal development and does not replace the checks below.

At minimum, run syntax checks for touched Python and shell files. For a broad validation pass, run:

```bash
python3 scripts/run_sandbox_tests.py
python3 -m py_compile run_termia.py scripts/compile_translations.py scripts/run_sandbox_tests.py src/termia/*.py tests/*.py
bash -n scripts/termia-setup.sh
scripts/compile_translations.py --check
```

When working inside a restricted Codex sandbox, use the runner above for the
complete local suite. It creates a private GTK display and D-Bus session over
loopback TCP and accepts unittest module names after the script for focused
runs. The `termia_tests` permission profile must allow local TCP sockets, and
`Xvfb`, `xauth`, and `dbus-daemon` must be installed. See
[Regression Checks](docs/REGRESSION_CHECKS.md#automated-checks) for details.
Outside that sandbox, `PYTHONPATH=src python3 -m unittest discover -s tests`
also works. GitHub Actions uses the private runner with branch coverage.

When changing English UI text, regenerate `po/termia.pot` with
`scripts/compile_translations.py --extract`, update both `.po` catalogs, then
compile them with `scripts/compile_translations.py` and run the `--check`
validation.

For UI, keyboard shortcut, SSH, settings, import/export, or terminal color changes, also review the relevant manual checks in `docs/REGRESSION_CHECKS.md`.

If a check cannot be run, mention that in the pull request with the reason.

GitHub Actions runs the unittest suite, translation validation, and Python
syntax checks automatically for every pull request and every push to `main`.

### Coverage with unittest

Keep unittest as the main framework; no pytest or pytest-cov is required.
Coverage runs the test process inside the existing isolated display and bus.
The installed `coverage` command must use a Python environment with access to
Termia's runtime dependencies. For a reproducible development environment:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements-ci.txt -r requirements-coverage.txt
export PATH="$PWD/.venv/bin:$PATH"
```

Run a fresh full measurement from the repository root:

```bash
coverage erase
coverage run scripts/run_sandbox_tests.py
coverage combine
coverage report
coverage html
coverage json -o htmlcov/coverage.json
```

Open `htmlcov/index.html` for module details and missing branches. A focused
run can use `coverage run scripts/run_sandbox_tests.py tests.test_terminal_cleanup`;
its results are not a full-suite baseline. Erase old data before a new baseline.
All production Python under `src/termia` is included, even if never imported.
Dependencies, tests and generated reports are outside that measurement scope.
There is initially no minimum percentage. CI preserves HTML and JSON reports
for 14 days; test failures and report-generation failures still fail CI.

Coverage records Python lines and branches, including supported Python
subprocesses. It does not measure native GTK/VTE code, remote SSH execution or
external programs. Abruptly killed Python children may not flush measurements.
The wrapper can report no data for its own process because only application
code is measured; combine the child data before interpreting the reports.
A percentage does not prove correct signal cleanup, process ownership or
Core/add-on isolation; review the relevant tests and missing branches.

### Ruff and Bandit

Install the development-only tools in a virtual environment, then compare your
working changes against the release-development branch:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-ci.txt
PATH="$PWD/.venv/bin:$PATH" python3 scripts/check_static_analysis.py --base origin/0.6.1-dev
```

The independent CI job uses the pinned versions in `requirements-ci.txt`.
It scans Python source in temporary copies without importing the application.
PRs compare their head with the merge base; pushes to `main` compare with the
previous push commit, including forced pushes. Use
`git merge-base HEAD <target-branch>` as the local base for a diverged branch.

For the first promotion from a base predating the quality gate, the helper
requires the immutable history chain: requested base → adoption commit
`fb584fc2906568cb62cd6f12b0831cd80fec682e` → approved release baseline
`50e747d1edaf2610aa6b0fdfc98675a8256493bb` → proposed head. It reports the requested
and effective SHAs and compares against that approved release baseline.
This preserves fixes made after initial adoption and rejects new occurrences.
A base at or after adoption keeps its original comparison, including forced
pushes. Missing history or an incompatible legacy lineage fails closed.
There is no configurable waiver or rule suppression. Changes to either
immutable reference require explicit policy review and regression validation.

An initial all-zero push base, invalid reports, syntax errors, missing tools or incorrect versions fail the check.

Existing findings remain visible. Only new findings block, including extra
copies of an existing finding. Source tokens and occurrence counts distinguish
findings without depending on line numbers. Renamed files are conservatively
treated as new; removed findings do not grant a budget for different findings.
This is a regression gate, not a security certification or approval of old debt.

The policy is defined in the helper: Ruff's isolated defaults target Python 3.10,
including tests, and Bandit excludes `tests/`. Virtual environments are excluded
from both. Project/user analyzer configuration and inline suppression comments
cannot weaken this gate. Review policy changes in the helper explicitly;
rerun both snapshots when updating the tool pins. Local WORKTREE mode includes
non-ignored new Python files and local deletions; CI uses committed files only.
Logs list relative paths, rule IDs and severity without source/credential text.
Exit codes are 0 for no new findings, 1 for new findings, and 2 for analysis errors.

## Pull Requests

A good pull request includes:

- A concise summary of the change.
- The issue it resolves, when applicable.
- The validation commands or manual checks performed.
- Screenshots or short notes for visible UI changes when useful.
- Any known limitations or follow-up work.

Before requesting review, make sure the diff only contains files related to the change.

## Security

Termia can store saved SSH passwords and exported configuration files in plain text. Treat credentials and exported configs as sensitive data. Prefer SSH keys in examples and documentation when possible.
