# TermiaWindow mixin contracts

This document records the implicit contract between `TermiaWindow` and its
mixins. It is an inventory of the current architecture, not a requirement that
new components inherit from the window.

The purpose of the inventory is to make dependencies visible before mixins are
replaced gradually with explicit controllers and services.

For the broader Core/add-on direction and approved dependency rules, see the
[architecture overview](architecture/overview.md). This document remains the
detailed reference for current window and mixin contracts; documented current
couplings are observations, not automatic exceptions to those rules.

## Shared window services

Most mixins expect the window to provide some combination of these services:

- `store`: the `ConnectionStore` and its app, terminal, connection, history,
  and statistics data.
- `t(key)`: translation using the language stored in `store`.
- `toast_label`: grouped shared status and error feedback; repeated calls to
  `set_label()` append messages to the current visible notification group.
- `ensure_writable()`: write-lock and encrypted-store guard.
- `configure_write_action(widget)`: sensitivity and tooltip configuration for
  actions that require writable storage.
- `add_dialog_action_button()` and `add_dialog_action_buttons()`: common dialog
  action construction.
- GTK window behavior inherited by `TermiaWindow`, including `set_title()`,
  `get_focus()`, and `get_pango_context()`.

These services are currently obtained through `self`. Future components should
receive only the services they use.

## State owned by the composed window

`TermiaWindow.__init__()` and `_build_ui()` create the shared state consumed by
the mixins:

- Persistence and feedback: `store`, `toast_label`.
- Session state: `session_registry` and an injected `session_observer` for
  optional lifecycle consumers. The Statistics observer owns its run counter
  and pending save timer.
- Explicit actions: `main_menu_actions`, `terminal_menu_actions`, and
  `tab_lifecycle_actions`.
- Terminal keyboard dispatch: `terminal_shortcut_handler(keyval, modifiers,
  session, terminal) -> bool`, composed in `app.py` with the snippet dialog
  adapter. The terminal mixin calls this only after existing terminal actions
  and does not import snippet UI implementations. The adapter checks focus,
  pane availability, scope, and assignments, then reuses variables/preview;
  it must not send a command without explicit confirmation. This remains a
  GTK session-level contract, not a new generic add-on API.
- Sidebar selection: `selected`, `selected_tree_widget`,
  `group_expanded_state`, `collapse_groups_on_startup`, `tree_widgets`, and
  `sidebar_drag_server_id`, and `active_context_popover`.
- Main UI widgets: `body`, `sidebar`, `search_entry`, `server_list`,
  `server_scroller`, `summary_label`, `title_label`, `info_label`,
  `terminal_stack` (`Gtk.Stack`), `session_tab_bar` (`Gtk.Box`),
  `session_tab_scroller` (`Gtk.ScrolledWindow`) and `session_tab_controls`.
- Header widgets: sidebar, new-tab, menu, read-only, add, expand, and collapse
  controls.

Some mixins add transient state after construction:

- `SidebarMixin`: `sidebar_tree_root`, `sidebar_tree_model`,
  `sidebar_tree_selection`, `sidebar_projection`, `visible_tree_rows`,
  `sidebar_model_token`, `scroll_restore_id`, `sidebar_visible`, and
  `sidebar_width`.
- `TabsMixin`: `tab_drag_session_id`.
- `TerminalSessionsMixin`: updates `run_connections` and `stats_save_id`.

## Mixin dependency inventory

### `ConfigActionsMixin`

- Reads: `store`, `toast_label`.
- Writes: clears `selected` when configuration is reset or imported.
- Window services: translation, writable guard, dialog buttons, theme
  application, and sidebar refresh.
- Cross-mixin dependency: `SidebarMixin.refresh_list()`.

### `ConnectionDialogsMixin`

- Reads: `store`, `toast_label`.
- Window services: translation, writable guard, dialog buttons, and sidebar
  refresh.
- Cross-mixin dependencies:
  `TerminalSessionsMixin.default_local_terminal_shell()` and
  `SidebarMixin.refresh_list()`.

### `MainMenuMixin`

- Reads: the explicitly composed `MainMenuActions` callback set.
- Window services: translation and writable-action configuration.
- Cross-mixin dependencies: none for menu dispatch; the shared dialog-button
  helpers and built-in Help and About dialog implementations remain on the
  mixin.
