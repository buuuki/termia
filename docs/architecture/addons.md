# Optional add-ons and trusted external plugins

## Component types and lifecycle

SFTP ships with Termia and reads its activation setting at startup.
Diagnostics, Statistics and SCP are trusted external plugins installed manually.
Restart Termia after installing or replacing their code. Activation changes
apply on Save and Cancel discards pending choices.
See [ADR-0002](decisions/ADR-0002-trusted-external-plugins.md), which amends the
built-in-only policy in ADR-0001.

Disabling a component stops its optional behavior without deleting its data.
External plugin removal also retains saved enablement choices. Modules remain
loaded until process exit; installing or updating plugin code requires restart.
Save applies external changes sequentially and can partially succeed.

This is an application composition boundary, not a security boundary: all
optional code runs in Termia's process with its permissions. API 2 is experimental,
not a stable third-party compatibility promise. Automatic installation or updates,
hot reload, sandboxing, a marketplace and dependency management are out of scope.

## Composition and dependency rules

- The composition root in `src/termia/app.py` is allowed to import concrete
  Core and built-in add-on implementations and wire them together. It assembles
  the generic external runtime with explicit capabilities; the runtime loads
  concrete external implementations through their manifests.
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

## Statistics and SFTP

### Statistics

Core's `MetricsSessionObserver` owns pane timing and duplicate suppression.
The plugin runtime delivers connection and duration events to active subscribers.
At shutdown the observer finishes outstanding panes before requesting a flush.
The external Statistics controller aggregates the events and uses the
profile-scoped `statistics_data` capability to read, update and save aggregates.

External API 2 manifests may request `session_events`. The factory receives
contract version 1. Active controllers implement `on_session_event(event, value)`:
`connection_started` carries the server identifier and `duration_finished`
carries elapsed seconds. A `flush` event with value `None` requests an immediate
save of pending updates at session end or shutdown. Delivery is synchronous, with no replay. A callback
failure is logged and does not interrupt terminal cleanup or other controllers.

An explicit plugin activation choice takes precedence over the legacy
`AppSettings.statistics_enabled` value. New profiles default to disabled.
The host retains the aggregates in `statistics.json` across removal and
reinstallation.

### SCP

Experimental API 2 capability `scp_upload_ui` version 1 provides a contextual
controller. Its `show(language)` prepares localized views with `select_files`,
`destination` and `progress` methods for the selected operation.
The controller builds native GTK controls for the selected operation. It has
server and SSH terminal menu entry points instead of a global launcher action.
The plugin owns its UI translations. The host supplies dialogs and action button layout. Host
code owns the selected server, credentials, fingerprint decisions, destination
validation, subprocess identities and cancellation. Disabling the plugin cancels
its controllers without cancelling other transfer types.

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

## Tool contributions and Diagnostics

The internal `ToolRegistry` in `tool_launcher.py` accepts an identifier,
translation key, icon, action and availability predicate. `app.py` registers
built-in tools and external runtime contributions; the launcher renders
available contributions and dispatches callbacks. Plugin discovery belongs to
`PluginRuntime`, not the launcher. Availability is checked on popup opening,
theme refresh and deferred activation.

Under the experimental API 2 decision (#536), Diagnostics is distributed
separately and installed manually. `diagnostics_contract.py` retains the Core's
immutable counts and process identities. `app.py` passes a fresh dictionary
snapshot, window attachment and styling callbacks through `PluginRuntime`.
The plugin converts the snapshot to its own data classes; its worker receives
no GTK widgets, stores or sessions. The implementation lives under
`diagnostics/src/termia_diagnostics/` in the separate local `termia-plugins`
source tree: `diagnostics.py` reads Linux process counters and
`diagnostics_view.py` owns the singleton window, bounded history and cancellable
worker. Monitoring starts on opening and stops on closing the window.
The duplicate implementations in `src/termia` are removed. API 2 compatibility
checks, trust limits and lifecycle requirements are defined in ADR-0002.

## Further contract work

Do not expand the runtime into a general package or dependency manager. When
an actual refactoring requires it, review small contracts for:

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
