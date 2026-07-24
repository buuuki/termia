# Changelog

## Unreleased

Changes merged after `0.5.0-beta` (2026-07-21 to 2026-07-23).

### Added

- Add an opt-in Debug mode in General preferences and a `--debug` launcher option for GTK/VTE rendering, storage-lock, encryption, and read-only diagnostics.
- Add a keyboard shortcut to focus the server filter (`#96`).
- Add keyboard navigation shortcuts for the sidebar and tabs (`#98`, `#100`).
- Add a safety confirmation before starting large server groups (`#90`).
- Allow creating subgroups from the group context menu (`#92`).

### Fixed

- Reset the main menu to its top-level view after closing the Import/Export submenu.
- Re-enable write-capable sidebar actions after encrypted connections are successfully unlocked.
- Keep the Debug mode checkbox enabled in General preferences when password shortcut options are present.
- Refresh write actions after encrypted connections are unlocked so preferences and configuration actions are not left disabled.

### Changed

- Document the supported Python, GTK, GDK, and VTE runtime baseline and retained compatibility guards.
- Rename the saved-password shortcut settings to avoid implying that Termia executes `sudo`.
- Unify the setup commands and dependency checks (`#94`).
- Synchronize translation catalogs and add automated catalog consistency validation (`#102`).

### Refactored

- Pass main-menu feature actions through an explicit callback contract composed by the application window.
- Extract statistics dashboard metrics and ranking into an explicitly injected, GTK-independent presenter.
- Extract connection-history filtering and display formatting into an explicitly injected, GTK-independent presenter.
- Document the state, services, cross-mixin calls, and dependency hotspots that make up the current `TermiaWindow` mixin contracts.
- Introduce explicit schema versioning and named migrations for connections, settings, statistics, and history files.
- Establish an automated unit-test and GTK smoke-test baseline (`#104`).
- Simplify sidebar row state and introduce a normalized sidebar projection (`#106`, `#116`).
- Make history persistence injectable and expose history recovery messages (`#108`).
- Extract SCP file transfers, terminal command/process helpers, split panes, terminal views, and preference sections into focused components (`#110`, `#112`, `#114`, `#118`, `#121`).

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
