# TermiaWindow mixin contracts

This document records the implicit contract between `TermiaWindow` and its
mixins. It is an inventory of the current architecture, not a requirement that
new components inherit from the window.

The purpose of the inventory is to make dependencies visible before mixins are
replaced gradually with explicit controllers and services.

## Shared window services

Most mixins expect the window to provide some combination of these services:

- `store`: the `ConnectionStore` and its app, terminal, connection, history,
  and statistics data.
- `t(key)`: translation using the language stored in `store`.
- `toast_label`: shared status and error feedback.
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
- Session state: `open_tabs`, `run_connections`, `stats_save_id`.
- Sidebar selection: `selected`, `selected_tree_widget`,
  `group_expanded_state`, `collapse_groups_on_startup`, `tree_widgets`, and
  `active_context_popover`.
- Main UI widgets: `body`, `sidebar`, `search_entry`, `server_list`,
  `server_scroller`, `summary_label`, `title_label`, `info_label`,
  `session_tab_bar`, and `terminal_stack`.
- Header widgets: sidebar, new-tab, menu, read-only, add, expand, and collapse
  controls.

Some mixins add transient state after construction:

- `SidebarMixin`: `group_expanders`, `sidebar_projection`,
  `visible_tree_rows`, `scroll_restore_id`, `sidebar_visible`, and
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

- Reads: no data widgets beyond the window services; it wires callbacks from
  nearly every feature area.
- Window services: translation and writable-action configuration.
- Cross-mixin dependencies: configuration actions, all preference dialogs,
  history, statistics, and the shared dialog-button helpers it defines.
- Architectural note: it is a composition boundary and should receive action
  callbacks explicitly instead of discovering methods on the window.

### Preference mixins

`PreferencesMixin` only combines the five focused preference mixins.

- `GeneralPreferencesMixin` reads `store` and `toast_label`; it updates sidebar
  expansion state and calls theme, sidebar, session-status, translation, and
  list-refresh methods.
- `TerminalPreferencesMixin` reads `store` and `toast_label`; it needs Pango
  font information, tree-style refresh, and application of terminal settings
  to open sessions.
- `PromptPreferencesMixin` reads `store` and `toast_label`; it otherwise needs
  only translation, the writable guard, and dialog helpers.
- `SecurityPreferencesMixin` reads `store` and `toast_label`; it otherwise
  needs translation, the writable guard, and dialog helpers.
- `KeybindingPreferencesMixin` reads `store` and `toast_label`; it otherwise
  needs translation, the writable guard, and dialog helpers.

The general and terminal dialogs have cross-feature side effects. Prompt,
security, and keybinding dialogs have comparatively small contracts.

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

### `ConnectionHistoryViewMixin`

- Reads: `store`, `toast_label`, and the explicitly composed
  `history_presenter`.
- Window services: translation, dialog buttons, and writable-action
  configuration.
- Cross-mixin dependencies: none beyond those common services.
- Extracted component: `ConnectionHistoryPresenter` owns filtering and display
  formatting. It receives only an entries provider and translation callback;
  the mixin retains GTK dialog and row construction.

### `StatisticsViewMixin`

- Reads: the explicitly composed `statistics_presenter`.
- Window services: translation and dialog buttons.
- Cross-mixin dependencies: none beyond those common services.
- Extracted component: `StatisticsPresenter` owns card metrics, duration
  formatting, current-run values, and server ranking. It receives statistics,
  servers, current-run, and translation providers; the mixin retains GTK
  widget construction.

### `TerminalMenusMixin`

- Reads: `store`.
- Window services: translation and context-menu construction.
- Cross-mixin dependencies: session splitting and disconnection, file
  transfer, tab duplication/renaming/closing, terminal copy/paste, preferences,
  status visibility, and statistics.
- Architectural note: like the main menu, it should eventually receive an
  explicit set of actions.

### `TerminalSessionsMixin`

- Reads: `store`, `open_tabs`, `terminal_stack`, `toast_label`, terminal-menu
  callbacks, and terminal-font resolution.
- Writes: `run_connections` and `stats_save_id`; it also mutates
  `TerminalSession` objects held in `open_tabs`.
- Cross-mixin dependencies: tab creation, ordering, activation, title updates,
  closing, terminal menus, and terminal preferences.
- Architectural note: process launching, terminal views, split panes, and file
  transfer are already delegated to focused modules, but lifecycle
  orchestration still depends directly on tab and window state.

### `TabsMixin`

- Reads: `store`, `open_tabs`, `session_tab_bar`, and `terminal_stack`.
- Writes: drag state and the GTK placement of session pages and labels.
- Cross-mixin dependencies: terminal creation/disconnection/termination,
  terminal context actions, and shared dialog helpers.
- Architectural note: the circular dependency between tabs and terminal
  sessions is the most important contract to break before either mixin can be
  replaced.

## Dependency hotspots

The principal cycles are:

1. `TerminalSessionsMixin` creates and closes tabs through `TabsMixin`, while
   `TabsMixin` starts, disconnects, and terminates sessions through
   `TerminalSessionsMixin`.
2. `TerminalMenusMixin` dispatches actions to both tabs and terminal sessions,
   while terminal sessions install the menu callback on each VTE widget.
3. `SidebarMixin` opens sessions and dialogs, while configuration and
   preference changes call back into sidebar refresh and selection state.

## Recommended extraction order

1. Define a small host interface for translation, feedback, writability, and
   dialog parenting.
2. Use the history and statistics presenters as the pattern for subsequent
   extractions with explicit providers and callbacks.
3. Pass explicit action callbacks into main and terminal menu builders.
4. Introduce a session registry that owns `open_tabs` and session lookup.
5. Separate tab placement from session lifecycle using the registry and
   callbacks, then replace `TabsMixin`.
6. Replace the remaining session and sidebar mixins after their state has a
   single explicit owner.

New components should not accept the complete `TermiaWindow` object when a
store, translator, callback, or GTK parent is sufficient.
