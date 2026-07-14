# Changelog

## Unreleased

### Changed

- Translate app theme choices.
- Close split tabs when the final pane exits.
- Add favorite servers section and favorite toggle in the server editor.
- Add keyboard navigation for filtered sidebar servers.
- Fix terminal function key handling.
- Fix terminal menu separator color in split panes.
- Rename the Spanish language label.
- Add gettext-backed translations and bump the project version to `0.4.0-alpha`.

### Added

- Add server file upload via SCP.
- Add manual terminal keybinding capture.
- Add a Recent sidebar section with the 10 most recently connected servers, deduplicated and ordered from connection history.
- Add a JSONL connection history view and local history log.
- Add a toggle to hide local terminal entries in the connection history view.

## 0.3.0-alpha.1 - 2026-06-19

### Changed

- Start new installations with the session status bar hidden by default.
- Use JetBrains Mono with the Polaris terminal palette by default.
- Use a white local prompt color by default.
- Refactor terminal session setup to share terminal, status bar, and page construction across local, SSH, and split terminals.
- Simplify app settings persistence by passing an `AppSettings` object instead of a long list of positional booleans.

### Removed

- Remove placeholder update methods and unused state/imports that did not affect runtime behavior.
