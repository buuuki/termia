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
- The global 40-tab limit must count detached tabs and reject individual or
  batched openings before starting any terminal process; closing a tab must
  immediately restore one available slot.
- Application notifications must appear in a visible temporary overlay and
  hide automatically without blocking terminal input.
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
- With the startup local-terminal preference enabled, cancelling the
  encrypted-connections unlock dialog must open exactly one generic local
  terminal in writable and read-only instances; disabling the preference must
  open none, and a successful unlock must not create a duplicate.
- Exiting an SSH session with `exit` must only close the tab when the relevant preference is enabled, and only after the last terminal in the tab has exited with no split panes remaining.
- Exiting a local shell must follow the configured local terminal close behavior.
- Exiting a split shell with `exit` must remove only that split pane and keep sibling panes usable.
- Every split pane must retain its own SSH or local-profile identity, process,
  status bar, reconnect state, history entry, statistics, and context actions.
- Disconnecting one pane must terminate only its managed process; closing the
  tab or Termia must terminate all pane processes.
- Directional split actions must duplicate the selected pane, while `Open
  connection in split…` must allow a different saved SSH or local-terminal
  profile and enforce the 16-pane limit. Its connection selector must filter
  saved SSH and local profiles by their useful details and support `Up`,
  `Down`, and `Enter` from the search field.
- When close-on-exit is enabled, a split tab must close after the last pane exits regardless of whether the original terminal or a split exits last.
- Closing Termia must terminate every process group in the isolated VTE session for active SSH, local-terminal, and split-pane sessions without signalling unrelated processes.

### Focus and Keyboard

- `Ctrl+PageUp` and `Ctrl+PageDown` must switch between tabs.
- After keyboard tab switching, focus must return to the terminal, not the tab label.
- After closing a session, focus must move to the active terminal automatically.
- Terminal shortcuts such as font size increase/decrease must not break normal terminal input unexpectedly.
- `Ctrl+F` must show the server sidebar, focus the server filter, select its current text, and not reach an embedded terminal.
- `Ctrl+Shift+B` must toggle the server sidebar without changing the `Ctrl+F` behavior.
- `F10` must open and close the main menu. Other unmodified function keys, including `F6`, must still reach the embedded terminal.
- `Ctrl+Shift+T` must open a new local terminal without changing the existing tab-navigation shortcuts.
- `Ctrl+F6` and `Ctrl+Shift+F6` must cycle focus forward and backward through the visible server list, tab bar, and active terminal, skipping unavailable regions.
- After selecting a visible server-list item, `Up`, `Down`, `Home`, `End`, and `Enter` must navigate or activate visible groups, servers, favorites, recent servers, and local terminal profiles. Keyboard navigation must scroll just enough to keep the selected item visible. These keys must still reach the VTE while a terminal has focus.
- The selected group, subgroup, or server must use a single consistent sidebar selection highlight; selecting a new item must clear the previous highlight. Starting navigation from the server filter must focus the selected row, GTK expander focus must not create a second selector, and `Up` must never leave the list for the sidebar action buttons while an earlier visible row exists. GTK must automatically scroll the focused row into view, while terminal focus must keep sidebar navigation disabled.

### Context Menus and Popovers

- Right-click on servers, groups, terminals, and tabs must show context menus at the expected location.
- Opening dialogs from popovers must close or defer the popover first to avoid GTK grabbing-popup hangs.
- Context menus must not cause sidebar scroll jumps or horizontal scroll movement.
- Context menu actions must operate on the selected/right-clicked item, not a stale selection.
- The terminal context menu must show `Show session status bar` when the
  selected pane bar is hidden and `Hide session status bar` when it is visible;
  toggling it must not change sibling panes or the global default.
- Terminal context menus must keep the translated `Split` submenu above the `Tab` submenu, with a visual separator before the split actions.
- Terminal context-menu submenus must share the same hover behavior: open on pointer movement over the submenu row, stay usable while moving into the submenu panel, close when leaving the row and panel, and never close the whole terminal menu unexpectedly.
- Future terminal context-menu submenus must use the shared nested-menu helper instead of building independent popovers with custom hover behavior.

### Server Tree

- The icon-only sidebar actions for creating a group, server, or local terminal
  and for expanding or collapsing all groups must expose their translated
  action tooltips. Write actions must show the read-only or locked-connections
  explanation only while disabled and restore their action tooltip when
  enabled again.
- Groups and subgroups must preserve expanded/collapsed state when editing servers or refreshing the list.
- The server tree must not jump to the top when selecting or right-clicking entries.
- Filtering must include matching servers, groups, and subgroups.
- Group server counts must include servers inside subgroups.
- Servers should display only their name in the tree, with connection details in the tooltip.

