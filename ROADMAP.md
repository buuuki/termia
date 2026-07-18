# Roadmap

This document tracks planned work and longer-term ideas for Termia.
It is not a release log or a regression checklist.

## Beta Exit

Goals for moving Termia from a beta release line to a stable release line.

- [ ] Keep the current layout, menu structure, and keyboard behavior stable
      across beta releases.
- [ ] Expand automated coverage for the behaviors in
      `docs/REGRESSION_CHECKS.md` where practical, starting with pure logic and
      high-risk flows.
- [ ] Reduce duplicate configuration paths so terminal, prompt, keybinding, and
      security settings have a single source of truth.
- [ ] Tighten documentation so README, localized docs, and in-app labels all
      describe the same supported behavior.
- [ ] Review defaults and destructive actions so first-run behavior is
      predictable and reversible.
- [ ] Treat data migration, import/export, and read-only-instance behavior as
      release-blocking if they regress.
- [ ] Define a versioning policy for stable releases, including what counts as
      a breaking change.

## Near Term

- [ ] Unify local terminal configuration so font, prompt, palette, startup directory, and related defaults are defined in one place and applied consistently to new terminals and duplicated sessions.
- [ ] Simplify and standardize configuration menus, especially the `Configuration` menu hierarchy and labels, so terminal, prompt, keybindings, and security settings are easier to find.
- [ ] Review terminal context menus to reduce duplication between local terminals, SSH sessions, split panes, and sidebar or server actions.

## Next

- [ ] Continue menu cleanup by consolidating shared actions and aligning icon and label choices across popovers and context menus.
- [ ] Audit keyboard shortcuts and menu accelerators for consistency with the new configuration layout.
- [ ] Improve the discoverability of favorite servers and other sidebar actions if they remain split across several entry points.

## Longer Term

- [ ] Consider richer local terminal profiles if the current single settings model is still too limited after the configuration refactor.
- [ ] Revisit menu structure and action placement if future features make the current layout feel crowded.
- [ ] Evaluate whether any protected behaviors from `docs/REGRESSION_CHECKS.md` should become automated tests before larger UI refactors.