- Extracted component: `MainMenuActions` defines the actions supplied by the
  application composition root. The menu builder no longer discovers
  configuration, preference, history, statistics, or notes callbacks on the
  window.

### Preference mixins

`PreferencesMixin` only combines the five focused preference mixins.

- `GeneralPreferencesMixin` reads `store` and `toast_label`; it updates sidebar
  expansion state and calls theme, sidebar, session-status, translation, and
  list-refresh methods.
- `TerminalPreferencesMixin` reads `store` and `toast_label`; it needs Pango
  font information, tree-style refresh, and application of terminal settings
  to open sessions, and composes the shared Terminal/Prompt dialog.
- `PromptPreferencesMixin` provides reusable prompt preset and preview helpers
  to the combined Terminal preferences surface.
- `SecurityPreferencesMixin` reads `store` and `toast_label`; it otherwise
  needs translation, the writable guard, and dialog helpers.
- `KeybindingPreferencesMixin` reads `store` and `toast_label`; it otherwise
  needs translation, the writable guard, and dialog helpers.

The general and terminal dialogs have cross-feature side effects. Security and
keybinding dialogs have comparatively small contracts.

### `SidebarMixin`

- Reads: `store`, the sidebar widgets, selection state, expansion state,
  `toast_label`, and current GTK focus.
- Writes: selection, projection, expansion widgets, context-menu state,
  sidebar visibility and width, visible rows, and scroll-restoration state.
- Cross-mixin dependencies: connection dialogs, terminal opening, file
  transfer, writable checks, and local-shell defaults.
- Architectural note: this is both a renderer and a controller. Projection,
  selection/navigation, rendering, and context actions are separate
  responsibilities despite sharing one mixin.
- GTK's tree model, expanders, list view, and single selection own disclosure,
  selection, scrolling, and in-view navigation. Termia provides projected row
  identities, filtering and expansion preferences, existing action dispatch,
  and private server-to-group drags. Recycled rows and deferred callbacks are
  checked against the current model generation. GTK model reads and expansion
  persistence wait until expansion notifications finish; disappearing child
  rows must not overwrite their saved expansion preferences.
- Owns reusable native menus for servers, groups, local profiles and saved
  workspaces. Each dispatch revalidates the captured object ID and permissions;
  menu construction no longer supplies generic custom rows to other mixins.

### `ConnectionHistoryDialog`

- Composed explicitly with a GTK parent, `ConnectionHistoryPresenter`, a
  translation callback, history-clearing callback, writable-action callback,
  and toast callback; it does not receive `TermiaWindow`.
- Cross-mixin dependencies: none.
- `ConnectionHistoryPresenter` owns filtering and display formatting, while
  `ConnectionHistoryDialog` owns GTK dialog and row construction.

### `StatisticsDialog`

- Composed explicitly with a GTK parent, `StatisticsPresenter`, and
  translation callback; it does not receive `TermiaWindow`.
- Cross-mixin dependencies: none.
- `StatisticsPresenter` owns card metrics, duration formatting, current-run
  values, and server ranking. `StatisticsDialog` owns only GTK dialog and
  widget construction.

### `NotesDialogs`

- Composed with the parent window, `ConnectionStore`, `NotesPresenter`, a
  translation callback, writable guard, error callback, and toast callback.
- Owns the reusable modeless notes/category windows and import/export flows;
  it does not inherit `TermiaWindow` or manage terminal sessions.
- `NotesPresenter` owns the personal/server/category tree, search filtering,
  server labels, and note ordering; `ConnectionStore` owns note persistence and
  per-scope category rules. `NotesDialogs` owns tree expansion, creation scope,
  and tab identity.

### `TerminalMenusMixin`

- Reads: `store` and the explicitly composed `TerminalMenuActions` callback
  set.
- Window services: translation and the session registry for target validation.
- Owns one reusable native context menu per owning window, including native
  Split and Tab submenu models. Commands retain the clicked session and pane;
  their lifetime and owning window are checked before deferred dispatch.
  A shared pointer-leave controller closes the nested child and refreshes the
  root menu so its outside-click dismissal and terminal input remain active.
