# Changelog

## Unreleased

Changes merged after `0.5.0-beta.3` (released 2026-07-30).

### Added

- Add severity icons to in-app information, success, warning, and error notifications.
- Add configurable `Ctrl+Arrow` keybindings for directional focus navigation
  between local and SSH split panes, with a scrollable shortcut editor (`#218`).
- Preserve custom tab titles and per-pane local working directories in saved
  workspaces, with safe fallback for unavailable paths and no SSH path capture
  (`#214`).
- Add a terminal preference to enable or disable the audible bell, disabled by
  default (`#207`).
- Restore the previous tabs and split layouts on startup after explicit user
  confirmation, using a private snapshot containing only saved connection
  references (`#184`).
- Add a General preference to enable previous-session restoration, disabled by
  default (`#184`).

### Fixed

- Preserve ancestor divider positions and split only the selected pane 50/50
  when adding a terminal to an existing nested layout.
- Avoid showing the same SSH disconnected notification twice when closing an
  active tab.
- Treat managed terminal exits during application shutdown as intentional,
  suppress reconnect notifications, and avoid duplicate forced termination
  requests (`#233`).
- Inspect SSH known-host files asynchronously so connection and SCP startup
  cannot block the GTK interface while `ssh-keygen -F` runs (`#230`).
- Bind session-specific dialogs, confirmations, terminal preferences, and SCP
  flows to the detached window that initiated them (`#226`).
- Keep a detached window's native and header titles synchronized when its tab
  is renamed, and bind the rename dialog input to that window (`#224`).
- Transfer focus safely before collapsing nested split layouts so closing a
  pane does not leave stale `GtkPaned` focus state (`#219`).
- Prevent Enter in the server filter from reopening a stale selection that is
  absent from the current search results (`#216`).
- Create detached sessions as normal application windows instead of transient
  windows so GTK exposes native minimize, maximize, and close controls while
  preserving tab restoration on close (`#209`).
- Show the tab overflow selector only when the visible tab titles exceed the
  available tab-strip width (`#211`).
- Apply the audible-bell preference through the supported VTE API and expose it
  independently in General preferences (`#207`).
- Apply audible-bell changes immediately to already open terminal panes after
  saving General preferences (`#207`).

### Changed

- Expand split regression coverage across progressive one-to-four-pane layouts,
  every insertion direction, odd sizes, and deferred GTK allocation (`#243`).
- Define `0.6.0-beta.1` as a stabilization checkpoint, prioritize SCP maturity
  before the first stable release, and allow stable pre-1.0 releases while
  reserving `1.0.0` for the long-term compatibility milestone.
- Make closing a detached window close its session, and provide an explicit
  action to reattach the live session to the main window (`#228`).
- Make debug logging focus on privacy-safe Termia lifecycle events, retain
  actionable GTK warnings, and capture Python stacks on fatal signals (`#221`).
- Unify Terminal appearance and local Prompt preferences in one dialog with a
  compact shared live preview, while preserving running shell environments (`#205`).
- Streamline repository maintenance guidance and validation output while
  preserving required test coverage (`#200`).

### Fixed

- Group concurrent application notifications so later events do not hide
  earlier feedback, and report every changed General preference without
  emitting messages for unchanged settings (`#203`).
- Align header and sidebar action buttons, clarify their creation tooltips, and
  mark local-terminal profile creation with a terminal-plus icon (`#197`).
- Enforce a 32-pane total workspace limit without prompting for valid
  workspaces (`#192`).
- Keep the split-connection search dialog open when Enter is pressed without a
  matching saved connection (`#191`).
- Show the startup master-password prompt as a modal layer inside the Termia
  window so it cannot appear on a different monitor, while keeping the locked
  window movable through its header bar (`#182`).
- Preserve split-divider positions when showing or hiding a pane status bar
  and allow status labels to ellipsize instead of forcing pane width (`#189`).

### Added

- Keep up to 40 terminal tabs reachable at normal window widths with a compact
  horizontal overflow strip, automatic active-tab reveal, and a complete tab
  selector (`#199`).
- Limit open terminal tabs globally to 40, including detached tabs; reject
  oversized workspace or group batches before starting processes, and show
  application notifications through a visible temporary overlay (`#195`).
- Save named multi-server workspaces from the sidebar and reopen their tabs,
  independent SSH/local split panes, and split layout safely (`#185`).
