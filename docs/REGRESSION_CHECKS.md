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
- Header actions must retain the same six-pixel spacing as sidebar actions and
  align with the sidebar's content inset when the sidebar is visible.
- The sidebar local-terminal profile action must show a terminal icon with a
  small plus badge; the main-toolbar new-tab action must retain
  `tab-new-symbolic` without that custom badge.
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
- Notifications triggered while the overlay is visible must remain grouped in
  arrival order, including repeated messages, and each new message must restart
  the hide timer instead of replacing earlier feedback.
- Duplicating an SSH tab must open a new SSH connection to the same server.
- Duplicating a local terminal tab must use the same local-terminal startup path as opening a new local terminal, including prompt settings.

### Terminal Sessions

- Local terminals must start in the user's home directory unless a future setting explicitly changes it.
- Local terminal prompt customization must apply to newly opened and duplicated local terminals.
- SSH sessions must not send arbitrary commands automatically to remote servers.
- SSH fingerprint prompts must remain visible and interactive in the terminal.
- Starting a password-backed SSH connection or SCP transfer must leave the
  interface responsive while the SSH known-host lookup completes.
- `Send files to server` must open its selector from both a saved server's
  sidebar context menu and a terminal context menu; the latter must use its
  owning main or detached window, and cancelling either selector must be safe.
- After local file selection, SCP must prompt for a per-transfer absolute remote
  destination defaulting to `/tmp/.termia`; invalid, relative, control-character,
  and parent-traversal paths must not start host inspection or a child process.
- SCP must only verify that the remote destination already exists and is a
  directory; it must never create a missing destination as an implicit side
  effect of sending files. Its remote `test -d` command must remain compatible
  with shell builtins and safely quote the absolute destination operand.
- Remote destinations containing spaces or shell metacharacters must remain one
  argument, must not gain literal shell-quote characters in SFTP-mode SCP, and
  must never execute as shell syntax. Transfer failures must safely identify
  whether remote preparation or file copying failed without exposing raw output.
- Cancelling an SCP transfer, closing its progress window, closing its owning
  detached window, or closing Termia must stop the isolated transfer process
  tree without starting a later phase, emitting duplicate outcomes, or leaving
  `sshpass`, `ssh`, `scp`, or `setsid` descendants behind.
- An SCP transfer started from a terminal belongs to that terminal session, not
  its current window: detaching the tab and then closing it, or closing the tab
  while still attached, must cancel the transfer and close its progress dialog.
- SCP diagnostics may record only lifecycle phase and outcome; they must not
  contain passwords, server identities, usernames, or selected paths.
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
- Explicitly disconnecting the original/first pane of a multi-pane local or SSH
  tab must remove and collapse that pane just like any later split, keep sibling
  panes usable, and clear its process identity so detached-window, tab, and
  application shutdown never signal the completed process again.
- Closing an original/first pane that is waiting to reconnect must remove only
  that pane while any connected or failed sibling remains; the whole tab closes
  only when its final pane is closed.
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
- In horizontal, vertical, nested, and 2x2 split layouts, use the configured
  `Ctrl+Arrow` shortcuts to move to the nearest pane in each visual direction.
  At an outer edge, focus must remain in the current pane. Disable one shortcut
  and confirm its key combination reaches the terminal instead.
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
- Creation tooltips must distinguish opening an immediate local terminal from
  creating an SSH connection or a reusable local-terminal profile.
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
- Adding a split inside an existing nested layout must preserve every ancestor
  divider and divide only the selected pane approximately 50/50, allowing a
  one-pixel difference for odd dimensions.

### Terminal Appearance

- Terminal foreground, background, font, font size, ANSI palette, and prompt settings must apply to new terminal sessions.
- The audible terminal bell must be disabled by default, and its preference
  must apply to newly opened and already open VTE terminals.
- Terminal foreground/background color changes must not affect app menus, header bars, sidebars, dialogs, or tab chrome.
- Terminal palette changes must preserve readable ANSI colors for common output such as directories, executables, warnings, errors, and prompts.
- Reconnect and warning messages printed inside VTE must remain readable on both light and dark terminal backgrounds.
- Prompt color customization must remain visible with the configured terminal background.
- Terminal appearance and local prompt settings must share one preferences
  dialog and one live preview showing prompt, command output, and ANSI colors.
- The standard Terminal preferences window must show its appearance controls,
  shared preview, and prompt controls together without requiring vertical scrolling.
