# Contributing to Termia

Thanks for considering a contribution to Termia. This project is a Python GTK 4 SSH connection manager with embedded VTE terminals, so changes often affect desktop UI behavior, terminal behavior, local configuration, or credential-adjacent workflows.

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

Run Termia from the checkout with:

```bash
python3 run_termia.py
```

## Branches and Commits

- Start feature and bugfix work from an up-to-date `main` branch.
- Use descriptive branch names, preferably tied to an issue, for example `feature/14-shortcuts-configuration` or `fix/reconnect-status-message`.
- Write focused commit messages that describe the behavior change.
- Reference issues when appropriate with `Closes #<issue>` in the pull request description, not necessarily in every commit.

## Code Guidelines

- Follow the existing module boundaries and GTK/VTE patterns.
- Keep terminal lifecycle and keyboard behavior close to `src/termia/terminal_sessions.py` unless a change clearly belongs elsewhere.
- Keep preferences UI and persistence changes aligned between `src/termia/preferences.py`, `src/termia/stores.py`, and `src/termia/models.py`.
- Keep user-facing strings in `src/termia/i18n.py` and update English, Spanish, and Catalan together.
- If documented behavior changes, update `README.md` and the localized docs in `docs/` when relevant.
- Keep CSS scoped to Termia classes where practical and avoid unintended GTK/VTE overrides.

## Validation

At minimum, run syntax checks for touched Python and shell files. For a broad validation pass, run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m py_compile run_termia.py scripts/compile_translations.py src/termia/app.py src/termia/asbru_import.py src/termia/config_actions.py src/termia/config_io.py src/termia/connection_dialogs.py src/termia/connection_utils.py src/termia/constants.py src/termia/i18n.py src/termia/keybindings.py src/termia/main_menu.py src/termia/models.py src/termia/preferences.py src/termia/sidebar.py src/termia/statistics_utils.py src/termia/statistics_view.py src/termia/stores.py src/termia/styles.py src/termia/tabs.py src/termia/terminal_sessions.py src/termia/terminal_config.py src/termia/ui_state.py
bash -n scripts/termia-setup.sh
scripts/compile_translations.py --check
```

When changing English UI text, regenerate `po/termia.pot` with
`scripts/compile_translations.py --extract`, update both `.po` catalogs, then
compile them with `scripts/compile_translations.py` and run the `--check`
validation.

For UI, keyboard shortcut, SSH, settings, import/export, or terminal color changes, also review the relevant manual checks in `docs/REGRESSION_CHECKS.md`.

If a check cannot be run, mention that in the pull request with the reason.

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