### Configuration and Data

- Existing combined `connections.json` files must remain loadable and migrate app/terminal settings into `settings.json` without losing groups, servers, or preferences.
- New plain `connections.json` writes must contain only groups and servers; app and terminal preferences must be written to `settings.json`.
- Obfuscated connection storage must decode back to the same groups, servers, passwords, and private key paths, and switching modes must rewrite the file immediately.
- Encrypted connection storage must require a master password on startup, preserve groups, servers, passwords, and private key paths after unlock, allow canceling activation before setting a password, and never silently recover data if the master password is lost.
- The startup master-password prompt must be an in-window modal layer rather
  than a separate desktop window, so it always stays inside Termia on single-
  and multi-monitor desktops and blocks the underlying controls until it is
  unlocked or cancelled. Window-management actions must remain available so
  the locked window can still be moved, minimized, maximized, or closed.
- Import/export configuration must preserve groups, subgroups, servers, SSH user, port, host, password, and private key path where available.
- Importing Asbru configuration must not add unwanted suffixes such as `- copy`.
- Launching a second Termia process must open a separate window and leave the new instance in read-only mode instead of writing shared config files concurrently.
- On writable startup, unfinished history records from an earlier Termia process must be finalized as interrupted; a read-only secondary instance must leave them unchanged.
- A read-only instance must keep connect and export flows available while preventing edits, imports, clears, preference saves, and statistics writes.
- Clearing configuration must require confirmation.
- Passwords are currently stored in the JSON file by explicit project decision; warnings and documentation must remain accurate until storage changes.
- Security preferences must clearly warn before enabling encryption that Termia will ask for the master password on every startup and that lost master passwords cannot be recovered.

### Application Appearance and Themes

- Configured application colors and theme styling must remain consistent after UI changes.
- Header bar, main menu, configuration menu, statistics menu, popovers, sidebars, tabs, buttons, selected rows, warning text, and dialogs must remain readable in light, dark, system, and any custom app themes.
- Tab colors, borders, spacing, close button contrast, selected tab state, and hover/active states must remain visually clear.
- Context menus and popovers must use readable foreground/background colors and must not inherit terminal colors.
- Sidebar group/server selection colors must remain readable and must preserve the distinction between folders/groups and server entries.
- New CSS rules must be scoped to Termia classes where practical and must not unintentionally override GTK/VTE internals.
- Split pane separators must remain visible, narrow, and readable on both light and dark themes.
- Showing pane status bars must not enlarge split separators; narrow panes may
  ellipsize the connection name while keeping the timer and actions usable.
- Showing or hiding a pane status bar must preserve the existing position of
  every affected split divider.

### Terminal Appearance

- Terminal foreground, background, font, font size, ANSI palette, and prompt settings must apply to new terminal sessions.
- Terminal foreground/background color changes must not affect app menus, header bars, sidebars, dialogs, or tab chrome.
- Terminal palette changes must preserve readable ANSI colors for common output such as directories, executables, warnings, errors, and prompts.
- Reconnect and warning messages printed inside VTE must remain readable on both light and dark terminal backgrounds.
- Prompt color customization must remain visible with the configured terminal background.
- Font size shortcuts must update existing open terminals.
- LS color customization must continue to reduce overly bright directory/file colors.
- Tab labels should show short and medium names without unnecessary truncation, and provide a tooltip with the full title.

### Connection History

- Searching connection history must remain case-insensitive and match server names, hosts, users, results, details, timestamps, and formatted durations.
- Hiding local terminals must preserve SSH entries and the current search filter.
- History rows must keep translated connection kinds and results, server or local-terminal names, endpoints, details, and durations.
- Clearing history must refresh the open dialog without retaining stale entries.

### Statistics

- Statistics collection must remain lightweight and should not continuously write to disk on every keypress.
- Statistics must be disabled by default and must not record command or keystroke counters, even when enabled.
- Disabling statistics from General preferences must stop new aggregate connection and duration counters from being recorded or flushed.
- Global and current-run connection counters must remain separate.
- Per-session statistics must correspond to the selected terminal pane.

## Manual Regression Checklist

Before merging changes that touch UI, terminals, tabs, or configuration, verify:

- Open Termia and confirm a local terminal opens if the preference is enabled.
- Open two local terminals and reorder their tabs with the mouse.
- Right-click a tab, move it to a new window, repeat with another tab, and restore both detached windows to the main window.
- Duplicate a local terminal and confirm the custom prompt is applied.
- Open two SSH sessions and duplicate one of them.
- With 39 tabs open, confirm one additional local or SSH tab opens; with 40
  open, confirm individual tabs are rejected with an explanation. Confirm a
  workspace or server group that would exceed 40 is rejected in full, without
  starting a partial batch, and that detached tabs count toward the limit. The
  rejection notification must be visible and hide automatically.
