# Regression Checks and Protected Behaviors

This document lists Termia behaviors that should be preserved during code changes. A change may intentionally modify one of these behaviors, but the impact must be explicit, reviewed, and documented.

## Change Policy

When a requested change touches a protected behavior:

- Prefer an implementation that preserves the existing behavior.
- If preserving it is not possible, explain the tradeoff before changing it.
- If the behavior must change intentionally, update this document and the user-facing documentation if needed.
- Before completing the change, run the automated checks and manually verify the affected behavior.

Protected behavior does not mean the code cannot change. It means regressions should not happen silently.

## Protected Behaviors

### Project License

- Termia must remain licensed as GNU GPL-3.0-or-later unless the project owner explicitly requests a license change.
- The `LICENSE` file, README license section, About dialog license metadata, and third-party notices must stay consistent with the GPL project license.
- New project-owned assets, including bundled icons, must use the same GPL project license unless a different compatible license is explicitly documented.

### Main Toolbar Icons

- Main toolbar action icons are protected UI decisions and must not be changed without explicit user approval.
- The local/new terminal tab action icon and sidebar toggle icon must remain stable unless a change is requested directly.
- If a toolbar icon is changed intentionally, document the previous icon name, new icon name, and reason in the commit message or related issue.

### Tabs

- Connection and local terminal tabs must remain visibly and reliably reorderable with left-button drag in the custom tab bar.
- Left-clicking a tab title must select that session without stealing focus from the terminal after selection.
- Drag logic must keep tab order, Ctrl+PageUp/Ctrl+PageDown navigation, and close-next-focus behavior aligned with the visual tab order.
- Right-click tab actions must keep working: duplicate, detach, and rename.
- The close button must only close the intended tab and must not make accidental closure too easy.
- Closing a tab must focus the terminal in the next active tab when one exists.
- Detached tabs must be restorable to the main window when their detached window closes.
- Duplicating an SSH tab must open a new SSH connection to the same server.
- Duplicating a local terminal tab must use the same local-terminal startup path as opening a new local terminal, including prompt settings.

### Terminal Sessions

- Local terminals must start in the user's home directory unless a future setting explicitly changes it.
- Local terminal prompt customization must apply to newly opened and duplicated local terminals.
- SSH sessions must not send arbitrary commands automatically to remote servers.
- SSH fingerprint prompts must remain visible and interactive in the terminal.
- Failed SSH connections must leave the tab usable and show the reconnect prompt.
- The reconnect prompt must be readable on both light and dark terminal backgrounds.
- Pressing Enter on a failed SSH tab must reconnect to the same server.
- Exiting an SSH session with `exit` must only close the tab when the relevant preference is enabled.
- Exiting a local shell must follow the configured local terminal close behavior.

### Focus and Keyboard

- `Ctrl+PageUp` and `Ctrl+PageDown` must switch between tabs.
- After keyboard tab switching, focus must return to the terminal, not the tab label.
- After closing a session, focus must move to the active terminal automatically.
- Terminal shortcuts such as font size increase/decrease must not break normal terminal input unexpectedly.

### Context Menus and Popovers

- Right-click on servers, groups, terminals, and tabs must show context menus at the expected location.
- Opening dialogs from popovers must close or defer the popover first to avoid GTK grabbing-popup hangs.
- Context menus must not cause sidebar scroll jumps or horizontal scroll movement.
- Context menu actions must operate on the selected/right-clicked item, not a stale selection.

### Server Tree

- Groups and subgroups must preserve expanded/collapsed state when editing servers or refreshing the list.
- The server tree must not jump to the top when selecting or right-clicking entries.
- Filtering must include matching servers, groups, and subgroups.
- Group server counts must include servers inside subgroups.
- Servers should display only their name in the tree, with connection details in the tooltip.

### Configuration and Data