- Cross-mixin dependencies: none for action dispatch; session splitting and
  disconnection, file transfer, tab operations, terminal copy/paste,
  preferences, status visibility, and statistics are supplied as callbacks.
- Extracted component: `TerminalMenuActions` defines the actions supplied by
  the application composition root. The menu builder no longer discovers these
  feature callbacks on the window.

### `TerminalSessionsMixin`

- Each `TerminalPane` owns its Termia UI handler IDs through `SignalConnections`,
  using native weak emitter references. Retiring a tab or removing a pane
  disconnects those UI handlers; its separately owned `child-exited` handler
  survives a live child and is released only after final history/accounting.
  A retained disconnected/reconnect pane keeps its interactions until retired.
- Tab labels similarly own their interaction handlers. Detaching/reparenting
  does not retire a session; final tab closure does. GTK internal handlers and
  captured process identities are not disposed through the UI signal owner.
- New split terminals receive focus only after mapping. Their pane owns the
  pending map handler, so retirement cancels it before a never-mapped split can
  leave GTK weak focus pointers referring into a destroyed paned container.
- Reads: `store`, `session_registry`, `toast_label`, terminal-menu
  callbacks, and terminal-font resolution.
- Writes: `TerminalSession` objects held in `session_registry`. Each session owns
  explicit `TerminalPane` state for every VTE pane, including its connection
  identity, managed process, status widgets, reconnect state, history, and
  statistics timing.
- Cross-mixin dependencies: tab creation, ordering, activation, title updates,
  closing, terminal menus, and terminal preferences. Tab-triggered duplication,
  disconnection, confirmation, and split cleanup are exposed through the
  explicitly composed `TabLifecycleActions` contract.
- Optional-tool boundary: connection start, pane finish, immediate flush, and
  shutdown are delivered to `session_observer`; the disabled implementation is
  a no-op. SFTP launch is delegated to the bundled SFTP tool through optional
  menu actions rather than implemented in this mixin.
- Architectural note: process launching, terminal views, split panes, and file
  transfer are already delegated to focused modules, but lifecycle
  orchestration still depends directly on tab and window state. Terminal
  actions resolve the pane that opened the context menu instead of assuming the
  tab's original connection identity.

### `TabsMixin`

- A single native `Gtk.PopoverMenu` owns the overflow actions; callbacks hold
  weak host/popover references. Its `show` callback refreshes the model only
  when entries changed, and updates active selection. Invalidating stale UI
  dismisses an open menu without rebuilding it.
- Reads: `store`, `session_registry`, `tab_lifecycle_actions`, `terminal_stack`,
  `session_tab_bar`, `session_tab_scroller` and `session_tab_controls`.
- Writes: drag state and the GTK placement of session pages and labels.
- `visible_terminal_page()` resolves the stack's visible child. Label order in
  `session_tab_bar` defines keyboard navigation, workspace snapshots and
  close-neighbor selection. Termia owns tab selection and private drag
  reordering; GTK owns scrolling and the native overflow menu interaction.
- Drag motion changes label placement without refreshing the overflow menu.
  Drag end compares initial and final order and invalidates only a changed
  order. A bounded edge-scroll timer revalidates the drag and stops on leave,
  drop, drag end, removal or shutdown. Deferred active-tab reveal is suppressed
  during drag. Async drops revalidate payload, session and shutdown state.
- The drag source uses `Gtk.WidgetPaintable` for its icon. The source tab uses
  scoped dragging color and opacity; no notebook-specific preview is created.
- Cross-mixin dependencies: terminal context actions and shared dialog helpers.
  Terminal creation, confirmation, disconnection, and split-process cleanup
  are supplied explicitly through `TabLifecycleActions`.
- Architectural note: terminal sessions still create and close tabs through
  `TabsMixin`, but tab management no longer discovers terminal lifecycle
  methods implicitly on the composed window.

## Dependency hotspots

### Update boundary

- `update_service.py` owns immutable release/version models, release-channel
  policy and bounded HTTPS downloads. It imports neither GTK nor installers.