- Close a tab and confirm focus moves to the next terminal.
- Middle-click a tab and confirm it follows the configured close confirmation and moves focus to the next terminal.
- Right-click a terminal and open the context menu.
- From the terminal context menu, confirm the translated `Split` submenu appears above `Tab` and is separated by a thin divider.
- Select `Open connection in split…`, search a saved server by name, host, and
  user, then use `Up`/`Down` and `Enter` to open the selected connection.
  Search for a value with no matches and confirm `Enter` keeps the dialog open
  with the query intact.
- Confirm terminal context-menu actions still work: disconnect, show and hide
  the selected pane's status bar, copy, paste, terminal preferences, session
  statistics, file transfer, all split directions, and all Tab submenu actions.
- Drag a horizontal split divider away from the centre, then show and hide its
  pane status bar from both the context menu and `Hide` button; the divider
  must remain at the chosen position and long status titles must ellipsize.
- Create split panes in all four directions and confirm each new pane opens a working shell.
- From an SSH pane, use `Open connection in split…` to open a different SSH
  server and then a saved local terminal; verify each pane's status bar, PID,
  elapsed time, saved-password action, SCP target, statistics, and history.
- Disconnect one mixed-connection pane and confirm its siblings remain usable.
- Open several SSH and local-terminal tabs with mixed split panes, use the
  sidebar save-workspace button, name the workspace, and confirm it appears
  with a grid icon in the `Workspaces` section.
- Open the saved workspace and confirm it recreates the expected tab order,
  connection identities, split orientations, and usable split panes as new
  terminal processes. Confirm its context menu can update, rename, duplicate,
  and delete it, while write actions are disabled in a read-only instance.
- Trigger a failed SSH connection in a split, press Enter, and confirm only that
  pane reconnects to its own server, its status bar remains usable, and its
  action returns from `Close` to `Disconnect`.
- Trigger a failed SSH connection in a split and confirm its status bar appears
  automatically with a `Close` action; use it and confirm the failed pane
  closes without reconnecting while its sibling remains usable.
- Trigger a failed connection in a tab with only one pane and confirm its
  automatically displayed `Close` action closes the tab.
- Confirm a seventeenth pane is rejected without changing the current layout.
- Run `exit` inside a split pane and confirm only that pane disappears while the sibling pane keeps focus and remains usable.
- Open an SSH session, a local terminal, and a split pane; close Termia and confirm their local child processes do not remain after a brief grace period.
- Right-click a server/group in the tree and open the context menu.
- Edit a server and confirm collapsed groups stay collapsed.
- Search for a group, subgroup, and server in the sidebar filter.
- Confirm the Recent section appears above Favorites, shows the 10 most recently connected servers without duplicates, and updates after new SSH connections.
- Open connection history, search for an SSH server, toggle local-terminal entries, and confirm row contents remain unchanged.
- Open statistics and confirm the four metric cards, current-run count, duration values, ranked servers, counts, and progress bars remain correct.
- Open every main-menu action and every Connections File submenu action, confirming each still opens or runs the intended feature after the popover closes.
- Open Import/Export, close the menu with `Esc` or its menu button, and confirm reopening starts at the top-level menu.
- Open Preferences from Configuration and confirm the app does not hang.
- Start a second Termia process and confirm it opens as a separate window with the read-only badge visible.
- With encrypted connection storage, start Termia on each monitor in turn and
  confirm the master-password prompt is rendered inside the Termia window;
  move the locked window between monitors, verify that underlying application
  controls are blocked, and confirm that successful unlock and cancellation
  work in writable and read-only instances.
- In the read-only instance, confirm add/edit/delete/import/clear/preferences actions are disabled or rejected, while connecting and exporting still work.
- Switch between available app themes and confirm header, menus, sidebars, dialogs, selected rows, and tabs remain readable.
- Change terminal foreground/background/palette and confirm only VTE terminal colors change, not the app chrome.
- Confirm terminal ANSI colors, prompt colors, and the reconnect prompt are readable on both light and dark terminal backgrounds.

## Automated Checks

Run at minimum:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m py_compile run_termia.py scripts/compile_translations.py src/termia/*.py tests/*.py
bash -n scripts/termia-setup.sh
scripts/compile_translations.py
scripts/compile_translations.py --check
```

When practical, add targeted tests for pure logic such as prompt templates, config migration, import/export, and statistics.

The automated equivalent runs in GitHub Actions for every pull request and
every push to `main`.