- Saving prompt settings must never inject commands into running local shells
  or SSH sessions; changes apply only to new and duplicated local Bash terminals.
- Font size shortcuts must update existing open terminals.
- LS color customization must continue to reduce overly bright directory/file colors.
- Tab labels should show short and medium names without unnecessary truncation, and provide a tooltip with the full title.
- The terminal tab strip must keep tabs at a readable width, show its compact
  horizontal scrollbar only when tabs overflow, and never widen the window or
  collapse/change the selected server-sidebar width.
- The tab overflow control must list every attached tab in visual order, show
  full titles, indicate the active tab, and support keyboard activation.

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

- Filter for one server and open it with Enter. Type a different query and
  immediately press Enter; only the first server in the current results may
  open. Repeat with a query that has no matches and confirm nothing opens.

- Open Termia and confirm a local terminal opens if the preference is enabled.
- Open two local terminals and reorder their tabs with the mouse.
- At 1280, 1366, 1920, and 2560 logical pixels, open enough tabs to overflow
  with the sidebar visible and hidden. Confirm the compact horizontal scrollbar
  appears only while needed, the window and sidebar widths remain unchanged,
  and every tab is reachable from the strip and overflow control.
- With exactly two tabs whose titles fit, confirm the overflow selector is
  hidden. Reduce the window width or lengthen a tab title until the strip
  overflows, then confirm the selector appears; restore the width and confirm
  it hides again.
- At each target width, confirm the active tab is revealed after opening,
  closing, keyboard navigation, overflow selection, drag reordering, resizing,
  and toggling the sidebar.
- Right-click a tab, move it to a new window, repeat with another tab, and restore both detached windows to the main window.
- Move a tab to a new window and confirm its title bar shows the configured
  GNOME minimize, maximize, and close controls. Minimize and maximize it
  without closing the session, then close the detached window and confirm the
  tab returns to the main window.
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
- Starting from one pane, create the second, third, and fourth panes. Before
  every insertion, move all existing dividers away from their defaults. Repeat
  the sequence as needed to cover left, right, up, and down. Confirm each new
  split divides only the selected pane approximately 50/50, every previous
  divider remains fixed, and every new pane opens a working shell.
- Repeat the progressive one-to-four-pane check with local and SSH connections,
  including a nested split with an odd-sized selected pane. Confirm the
  one-pixel difference is the largest imbalance and the terminal prompt is not
  repeatedly redrawn while the connection starts.
- Save and reopen a workspace containing several tabs with nested local and SSH
  splits. Visit every restored tab and confirm all left/right and top/bottom
  panes are visible immediately, without opening a context menu, while saved
  divider proportions remain intact.
- From an SSH pane, use `Open connection in split…` to open a different SSH
  server and then a saved local terminal; verify each pane's status bar, PID,
  elapsed time, saved-password action, SCP target, statistics, and history.
- Start an SCP upload and cancel it once while preparing the remote directory
  and once while copying. Repeat by closing the progress window and by closing
  its owning Termia window; confirm a single cancelled outcome and no transfer
  processes remain. Complete one password-backed and one key-backed upload and
  confirm success, then force a remote failure and confirm an error outcome.
- Upload to the default destination and to a custom absolute path, including a
  path with spaces. Reject an empty path, a relative path, a `..` segment, and a
  pasted newline while keeping the destination dialog open and starting no
  SSH/SCP process.
- Select a missing but otherwise valid absolute destination and confirm that the
  transfer reports it as unavailable without creating it on the remote server.
- While a terminal-owned SCP copy is active, detach its tab and close the new
  window; repeat by closing an attached tab. Confirm both paths cancel the copy
  and close its dialog, while a sidebar-started transfer is unaffected by
  closing an unrelated terminal tab.
- Disconnect one mixed-connection pane and confirm its siblings remain usable.
- In attached and detached tabs with at least three panes, explicitly disconnect
  the original/first local and SSH pane. Confirm it disappears, the remaining
  split fills the space, focus stays usable, and later window/application close
  reports no failed or duplicate termination for the disconnected process.
- Open several SSH and local-terminal tabs with mixed split panes, use the
  sidebar save-workspace button, name the workspace, and confirm it appears
  with a grid icon in the `Workspaces` section.
- Open the saved workspace and confirm it recreates the expected tab order,
  connection identities, split orientations, and usable split panes as new
  terminal processes. Confirm its context menu can update, rename, duplicate,
  and delete it, while write actions are disabled in a read-only instance.
