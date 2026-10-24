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
  currently `release/0.6.0-beta.4-dev`. Use an up-to-date `main` branch only
  for release preparation or work that explicitly targets the published-release
  line.
- Use descriptive branch names, preferably tied to an issue, for example `feature/14-shortcuts-configuration` or `fix/reconnect-status-message`.
- Write focused commit messages that describe the behavior change.
- Reference issues when appropriate with `Closes #<issue>` in the pull request description, not necessarily in every commit.

The `main` branch represents the latest published release. During an active
prerelease cycle, the next release has one development branch named with the
target version and a `-dev` suffix, for example
`release/0.6.0-beta.4-dev`. Feature and bugfix branches are based on that
branch and pull requests target it. Once the release is validated, prepare the
exact release version on the development branch, merge it into `main`, tag and
publish the release, and create the next development branch from the updated
`main`.

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
also works. GitHub Actions retains its existing command.

When changing English UI text, regenerate `po/termia.pot` with
`scripts/compile_translations.py --extract`, update both `.po` catalogs, then
compile them with `scripts/compile_translations.py` and run the `--check`
validation.

For UI, keyboard shortcut, SSH, settings, import/export, or terminal color changes, also review the relevant manual checks in `docs/REGRESSION_CHECKS.md`.

If a check cannot be run, mention that in the pull request with the reason.

GitHub Actions runs the unittest suite, translation validation, and Python
syntax checks automatically for every pull request and every push to `main`.

### Ruff and Bandit

Install the development-only tools in a virtual environment, then compare your
working changes against the release-development branch:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-ci.txt
PATH="$PWD/.venv/bin:$PATH" python3 scripts/check_static_analysis.py --base origin/release/0.6.0-beta.4-dev
```

The independent CI job uses the pinned versions in `requirements-ci.txt`.
It scans Python source in temporary copies without importing the application.
PRs compare their head with the merge base; pushes to `main` compare with the
previous push commit, including forced pushes. The local helper compares the
exact base supplied; use `git merge-base HEAD <target-branch>` as the base if
your local branch has diverged. Missing history, an initial all-zero push base, invalid
reports, syntax errors, missing tools or incorrect versions fail the check.

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
