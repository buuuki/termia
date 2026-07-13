# Roadmap

This document tracks planned work and longer-term ideas for Termia.
It is not a release log or a regression checklist.

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