- Rename a tab, change the working directory independently in two local split
  panes, save the workspace, and reopen it. Confirm the custom tab title and
  both local directories are restored. Remove one saved directory and confirm
  that pane falls back to its normal startup directory without blocking the
  rest of the workspace. Confirm SSH panes do not persist a remote directory.
- Confirm a workspace with 32 total panes opens directly without confirmation,
  while saving, updating, duplicating, or opening one with more than 32 total
  panes is rejected without starting terminal processes or deleting the saved
  workspace.
- Trigger a failed SSH connection in a split, press Enter, and confirm only that
  pane reconnects to its own server, its status bar remains usable, and its
  action returns from `Close` to `Disconnect`.
- Trigger a failed SSH connection in a split and confirm its status bar appears
  automatically with a `Close` action; use it and confirm the failed pane
  closes without reconnecting while its sibling remains usable.
- Start with a failed original SSH pane, add both failed and successfully
  connected SSH splits, and close the original pane. Confirm only that pane is
  removed, every sibling keeps its own state, and the tab remains open.
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
- Save unchanged General preferences and confirm no setting-change notification
  appears. Then change Theme, Language, Debug mode, and several switches
  together; confirm every changed setting appears once, with its translated
  value, in the same notification panel.
- Start a second Termia process and confirm it opens as a separate window with the read-only badge visible.
- With encrypted connection storage, start Termia on each monitor in turn and
  confirm the master-password prompt is rendered inside the Termia window;
  move the locked window between monitors, verify that underlying application
  controls are blocked, and confirm that successful unlock and cancellation
  work in writable and read-only instances.
- Open a local terminal, a saved SSH connection, and a mixed split layout in
  several tabs, then close Termia. Reopen it and confirm that the restore dialog
  appears (after unlocking encrypted connections when enabled), restoring the
  tab order, saved identities, split directions, and divider positions as new
  processes. Confirm terminal output and the old processes are not restored.
- In a fresh profile, confirm `Restore the previous session when Termia starts`
  is disabled in `General`; create and close sessions, reopen Termia, and
  confirm no restoration prompt appears. Enable it, repeat the close/reopen
  flow, and confirm the prompt and restoration are available.
- Choose `Start fresh` in the restore dialog and confirm normal startup behavior
  continues, the same snapshot is not offered again, and the configured startup
  local-terminal preference still works. Delete one saved connection before
  restoring and confirm the unavailable tab is skipped with a notification.
- Start a second read-only Termia instance while a snapshot exists and confirm
  it never modifies or deletes the snapshot; close the writable instance and
  confirm the snapshot remains restorable.
- In the read-only instance, confirm add/edit/delete/import/clear/preferences actions are disabled or rejected, while connecting and exporting still work.
- Switch between available app themes and confirm header, menus, sidebars, dialogs, selected rows, and tabs remain readable.
- Change terminal foreground/background/palette and confirm only VTE terminal colors change, not the app chrome.
- Open Terminal preferences and change appearance and prompt controls together;
  confirm the shared preview updates both, appearance updates all open panes on
  save, and prompt changes appear only in a newly opened or duplicated local Bash terminal.
- At the default Terminal preferences size, confirm the shared preview remains
  visible while changing the font family and size, and controls use compact natural widths.
- Open General preferences, enable the audible terminal bell, and press Tab in
  a shell where completion produces a bell; disable it again and confirm the
  same action is silent. Verify the default is disabled in a fresh profile.
- Confirm terminal ANSI colors, prompt colors, and the reconnect prompt are readable on both light and dark terminal backgrounds.

## Automated Checks

While iterating on code, run the affected test module and syntax-check the
touched Python files. Use non-verbose output by default; rerun only a failing
module or case with `-v` when its detailed output helps diagnose the failure.

After a code implementation is stable and before opening the PR, run at minimum:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m py_compile run_termia.py scripts/compile_translations.py src/termia/*.py tests/*.py
bash -n scripts/termia-setup.sh
scripts/compile_translations.py --check
```

If translations changed, run `scripts/compile_translations.py` before its
`--check` mode. Do not repeat an unchanged successful command. If subsequent
edits can affect a check's coverage, rerun that check; repeat the complete suite
only when the later change warrants it.

For documentation-only changes, validate the affected documentation, links,
and documented command availability without running unrelated application
tests.

When practical, add targeted tests for pure logic such as prompt templates,
config migration, import/export, and statistics.

The automated equivalent runs in GitHub Actions for every pull request and
every push to `main`.
