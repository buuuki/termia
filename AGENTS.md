# AGENTS.md

Guidance for coding agents and maintainers working on Termia.

## Scope

These instructions apply to the whole repository.

## Project Context

Termia is a Python GTK 4 SSH connection manager with embedded VTE terminals. It stores SSH connection configuration locally, supports English, Spanish, and Catalan UI text, and keeps user-facing documentation in the root README plus localized docs.

Keep changes small, explicit, and aligned with the existing GTK/VTE architecture. Avoid unrelated refactors while solving a feature or bug.

## Repository Map

- `run_termia.py`: source-checkout launcher.
- `src/termia/app.py`: main application composition.
- `src/termia/terminal_sessions.py`: terminal session lifecycle, keyboard handling, reconnect behavior, and SSH launch flow.
- `src/termia/tabs.py`: tab management behavior.
- `src/termia/preferences.py`: preferences UI and settings persistence hooks.
- `src/termia/i18n.py`: UI strings for English, Spanish, and Catalan.
- `src/termia/stores.py` and `src/termia/models.py`: configuration models and persistence.
- `docs/REGRESSION_CHECKS.md`: manual regression checklist and minimum validation commands.
- `scripts/`: dependency and desktop integration helpers.

## Development Workflow

- Start from `main` unless the task names an existing branch.
- Use feature branches for issue work, for example `feature/14-shortcuts-configuration`.
- Keep commits focused and use messages that describe the resolved behavior. Include the issue reference when applicable.
- Do not commit local user configuration, exported credentials, generated caches, or unrelated cleanup.
- If a task changes user-facing behavior, update the README and localized docs when the behavior is documented there.
- If a task changes UI text, update all three translation dictionaries in `src/termia/i18n.py` unless the string is intentionally language-specific.

## Validation

Run the narrowest useful checks for the change. At minimum, syntax-check touched Python files. For broader changes, use the project checks from `docs/REGRESSION_CHECKS.md`:

```bash
python3 -m py_compile run_termia.py src/termia/app.py src/termia/asbru_import.py src/termia/config_actions.py src/termia/config_io.py src/termia/connection_dialogs.py src/termia/connection_utils.py src/termia/constants.py src/termia/i18n.py src/termia/main_menu.py src/termia/models.py src/termia/preferences.py src/termia/sidebar.py src/termia/statistics_utils.py src/termia/statistics_view.py src/termia/stores.py src/termia/styles.py src/termia/tabs.py src/termia/terminal_sessions.py src/termia/terminal_config.py src/termia/ui_state.py
bash -n scripts/install_dependencies.sh
bash -n scripts/install_desktop.sh
bash -n scripts/uninstall_desktop.sh
```

When the system packages are available, also run:

```bash
./scripts/install_dependencies.sh --check
python3 run_termia.py
```

For UI, terminal, keyboard shortcut, SSH, settings, or import/export changes, review the relevant sections in `docs/REGRESSION_CHECKS.md` and mention what was covered.

## GTK/VTE Notes

- Keep terminal keyboard shortcuts centralized in terminal session handling unless a feature clearly belongs elsewhere.
- Be careful with GTK popovers and dialogs; opening dialogs from popovers can require closing or deferring the popover first.
- Scope CSS changes to Termia classes where practical and avoid overriding GTK or VTE internals unintentionally.
- Preserve readability on both light and dark terminal backgrounds.

## Security Notes

- Saved SSH passwords and exported configuration files can contain plain-text credentials. Treat examples and test data accordingly.
- Do not print, log, commit, or expose real passwords, private keys, or exported user configs.
- Prefer SSH keys in documentation and examples when possible.

## Pull Request Checklist

Before opening or merging a PR, confirm:

- The branch is based on current `main`.
- The diff contains only files related to the task.
- User-facing docs and translations are updated when needed.
- Validation commands were run, or any skipped checks are explicitly noted.
- The PR description includes a concise summary, test notes, and `Closes #<issue>` when applicable.
