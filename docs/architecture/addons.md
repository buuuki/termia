# Internal add-on policy

## Meaning of “add-on” today

An add-on is an optional, trusted feature shipped as part of Termia and composed
at startup. The user can enable or disable it; the current pilot applies that
choice after restarting Termia. Disabling an add-on hides or omits its actions
and stops its optional behavior without deleting its data. This is an
application composition boundary, not a security boundary: add-on code runs in
the same process with the permissions of Termia.

This policy does not promise a stable API to third parties. It does not call
for dynamic discovery, package installation, hot reload, sandboxing, a
marketplace, or a general dependency manager.

## Composition and dependency rules

- The composition root in `src/termia/app.py` is allowed to import concrete
  Core and add-on implementations and wire them together.
- Other Core modules must not import or directly invoke a concrete add-on
  implementation. Supply behavior through explicit, add-on-neutral callbacks
  or protocols.
- An add-on should receive the smallest capability it needs. Prefer immutable
  event/request data and narrow service interfaces over a complete
  `TermiaWindow`, `TerminalSession`, `Server`, or `ConnectionStore`.
- Core contracts should describe behavior and data, not expose GTK widgets or
  mutable implementation details unless the UI capability itself is required.
- A new dependency crossing these boundaries must be identified in the issue
  and described in the PR. An existing coupling is not automatically an
  approved exception.

## Current Statistics and SFTP pilot

These observations describe the code after PR #305; they are not endorsements
of every current dependency as a long-term contract.

### Statistics

`SessionObserver` in `src/termia/session_observer.py` is the current seam between
terminal lifecycle code and aggregate statistics. A no-op observer provides
the disabled behavior, and `StatisticsCollector` owns aggregate updates and
deferred persistence. The composition root creates the collector only when
Statistics is enabled.

The contract currently receives `TerminalPane`/`TerminalSession` objects from
the GTK-facing session model. The collector reads their process/timing fields
and marks `duration_recorded` on the pane. This is a useful first separation,
but it is still coupled to mutable terminal-session state. A later contract
review may replace these objects with immutable lifecycle events; do not make
that implementation change as part of unrelated work.

Statistics preferences live in `AppSettings`; aggregate data is stored
separately in `statistics.json`. Disabling Statistics must retain that data.

### SFTP

SFTP already has useful lower-level boundaries: `SFTPBackend` describes backend
operations, `SFTPService` serializes cancellable work, and the view owns GTK
presentation. `SFTPTool` is the current launch adapter and is created only
when SFTP is enabled.

The launch adapter currently receives a GTK popover, a complete
`TerminalSession`, and a `Server`; the server includes saved credentials. It
also receives callbacks for session/window lookup and transfer ownership. The
terminal menu uses an injected action callback, while the sidebar currently
reaches the `sftp_tool` property directly. These are known coupling points, not
additional exceptions to the `app.py` rule. They are intentionally documented
for later review and are not changed by the policy/documentation task.

SFTP credentials are passed to an endpoint for the active operation; disabling
the add-on must not remove saved connection credentials. Transfer cancellation
and owner-session cleanup remain protected behaviors.

## Future contract direction

Do not implement a generic manager from these sketches. When an actual
refactoring requires it, review small contracts for:

- Add-on action contributions, composed by the host rather than discovered by
  menus through window attributes.
- Immutable session lifecycle events, so observers need not inspect or mutate
  GTK/session objects.
- Narrow connection and transfer requests, with explicit window-parent and
  transfer-owner capabilities instead of full server/session objects.
- Explicit persistence ownership and data-preservation semantics for each
  feature.

The required contract is the smallest one that meets the real use case. A
contract is internal unless a separate, explicitly approved project decision
states otherwise.

## When changing an add-on boundary

1. State the current dependency and proposed direction in the tracking issue.
2. Preserve existing enabled behavior, disabled behavior, stored data, and
   resource cleanup unless a behavior change is approved.
3. Test the host behavior with the add-on enabled and disabled, including
   lifecycle and failure paths relevant to the change.
4. Update the architecture document and the protected regression checklist if
   the contract or user-visible behavior changes.
5. Keep each extraction focused; do not combine it with unrelated Core cleanup.