- Existing combined `connections.json` files must remain loadable and migrate app/terminal settings into `settings.json` without losing groups, servers, or preferences.
- New plain `connections.json` writes must contain only groups and servers; app and terminal preferences must be written to `settings.json`.
- Obfuscated connection storage must decode back to the same groups, servers, passwords, and private key paths, and switching modes must rewrite the file immediately.
- Import/export configuration must preserve groups, subgroups, servers, SSH user, port, host, password, and private key path where available.
- Importing Asbru configuration must not add unwanted suffixes such as `- copy`.
- Clearing configuration must require confirmation.
- Passwords are currently stored in the JSON file by explicit project decision; warnings and documentation must remain accurate until storage changes.

### Application Appearance and Themes

- Configured application colors and theme styling must remain consistent after UI changes.
- Header bar, main menu, configuration menu, statistics menu, popovers, sidebars, tabs, buttons, selected rows, warning text, and dialogs must remain readable in light, dark, system, and any custom app themes.
- Tab colors, borders, spacing, close button contrast, selected tab state, and hover/active states must remain visually clear.
- Context menus and popovers must use readable foreground/background colors and must not inherit terminal colors.
- Sidebar group/server selection colors must remain readable and must preserve the distinction between folders/groups and server entries.
- New CSS rules must be scoped to Termia classes where practical and must not unintentionally override GTK/VTE internals.

### Terminal Appearance

- Terminal foreground, background, font, font size, ANSI palette, and prompt settings must apply to new terminal sessions.
- Terminal foreground/background color changes must not affect app menus, header bars, sidebars, dialogs, or tab chrome.
- Terminal palette changes must preserve readable ANSI colors for common output such as directories, executables, warnings, errors, and prompts.
- Reconnect and warning messages printed inside VTE must remain readable on both light and dark terminal backgrounds.
- Prompt color customization must remain visible with the configured terminal background.
- Font size shortcuts must update existing open terminals.
- LS color customization must continue to reduce overly bright directory/file colors.
- Tab labels should show short and medium names without unnecessary truncation, and provide a tooltip with the full title.

### Statistics

- Statistics collection must remain lightweight and should not continuously write to disk on every keypress.
- Statistics must be disabled by default and must not record command or keystroke counters, even when enabled.
- Disabling statistics from General preferences must stop new aggregate connection and duration counters from being recorded or flushed.
- Global and current-run connection counters must remain separate.
- Per-session statistics must correspond to the selected terminal session.

## Manual Regression Checklist

Before merging changes that touch UI, terminals, tabs, or configuration, verify:

- Open Termia and confirm a local terminal opens if the preference is enabled.
- Open two local terminals and reorder their tabs with the mouse.
- Duplicate a local terminal and confirm the custom prompt is applied.
- Open two SSH sessions and duplicate one of them.
- Close a tab and confirm focus moves to the next terminal.
- Right-click a terminal and open the context menu.
- Right-click a server/group in the tree and open the context menu.
- Edit a server and confirm collapsed groups stay collapsed.
- Search for a group, subgroup, and server in the sidebar filter.
- Open Preferences from Configuration and confirm the app does not hang.
- Switch between available app themes and confirm header, menus, sidebars, dialogs, selected rows, and tabs remain readable.
- Change terminal foreground/background/palette and confirm only VTE terminal colors change, not the app chrome.
- Confirm terminal ANSI colors, prompt colors, and the reconnect prompt are readable on both light and dark terminal backgrounds.

## Automated Checks

Run at minimum:

```bash
python3 -m py_compile run_termia.py src/termia/app.py src/termia/asbru_import.py src/termia/config_actions.py src/termia/config_io.py src/termia/connection_dialogs.py src/termia/connection_utils.py src/termia/constants.py src/termia/i18n.py src/termia/main_menu.py src/termia/models.py src/termia/preferences.py src/termia/sidebar.py src/termia/statistics_utils.py src/termia/statistics_view.py src/termia/stores.py src/termia/styles.py src/termia/tabs.py src/termia/terminal_sessions.py src/termia/terminal_config.py src/termia/ui_state.py
bash -n scripts/install_dependencies.sh
bash -n scripts/install_desktop.sh
bash -n scripts/uninstall_desktop.sh
```

When practical, add targeted tests for pure logic such as prompt templates, config migration, import/export, and statistics.
