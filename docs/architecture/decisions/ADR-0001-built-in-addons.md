# ADR-0001: Start with built-in optional add-ons

- Status: Accepted
- Date: 2026-10-09

## Context

Termia is beginning a gradual separation of optional functionality from its
essential terminal and SSH workflows. Statistics and SFTP are the first pilot.
The project needs a useful internal boundary without taking on the complexity
or compatibility cost of a third-party plugin system.

## Decision

- Add-ons in the current architecture are trusted components shipped with
  Termia.
- Enablement is resolved during startup; changing an add-on preference takes
  effect after restarting the application.
- Disabled add-ons do not contribute their optional actions or behavior and do
  not cause their stored data to be deleted.
- `src/termia/app.py` is the sole composition-root exception allowed to import
  and assemble concrete add-on implementations. Other Core modules depend on
  narrow, add-on-neutral contracts.
- These contracts are internal. This decision does not establish a public API
  or support external add-on loading.

## Consequences

- The Core can start without optional functionality and remains responsible for
  the terminal, sessions, connections, and shared host services.
- Add-on boundaries can evolve as real use cases are studied; they are not a
  compatibility promise.
- Current Statistics and SFTP integrations have known coupling to session,
  server, and GTK state. Those dependencies are recorded in
  [`addons.md`](../addons.md) and are not retroactively approved by this ADR.
- External plugin loading, hot reload, sandboxing, marketplaces, and a general
  plugin manager require a new reviewed decision.

## Revisit when

The built-in boundary proves insufficient for a concrete use case, or the
project considers supporting independently distributed extensions.
