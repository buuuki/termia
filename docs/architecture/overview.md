# Termia architecture overview

This document records the initial direction for Termia's gradual architectural
evolution. It is a working boundary, not a final decomposition of the codebase.
The implementation remains in the `termia` Python package; no physical
Core/add-on package split is implied.

## Approved direction

Termia is evolving around a cohesive Core and trusted, built-in optional
add-ons. The Core remains useful when an optional add-on is disabled. Add-ons
are internal implementation units, not third-party plugins or a public
extension API. See [the add-on policy](addons.md) and
[ADR-0001](decisions/ADR-0001-built-in-addons.md).

The dependency direction is:

```text
                    app.py
              composition root
                /           \
          Termia Core      Add-ons
                \           /
              narrow host contracts
```

`src/termia/app.py` may know concrete implementations so it can assemble the
application. Core modules outside that composition root must not import or call
concrete add-on implementations. They should use add-on-neutral contracts
injected by the composition root. Add-ons may consume only the specific host
capabilities and data that they require. This applies to small bug fixes and
unrelated features as well as explicit architecture work.

## Initial Core responsibilities

The following is the initial approved working boundary, not a claim that every
responsibility already has an independent module or controller:

- Application startup, shutdown, primary-window composition, and shared UI
  services.
- Local and SSH terminal execution; VTE/process ownership; session and pane
  lifecycle; tabs, splits, and workspace layout/restoration.
- Saved connection configuration, credential and host-key policy, write
  protection, configuration compatibility, and shared persistence safeguards.
- Shared UI conventions and services such as translations, theme application,
  notifications, and action dispatch.
- Host contracts through which optional functions receive lifecycle events,
  contribute actions, and use narrowly scoped services.

This boundary protects the essential terminal and connection workflow; it does
not freeze the Core or prohibit extracting an implementation behind a better
contract later.

## Current structure and observations

- `app.py` is the composition root. It creates the `ConnectionStore`, session
  registry, presenters, dialogs, and action callback sets.
- `TermiaWindow` still combines several GTK mixins. Their current shared state
  and dependencies are documented in
  [`WINDOW_MIXIN_CONTRACTS.md`](../WINDOW_MIXIN_CONTRACTS.md); that file remains
  the detailed source for mixin-level behavior.
- Session, tab, sidebar, connection, storage, and feature modules are
  co-located under `src/termia`. Directory placement alone does not identify a
  module as Core or an add-on.
- Statistics and SFTP are the first built-in optional add-ons. Their current
  implementation and known coupling are documented in [the add-on policy](addons.md).
- Notes, snippets, SCP, connection history, updates, and preference surfaces
  are not classified here. Their classification requires examining actual data
  ownership, lifecycle, and dependencies first.

## Decisions versus open questions

Approved decisions:

- Refactor incrementally and preserve behavior unless a change is explicitly
  requested.
- Keep add-ons trusted and built into Termia; there is no external plugin API
  in scope.
- Treat `app.py` as the sole composition-root exception for concrete add-on
  implementations.
- Prefer explicit, minimal contracts over dependencies on broad window or
  session internals.

Open questions that require evidence and review:

- Whether Notes, Snippets, SCP, history, or updates should be add-ons or remain
  Core capabilities.
- How feature-specific persistence should be owned and how shared settings,
  migrations, import/export, and recovery should interact with that ownership.
- The exact contracts and failure behavior for optional components when their
  startup or shutdown fails.
- Whether the current mixin composition should be replaced, and in what order.

Do not resolve these questions by assumption in an unrelated implementation.
Record a concrete proposal and review it before changing a boundary.

## Related documents

- [Internal add-on policy and current pilot](addons.md)
- [Initial architecture decision](decisions/ADR-0001-built-in-addons.md)
- [Current UI styling inventory](../UI_STYLING.md)
- [Window and mixin contracts](../WINDOW_MIXIN_CONTRACTS.md)
- [Storage schemas and migration policy](../STORAGE_MIGRATIONS.md)
- [Protected behaviors and regression checks](../REGRESSION_CHECKS.md)