- Search saved SSH and local-terminal profiles by keyboard when opening a
  connection in a split (`#187`).

## 0.5.0-beta.3 - 2026-07-30

Changes merged after `0.5.0-beta.2` (released 2026-07-29).

### Fixed

- Toggle the selected pane's session status bar from the terminal context menu
  with translated show and hide actions (`#178`).
- Show a `Close` action automatically for failed panes awaiting reconnection,
  allow them to be removed without retrying, and keep split separators narrow
  when pane status bars are visible (`#174`).
- Preserve translated action tooltips for writable sidebar icon buttons while
  retaining read-only and locked-connection explanations when disabled
  (`#170`).
- Open the configured startup local terminal after cancelling encrypted
  connection unlocking, including in read-only instances (`#172`).

### Added

- Allow split panes in the same tab to connect independently to different
  saved SSH servers or local terminal profiles, with pane-specific status,
  actions, history, statistics, reconnect state, and process cleanup (`#174`).

### Changed

- Synchronize the Spanish and Catalan feature documentation for independent
  split-pane connections (`#176`).

## 0.5.0-beta.2 - 2026-07-29

Changes merged after `0.5.0-beta` (released 2026-07-20).

### Added

- Add Debian packaging metadata, a downloadable `.deb`, and Pyproject build support to install Termia on Ubuntu 24.04 or newer with its desktop icon (`#155`).
- Close tabs with a middle mouse click (`#141`).
- Add an opt-in Debug mode in General preferences and a `--debug` launcher option for GTK/VTE rendering, storage-lock, encryption, and read-only diagnostics (`#125`).
- Add a keyboard shortcut to focus the server filter (`#95`).
- Add keyboard navigation shortcuts for the sidebar and tabs (`#97`, `#99`).
- Add a safety confirmation before starting large server groups (`#89`).
- Allow creating subgroups from the group context menu (`#91`).

### Fixed

- Stop Debug mode from enabling GSK renderer frame statistics that flood the system log, and format structured GLib diagnostics as readable text (`#162`).
- Finalize stale connection-history entries from an earlier Termia process as interrupted instead of leaving them in progress (`#151`).
- Terminate isolated VTE process groups when disconnecting sessions or closing Termia to avoid orphaned terminal and SSH children (`#148`).
- Keep Debug output in Termia's state log instead of forwarding it to stderr/syslog, and show its path in the Debug preference tooltip (`#135`).
- Fix moving a tab to a new window by preserving the previous tab order when selecting the next focused session (`#137`).
- Reset the main menu to its top-level view after closing the Import/Export submenu (`#134`).
- Re-enable write-capable sidebar actions after encrypted connections are successfully unlocked.
- Keep the Debug mode checkbox enabled in General preferences when password shortcut options are present.
- Refresh write actions after encrypted connections are unlocked so preferences and configuration actions are not left disabled.

### Changed

- Define a consistent Termia prerelease and Debian package revision policy (`#166`).
- Add persistent multi-connection session workspaces to the planned roadmap (`#164`).
- Reorder the README feature and setup sections to highlight embedded terminals, split workspaces, SCP uploads, encrypted storage, and quick-start instructions.
- Add and promote an optimized Termia screenshot across the main README, localized documentation, and roadmap.
- Make isolated test profiles clone the current Termia history, statistics, and debug log along with configuration.
- Document the required managed-process cleanup behavior for future VTE features.
- Document the supported Python, GTK, GDK, and VTE runtime baseline and retained compatibility guards.
- Rename the saved-password shortcut settings to avoid implying that Termia executes `sudo`.
- Unify the setup commands and dependency checks (`#93`).
- Synchronize translation catalogs and add automated catalog consistency validation (`#101`).

### Refactored