- `update_installers.py` defines the `Installer` protocol and Git/Debian
  adapters. `availability` explains restrictions, `prepare` stages a verified
  artifact, `dependencies` returns a declarative plan, and `apply` finishes the
  confirmed transaction. `update_dependencies.py` parses bounded runtime
  relationships, checks package versions and fresh interpreter bindings, and
  builds native APT arguments/manual commands without executing target scripts.
  Adapters never receive widgets, terminal sessions or connection stores.
- `update_controller.py` serializes work, owns the cross-profile process lock
  and temporary directory, and dispatches callbacks through an injected function.
  Staging and application are separate jobs. Manual dependency mode retains
  staging and waits for rechecks without holding the process lock; each worker
  reacquires it and revalidates the target. Closing suppresses queued callbacks
  and cancels preparation; an application transaction retains a non-daemon worker
  until the installer exits. Final success requires dependency verification and,
  for Debian, confirmation of the installed package version.
  Installer `set_output` callbacks carry only plain text, never widgets. Verbose
  APT/Git operations stream stdout/stderr without retaining the complete output;
  commands used to parse metadata keep their stdout-only return contract.
  `update_output.py` removes terminal controls and URLs from complete, bounded
  lines. The controller coalesces output into one queued callback and a 65,536
  character tail; a closed view receives no pending output. Authentication
  remains owned by the desktop agent, not by this stream.
- `update_view.py` adds one header-bar action to About using public GTK APIs and
  owns the update/confirmation dialogs. It receives only a GTK parent and a
  translator. It changes no terminal CSS, geometry, keyboard dispatch or storage.
  Its read-only `Gtk.TextView` log retains the same bounded tail, supports copy,
  and clears on a new check; receiving output must not end the busy state.
- To add another installation format, implement `Installer` and extend detection;
  keep release selection and widgets independent. Release APIs can be replaced
  through the injected client; tests inject clients/adapters without installing.

### SFTP boundary

- `sftp_service.py` defines immutable endpoint/entry data, typed authentication
  events and the `SFTPBackend` protocol without GTK or Paramiko dependencies.
- `SFTPService` serializes work off the GTK thread. Its injected dispatcher
  delivers results on the UI loop and suppresses queued callbacks after closure.
- `sftp_backend.py` implements that protocol using Paramiko. It owns the SSH
  transport, known-host verification, bounded I/O, and explicit file operations.
  It never executes shell commands, mounts paths or receives GTK widgets.
- `sftp_view.py` owns the independent window, prompts and selection state;
  tests can inject a backend. New backends must implement the service contract
  and translate authentication errors to its typed events.
- `ManagedTransfer` provides the common lifecycle contract with existing SCP.
  Session-owned explorers are closed through the existing tab/application
  transfer cleanup. Sidebar-owned explorers have no terminal session owner.
- The initial adapter uses saved endpoint fields rather than OpenSSH config
  interpretation. SFTP credentials are never persisted. Backend replacement,
  remote editing or transfer queues must not alter terminal layout or styling.

The principal dependency hotspots are:

1. `TerminalSessionsMixin` still creates and closes tabs through `TabsMixin`;
   the former reverse dependency now uses the explicit `TabLifecycleActions`
   callback contract.
2. `TerminalMenusMixin` dispatches actions to both tabs and terminal sessions,
   while terminal sessions install the menu callback on each VTE widget.
3. `SidebarMixin` opens sessions and dialogs, while configuration and
   preference changes call back into sidebar refresh and selection state.

## Recommended extraction order

1. Define a small host interface for translation, feedback, writability, and
   dialog parenting.
2. Use the extracted `StatisticsDialog` and the history presenter as the
   pattern for subsequent extractions with explicit providers and callbacks.
3. Pass explicit action callbacks into menu builders. The main menu uses
   `MainMenuActions` and terminal context menus use `TerminalMenuActions`.
4. `SessionRegistry` owns open terminal sessions and their lookup for tab and
   lifecycle code.
5. `TabLifecycleActions` separates tab placement from terminal lifecycle
   operations. The next step is to replace `TabsMixin` with an explicitly
   composed tab controller.
6. Replace the remaining session and sidebar mixins after their state has a
   single explicit owner.

New components should not accept the complete `TermiaWindow` object when a
store, translator, callback, or GTK parent is sufficient.
