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

- Base issue branches on the active release-development branch, such as
  `release/0.6.0-beta.2-dev`. Use `main` only for release preparation and
  maintenance that must apply to the published-release line.
- Keep each change focused and avoid unrelated refactors or cleanup.
- Do not commit local user configuration, exported credentials, generated caches, or unrelated cleanup.
- Update the README and localized documentation when documented user-facing behavior changes.
- When UI text changes, update English, Spanish, and Catalan catalogs unless the string is intentionally language-specific.

## Architecture Boundaries

- Evolve Termia incrementally around a cohesive Core and trusted, built-in
  optional add-ons. This is an internal architecture, not a public plugin API.
- `src/termia/app.py` is the composition root and the only approved place for
  importing and assembling concrete add-on implementations. Other Core modules
  must not depend directly on those implementations; pass narrow, explicit
  contracts or callbacks instead.
- Add-ons should receive only the host capabilities and data they need. Prefer
  focused protocols and immutable data over passing `TermiaWindow`, complete
  terminal sessions, connection stores, or other broad internal objects.
- Apply these boundaries to every task, including unrelated bug fixes. If the
  affected code currently crosses a boundary, report the coupling and preserve
  behavior; do not expand the coupling or perform an unrequested refactor.
- Before modifying code, identify the affected responsibilities and whether the
  change touches Core, an add-on, or their integration boundary; consider likely
  regressions. If the requested change conflicts with an architectural boundary,
  explain the conflict and propose an approach before proceeding.
- Before changing code that touches a shared contract or optional behavior,
  review `docs/architecture/overview.md` and `docs/architecture/addons.md`;
  check `docs/WINDOW_MIXIN_CONTRACTS.md` before moving window/mixin behavior.
- Preserve behavior and stored data when an add-on is disabled. Do not
  introduce external plugins, hot reload, sandboxing, marketplaces, or a
  general plugin manager without an explicitly reviewed issue.
- Keep architecture documentation aligned with the implementation. Distinguish
  approved rules from observed implementation and unresolved questions; a
  documented current dependency is not automatically an approved exception.
- Changes to Core/add-on boundaries must include regression coverage for the
  affected Core behavior and the add-on enabled and disabled. Consult the
  architecture and regression documents before changing a shared contract.

## Changelog

- Every code change must update `CHANGELOG.md` under `Unreleased`, including internal refactors, tests, build changes, and maintenance work.
- Use a concise entry under `Added`, `Changed`, `Fixed`, `Removed`, or `Refactored`.
- Do not skip the changelog entry because the change is not user-visible.

## Versioning

- Follow `docs/VERSIONING.md` when preparing application releases or Debian
  packages.
- Increment the Termia prerelease or application version when publishing source
  changes; reserve Debian revision increments for packaging-only changes.
- Keep the source version, changelog, Debian version, annotated Git tag, GitHub
  release, and published download links consistent.

## Validation

For code changes, use the narrowest relevant checks while iterating. At
minimum, syntax-check touched Python files and run the affected test module
without verbose output. For example, for a tabs-only change:

```bash
python3 -m py_compile src/termia/tabs.py
PYTHONPATH=src python3 -m unittest tests.test_tabs
```

Rerun only a failing module or case with `-v` when detailed output helps.

After a code implementation is stable and before opening the PR, run the
complete non-verbose checks from `docs/REGRESSION_CHECKS.md` once. Do not repeat
an unchanged successful command. If later edits can affect its coverage, rerun
the relevant check; rerun the full suite only when the later change warrants
it. For documentation-only changes, validate the affected documentation,
links, and documented commands without running unrelated application tests.

When UI behavior changes, run an isolated test instance and review the relevant
manual regression sections:

```bash
scripts/run_test_instance.sh --fresh
```

## GTK/VTE Notes

- Keep terminal keyboard shortcuts centralized in terminal session handling unless a feature clearly belongs elsewhere.
- Be careful with GTK popovers and dialogs; opening dialogs from popovers can require closing or deferring the popover first.
- Treat every VTE child as a managed terminal process. Launch it through `terminal_processes.spawn_terminal_process()` and retain its captured identity instead of storing or signalling an unvalidated PID.
- When a feature closes, replaces, duplicates, detaches, or splits a terminal session, preserve the existing process-cleanup path: terminate the isolated VTE session through the terminal-session helpers so background jobs and split panes are also stopped.
- Never send signals to a process group or session unless it was captured for that VTE child and is known not to be Termia's own group. Keep the PID-reuse safeguard and the bounded `SIGTERM`/`SIGKILL` cleanup behavior intact.
- Scope CSS changes to Termia classes where practical and avoid overriding GTK or VTE internals unintentionally.
- Preserve readability on both light and dark terminal backgrounds.

## Security Notes

- Saved SSH passwords and exported configuration files can contain plain-text credentials. Treat examples and test data accordingly.
- Do not print, log, commit, or expose real passwords, private keys, or exported user configs.
- Prefer SSH keys in documentation and examples when possible.

## Pull Request Checklist

Before opening or merging a PR, confirm:

- The branch is based on the active release-development branch, or on `main`
  when the task explicitly targets the published-release line.
- The diff contains only files related to the task.
- User-facing docs and translations are updated when needed.
- Validation commands were run, or any skipped checks are explicitly noted.
- `CHANGELOG.md` was updated under `Unreleased`.
- The PR description includes a concise summary, test notes, and `Closes #<issue>` when applicable.
- For changes to Core/add-on boundaries, the PR describes the architectural
  impact, affected components or contracts, regression coverage, and known
  risks.