- Pass tab-triggered terminal lifecycle operations through an explicit callback contract (`#158`).
- Introduce an explicit terminal session registry instead of sharing the `open_tabs` dictionary between window mixins (`#156`).
- Replace the connection history view mixin with an explicitly composed dialog.
- Replace the statistics view mixin with an explicitly composed statistics dialog.
- Pass terminal context-menu actions through an explicit callback contract composed by the application window (`#139`).
- Pass main-menu feature actions through an explicit callback contract composed by the application window (`#132`).
- Extract statistics dashboard metrics and ranking into an explicitly injected, GTK-independent presenter.
- Extract connection-history filtering and display formatting into an explicitly injected, GTK-independent presenter.
- Document the state, services, cross-mixin calls, and dependency hotspots that make up the current `TermiaWindow` mixin contracts.
- Introduce explicit schema versioning and named migrations for connections, settings, statistics, and history files (`#122`).
- Establish an automated unit-test and GTK smoke-test baseline (`#103`).
- Simplify sidebar row state and introduce a normalized sidebar projection (`#105`, `#115`).
- Make history persistence injectable and expose history recovery messages (`#107`).
- Extract SCP file transfers, terminal command/process helpers, split panes, terminal views, and preference sections into focused components (`#109`, `#111`, `#113`, `#117`, `#119`).

## 0.5.0-beta - 2026-07-20

### Added

- Add encrypted connection storage protected by a master password (`#84`).
- Show the locations of Termia's data files from the application menu (`#88`).
- Add a connection history view with JSONL persistence and a Recent sidebar section (`#61`, `#62`).
- Add configurable local terminal profiles, split-layout presets, and local terminal profile cloning (`#64`, `#67`, `#68`).
- Import saved passwords from Ásbrú YAML (`#72`).
- Add favorites to the sidebar and server editor (`#55`).

### Changed

- Bump the application version to `0.5.0-beta` and update the beta-exit roadmap (`#80`, `#82`).
- Customize split separator styling and keep split tabs active while panes remain (`#74`, `#76`).
- Improve terminal context-menu handling and defer menu callbacks safely after popovers close (`#70`, `#74`).
- Focus the previous tab after closing the current tab (`#78`).
- Translate application theme choices and improve multilingual UI coverage (`#52`, `#55`, `#59`).

### Fixed

- Keep the split separator color valid after configuration changes (`#86`).
- Close a split tab after its final pane exits (`#57`).

## 0.4.0-alpha - 2026-06-29

### Added

- Add manual terminal keybinding capture (`#49`).
- Add server file upload via SCP (`#51`).

### Changed

- Migrate UI translations to gettext and bump the application version to `0.4.0-alpha` (`#52`).
- Rename the Spanish language label (`#52`).

### Fixed

- Fix terminal menu separator colors in split panes (`#52`).
- Fix terminal function-key handling (`#52`).

## 0.3.0-alpha.1 - 2026-06-19

### Changed

- Start new installations with the session status bar hidden by default.
- Use JetBrains Mono with the Polaris terminal palette by default.
- Use a white local prompt color by default.
- Add a start-group context action (`#44`).
- Allow secondary Termia instances to run in read-only mode (`#41`).
- Refactor terminal session setup to share terminal, status-bar, and page construction across local, SSH, and split terminals.
- Simplify app settings persistence by passing an `AppSettings` object instead of positional booleans.

### Fixed

- Fix tab closing when split panes remain after a terminal exits (`#43`).
- Refine split separator styling.

### Removed

- Remove placeholder update methods and unused state/imports that did not affect runtime behavior.

## 0.2.0-alpha.1 - 2026-06-14

### Added

- Initial Termia SSH connection manager with server groups, local terminals, tabs, and embedded VTE terminals.
- Add configurable terminal keybindings and terminal tab actions (`#15`, `#26`, `#35`).
- Add terminal split panes (`#37`).
- Add separate application settings storage and configurable connection-storage security options (`#17`, `#19`).
- Add optional local statistics and disable statistics by default (`#21`, `#23`).
- Add system-language detection and English, Spanish, and Catalan documentation.
- Add SSH reconnect prompts, close-on-exit preferences, startup sidebar settings, and server-tree navigation.

### Changed

- Improve terminal font, prompt, tab, sidebar, statistics, and embedded-terminal UI.
- Preserve server-tree expansion state and support group-name searching.
- Improve dependency checks and installation diagnostics.
- Switch the project license to GPL-3.0-or-later.

### Fixed

- Fix recursive group deletion and server validation (`#5`, `#7`).

### Refactored

- Split the application into focused models, stores, helpers, views, and window mixins to establish the current architecture.

## Initial development - 2026-06-03 to 2026-06-13

- Publish the initial Termia release and establish the source-checkout launcher, dependency checks, documentation, and issue templates.
