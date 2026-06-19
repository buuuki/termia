# Changelog

## 0.3.0-alpha.1 - 2026-06-19

### Changed

- Start new installations with the session status bar hidden by default.
- Use JetBrains Mono with the Polaris terminal palette by default.
- Use a white local prompt color by default.
- Refactor terminal session setup to share terminal, status bar, and page construction across local, SSH, and split terminals.
- Simplify app settings persistence by passing an `AppSettings` object instead of a long list of positional booleans.

### Removed

- Remove placeholder update methods and unused state/imports that did not affect runtime behavior.
