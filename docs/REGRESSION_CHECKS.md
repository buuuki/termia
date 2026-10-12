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
- Command snippets must be stored locally and run only after explicit selection,
  variable entry when required, and confirmation of the final preview. Their
  command text and variable values must never be written to debug logs.
- Snippet management must open with three visible columns: compact categories
  with counts, a snippet list, and a read-only command preview. The preview and
  Edit/Duplicate/Delete actions must remain empty or disabled until a snippet
  is selected. Category rows must remain uniformly sized, including long names
  and empty categories. Selecting a category filters the list; typing in search
  must search across all categories, even after a category was selected.
  Search spans the top alone; Manage categories appears above the category
  column, Create snippet above the list, and a modest Command preview label
  above the read-only preview. The selection hint appears beneath the list
  until a snippet is selected, including below No matching snippets when the
  list is empty. A category-filtered list shows snippet names only; global
  search and the execution picker retain
  category-qualified names. Category creation from the editor remains available.
  Adding from a category must preselect it, and uncategorized snippets must
  remain selectable even when other categories exist. Category management must
  preserve empty categories, rename all contained snippets, duplicate them
  with new IDs, and move them to Uncategorized on confirmed deletion. The
  category-management page must have no repeated heading; All categories
  remains at the top, while Cancel sits beside Delete category and both return
  to the three-column snippet manager. Category management must show uniform
  icon tiles with names and snippet counts (including zero) across multiple
  rows; selecting a tile enables Rename, Duplicate, and Delete. The selected
  highlight must follow the rounded tile rather than the square outer cell,
  while keyboard focus remains visible in light and dark themes.
- Snippet variable values must be shell-quoted as individual arguments, and a
  group-scoped snippet must apply to servers in that group and its nested
  subgroups. Invalid or deleted scope targets must never broaden a snippet to
  global availability.
- Repeatedly opening, cancelling, and reusing snippet management and execution
  flows must reuse their existing windows and remain responsive during window
  resizing; these flows must not accumulate top-level GTK surfaces.
- SSH fingerprint prompts must remain visible and interactive in the terminal.
- Known-host inspection must prefer the configured endpoint (`host` on port 22
  or `[host]:port` otherwise), then mirror OpenSSH's non-standard-port fallback
  to `host` without modifying any known_hosts file. A genuinely unknown host
  must still show the interactive fingerprint prompt.
- Starting a password-backed SSH connection or SCP transfer must leave the
  interface responsive while the SSH known-host lookup completes.
- `Send files to server` must open its selector from both a saved server's
  sidebar context menu and a terminal context menu; the latter must use its
  owning main or detached window, and cancelling either selector must be safe.
- When SCP targets an unknown endpoint, it must show an explicit dialog with
  host, port, key type, and SHA-256 fingerprint. Accepting must save the key
  only after confirmation and continue the transfer; cancelling must leave
  known_hosts unchanged. The flow must work from both sidebar and terminal
  context actions.
- When no saved password is available, SCP must suppress system SSH_ASKPASS,
  try public-key authentication first, and show one native Termia password
  dialog only when key authentication fails. The entered password must be
  reused for preparation and copying without being logged or persisted.
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
- An SSH shell that exits after a failed or cancelled remote command (for
  example, cancelling `sudo` and then running `exit`) must follow the same
  clean-close behavior. OpenSSH transport/authentication failures (exit status
  `255`) and signalled SSH children must instead retain the reconnect prompt.
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

### Notes

- Notes and categories must persist in `notes.json`, separately from
  `connections.json`; changing connection storage mode must protect notes using
  the same selected mode and master password.
- The notes workspace must be modeless and reusable: keep it open while
  switching focus to and typing in an embedded or detached terminal.
- The notes window must provide normal minimize, maximize, and close controls.
- The notes writing area must remain visibly distinct from the surrounding
  workspace, with a readable background and border in both light and dark
  themes; text must not sit directly against the edge.
- Notes must autosave non-empty text changes without a separate autosave
  preference. A completely empty draft must not be persisted. If an existing
  note is emptied, its prior saved content must remain intact until an explicit
  non-empty edit is saved or the note is deleted.
- Keep the notes-list toggle, New note button, and Import/Export overflow menu,
  in that order, on the left side of the notes window title bar. Hiding the
  list must remove the pane and category button, while New note remains
  available; align the tab and editor left edges. Restoring the list must
  return it to its
  previous width and restore a small, visible inset beside the divider
  (about 6 px).
  Place the Add category icon above global search and the category-grouped note
  tree in the sidebar. Keep it aligned with the list toggle. Both New note and
  Add category must remain usable when no categories exist.
  Search must span all categories, and there must be no category filter
  dropdown. Align the top of search with the top of the notes writing area,
  and keep the same 6 px inset on both sides of the list divider at the default
  and resized sidebar widths. Hide Import/Export for server-scoped notes.
  Selecting the Servers root or expanding a category must not automatically
  select a note or populate the editor. Disable category/note creation at the
  Servers root with no server selected, and enable both when a server branch is
  selected. Preserve an explicit note selection during list refreshes.
  Server associations must remain intact when editing saved notes. In a
  read-only instance, opening
  a note must still allow reading
  and selecting its text without enabling edits.
- The sidebar must show a hierarchical tree: Personal contains personal
  categories; Servers contains servers with notes or saved categories, plus
  the currently selected server scope, with its categories and notes beneath
  it. Omit other servers without notes or categories. Server branches should start collapsed so
  large server collections do not flood the list; search must find servers by
  name as well as notes by title, body, or category. Selecting a server or
  personal category sets the creation scope without mixing categories. Scope
  changes preserve open tabs and drafts. Categories are scoped independently,
  so the same name can exist personally and on multiple servers. Show persistent
  empty categories only in their own scope; show Uncategorized when that scope
  has uncategorized notes or an active unsaved draft. Show each empty draft as a
  temporary New note row beneath its scope's Uncategorized category; do not
  persist it until it contains text. Category rows must expand/collapse and accept
  drag-and-drop; dropping updates only the note and its open tabs. Rows fit on
  one line; note rows show titles, while server rows identify their server.
  New note titles are numbered
  within the selected scope (New note, New note 2, etc.). Tabs show a
  personal/server icon; hovering or focusing a server-note
  tab identifies its server. Keep the tab bar and editor aligned when the
  sidebar is hidden. Tab close icons must appear inside the tab card and remain
  independently clickable.
- Note editors must support multiple open tabs. New note titles are numbered
  within their scope (“New note”, “New note 2”, and so on). The active tab
  must have the
  same visible focus highlight as a terminal tab plus a thin, full-width
  dark-blue underline with no side glow; inactive note tabs must not show that
  underline. Tabs must be reorderable by
  dragging without changing note content or saved associations. Right-click an
  open tab and a note in the sidebar; each menu must offer Rename, and renaming
  must persist while updating all open tabs for the same note. Opening a note
  already in a tab
  must activate that tab rather than opening a duplicate. Switching tabs must
  preserve each note's title, content, category, server association, and dirty
  state; autosave and explicit Save must only affect the intended note. Closing
  an incomplete unsaved draft must require confirmation. Closing a clean tab
  using its close icon must close only that tab, including immediately after
  saving; closing a dirty tab must offer Save and close,
  Close without saving, and Keep editing. Switching between unsaved draft tabs
  when the persisted note list is empty must keep the newly selected editor
  visible without requiring a second click.
- Main-menu notes management must show the complete tree, with a search field
  wide enough for roughly 30 letters and import/export actions. Opening notes
  from a server must expand its tree branch and hide Import/Export. In the
  general view, omit servers without notes or saved categories; when opening a
  specific server with no notes, include that server and its active draft.
  Opening the hidden notes window must focus a new empty draft for the selected
  scope, or resume an existing draft for that scope without adding a duplicate.
  Re-presenting an already visible window must not add a draft; read-only
  instances must not create drafts. Empty drafts must remain unpersisted.
  Search belongs above the note tree in the sidebar, below the category button.
  The Import/Export overflow menu stays in the title bar and is
  visible only while Personal is the active creation scope. New-note numbering
  must be independent in Personal and each server scope. Empty
  views must show a useful message instead of a disabled editor. Single-clicking
  a note must only select it; double-clicking opens its editor in a tab,
  activating an existing tab instead of duplicating it. Selecting another note
  must not replace or visually disagree with the active editor. Verify the idle
  workspace explains that double-click opens a note.
- Verify standalone notes and server-linked notes can be created, searched,
  edited, and deleted. Create a category with the button above search, then
  right-click its folder row to rename, duplicate, or delete it. The context
  menu must also open with Menu or Shift+F10 while the row button has focus.
  Uncategorized and Server notes must not have category-management menus.
  Existing categories persist; duplicating a category duplicates its notes
  with new IDs; deleting a category moves its notes to Uncategorized. Renaming
  or deleting a category must update already-open note tabs without restoring
  the old category on the next autosave.
- Right-click notes in the list and confirm the menu offers Edit, Rename,
  Clone, Properties, and Delete. Properties must remain available in read-only
  mode and show title, category, associated server or Personal notes, creation
  and modification dates in local time without fractional seconds, line and
  character counts, and UTF-8 content size. The Properties window must use its
  natural content height, with Close in a bottom row inset from the edges and no
  large blank area beneath it. Check that the details text has padding inside
  its contrasting background and that the outer top and bottom margins are
  compact.
  Opening Properties must not briefly highlight Delete or select the title
  value. Keep the bottom inset compact. The title bar and outer frame use the
  menu surface, while the inner details panel uses the window surface in both
  light and dark themes.
  Clone a note and verify the copy
  has a new identity, a “(copy)” title suffix, the same content/category/server
  association, and is saved immediately.
- Verify the note, category, tab, and Import/Export context menus use the same
  theme-aware popover surface and button treatment as the main menu.
- Rename an open note tab and confirm the current title is selected in the
  rename field so typing replaces it immediately.
- Toggle the notes list off and on; verify the toggle stays at the far left of
  the title bar and the new-note button remains beside it. The list pane and
  category button disappear completely; the category button returns above
  search when the list is restored. While hidden,
  the left edges of the note tabs and editor must align; restoring the list
  returns its previous width and the
  normal content inset. Confirm the overflow menu follows the list toggle,
  contains Import and Export in the general view, and is hidden in server-scoped
  notes. With several notes, verify the list fills the panel height and shows
  multiple rows before scrolling. Open
  enough note tabs to overflow and confirm that their horizontal scrollbar is
  slim and translucent, does not obscure tab titles, and remains usable with
  the mouse in light and dark themes. Open two existing notes and one draft in
  tabs; verify the close icon is visually inside each tab and works
  independently. Switch among the tabs while editing,
  reorder them by dragging, and verify each retains its own content without a
  colored outline around the entire tab bar. Confirm
  opening an already open note activates its existing tab, and Save/autosave
  affect only that note. Closing a clean tab must close only that tab. Close a
  dirty tab and test Save and close, Close without saving, and Keep editing.
  The editor's Close tab button must follow the same behavior as the tab's X;
  neither can undo changes that were already saved automatically.
  Confirm the active tab highlight follows the selected note. With no saved
  notes, switch between multiple unsaved drafts and verify each editor appears
  on the first click. Hide the sidebar and verify the tab row and text editor
  share the same left edge.
  While editing one note, right-click another and confirm edits are saved before
  its context menu opens and the clicked note remains selected.
- Edit an existing note and create a new note; confirm autosave status and
  modified timestamp update, and that the list sorts by most recently modified.
  Displayed dates must use local `YYYY-MM-DD HH:MM:SS` format without the `T`
  separator or fractional seconds; stored timestamps must retain their original
  precision.
  Confirm new note titles are numbered within their scope (“New note”,
  “New note 2”, etc.), and there are no title,
  category, server, or autosave-toggle controls in the editor. Start typing and
  verify content saves automatically. Leave a new draft empty and verify no
  record is created. Empty an existing note and verify its previous saved text
  remains until explicitly deleted or non-empty content is restored.
  Drag a note onto another category and onto Uncategorized; verify list grouping
  updates and an already-open editor keeps the new category after autosaving.
  Confirm the explicit Save button persists server-linked notes even before the
  autosave delay. Close an incomplete draft tab and confirm Keep editing
  preserves it while Close without saving removes only that draft.
  Open server notes from a sidebar context menu and confirm the notes window
  receives focus after the popover closes and remains modeless.
  Confirm a long category name stays within its folder row and does not widen
  the notes sidebar.
  Force a save failure and confirm the editor retains the unsaved text when
  switching notes or closing the notes window.
- Delete a server, delete a group containing servers, clear connection
  configuration, and replace connections through import. Notes must be kept;
  associations to removed servers become personal notes.
- Export notes without protection and with a separate password. Import both,
  reject wrong passwords and malformed/future schemas without changing local
  notes, and verify orphaned server associations are detached.
  The export choice must explain that no password means readable, unencrypted
  JSON, while an export password encrypts the file and is required for import.
  Confirm this password is independent of the local master password.
  Choosing password protection must open a masked password prompt and then the
  file-save chooser; importing a protected file must show the same password
  prompt without a GTK error.
- When notes already exist, cancel import or choose Keep existing and confirm
  the current notes remain unchanged. Choose Back up and replace and confirm a
  protected backup exists before replacement; an unwritable backup location
  must leave the current file unchanged.
- Test notes in plain, obfuscated, encrypted, and read-only configurations;
  do not expose note text in logs or terminal input.
- `scripts/run_test_instance.sh --copy-current-config <profile>` must copy
  `notes.json` into the isolated profile without changing the original file.
  The test profile must redirect only Termia data, preserving the desktop GTK
  configuration and appearance.

### Application Appearance and Themes

- Configured application colors and theme styling must remain consistent after UI changes.
- System follows GNOME's active appearance, while Light and Dark request the
  corresponding GTK variant. None of these built-in modes may impose a
  Termia-specific menu, dialog, button, text, selection, or error color.
- Header bar, main menu, configuration menu, statistics menu, popovers, sidebars, tabs, buttons, selected rows, warning text, and dialogs must remain readable in light, dark, system, and any custom app themes.
- Tab colors, borders, spacing, close button contrast, selected tab state, and hover/active states must remain visually clear.
- Context menus and popovers must use readable foreground/background colors and must not inherit terminal colors.
- Sidebar group/server selection colors must remain readable and must preserve the distinction between folders/groups and server entries.
- New CSS rules must be scoped to Termia classes where practical and must not unintentionally override GTK/VTE internals.
- Split pane dividers have two deliberately different visual parts that must be
  checked separately:
  - The thin visual separator line uses the configured split-separator color
    (green `#008712` by default) and configured thickness. It must remain
    distinct from the drag area and must not be replaced by the terminal
    background color.
  - The wider draggable area uses the configured terminal background color, so
    it must change when the terminal background changes and must follow the
    active terminal theme/background. Its minimum drag size is 5 px, or the
    configured separator thickness when that is larger; it is vertical for
    horizontal splits and horizontal for vertical splits.
- Split dividers must remain readable on both light and dark themes. Confirm
  that the thin configured line remains visible while the wider drag area
  blends with the terminal background.
- Showing pane status bars must not enlarge either the thin separator line or
  the draggable area; narrow panes may ellipsize the connection name while
  keeping the timer and actions usable.
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
- Disabling Statistics from **Add-ons** must stop new aggregate connection
  and duration counters from being recorded or flushed after the next restart.
- Global and current-run connection counters must remain separate.
- Per-session statistics must correspond to the selected terminal pane.
- Statistics remains disabled by default. When it is off, its main and terminal
  menu actions must be absent, and no aggregate statistics writes may occur.
- The SFTP browser remains on by default. Disabling it must hide both sidebar
  and terminal-menu actions without disabling SCP or changing saved credentials.
- Optional-tool changes take effect only after restart and must never delete
  statistics data or interrupt existing SFTP transfers.

### Optional built-in tools

- In an isolated test profile, toggle Statistics and SFTP in Add-ons,
  restart Termia, and verify the main, server, and terminal menus reflect each
  choice. Re-enable both, restart, and verify their previous data remains.
- With Statistics enabled, open and close local, SSH, and split panes; verify
  connection counts, duration counts, current-run counts, and shutdown flushes
  without duplicate records. Repeat with Statistics disabled and verify no
  counters change.
- With SFTP enabled, open it from both server and terminal context menus;
  closing the owner session must still cancel its transfer. Disabling it must
  not affect SCP or terminal operation.

## Manual Regression Checklist

### About updates

- Open About and use Check for updates. Keep the existing logo, version,
  license, issue link and native dialog appearance. Check keyboard access,
  light/dark themes, and English/Spanish/Catalan. Terminal and split geometry
  must remain unchanged; opening About alone must not query the network.
- Run from the development branch: no downgrade to beta.1 is offered and the
  checkout restriction is explained. Verify no-update, offline, timeout,
  malformed metadata and newer compatible release states using injected clients.
- Check numeric beta ordering and beta-to-final-stable progression in the same
  application line. Stable users must never be offered prereleases automatically.
- In a disposable clean release checkout, prepare an official tag and confirm a
  fast-forward. Repeat with dirty, development, detached non-release and divergent
  checkouts: refuse without resetting or stashing user files. A fetch may leave
  a tag, but cancellation before application must not alter the working tree.
- In a disposable Debian installation, verify a compatible package's digest,
  package identity, version and architecture. Reject missing/wrong digests,
  truncated/oversized downloads and downgrades before requesting authorization.
  Confirm installation through the desktop authentication agent and separately
  cancel authorization; check missing tools and a busy package manager.
- Cancel a download and close/reopen the dialog during checks; suppress late
  callbacks and remove partial downloads. A second profile must not start a
  concurrent job. Once package installation starts, let APT finish even if Termia
  closes, retain its temporary package until then, and restart manually.
- Verify debug logs contain only update lifecycle events, not downloaded bodies,
  command output, credentials or paths. Existing connection data is untouched.

### Native SFTP explorer

- From the saved-server menu and from each SSH pane of a mixed split, open
  `Browse files (SFTP)` and check the correct endpoint. Terminal size, divider
  positions, application CSS, and existing SCP actions must remain unchanged.
- Check passwords, SSH-agent/default keys and explicit private keys. Reject an
  unknown fingerprint and verify no key is saved; accept a verified fingerprint
  and reconnect. A changed known key must be refused, without an accept option.
- Navigate and refresh, including paths with spaces. Upload multiple files and
  nested directories, download them and compare contents. Existing destinations
  must be refused without truncating data, including symbolic-link destinations.
- Create and rename directories. Confirm deletion only affects the selected
  file or empty directory. Symbolic links must not be followed in recursive
  transfers, and nonempty directories must not be recursively deleted.
- Cancel during connection and transfer. Reconnect explicitly and repeat the
  operation; no old callbacks may affect the new session. Partial remote files
  or newly created directories may remain, as explained by the status message.
- Close the explorer, its owning tab (also after detaching), and Termia during
  a transfer. Confirm the SFTP transport closes and no worker remains after the
  bounded network timeout. Unrelated terminals and sidebar-owned explorers must
  remain usable when closing a different tab.
- Check light/dark themes and English/Spanish/Catalan labels. Verify remote
  errors do not expose credentials or private paths in debug logs. A read-only
  Termia instance must not persist passwords or alter connection configuration.

### Existing application behavior

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
  Check the divider's two visual parts independently: the thin line must keep
  its configured color and thickness, while the wider drag area must retain its
  minimum drag size and terminal-background color.
- In both light and dark application themes, change the terminal background in
  Terminal preferences and save it. Confirm that the wider draggable area
  changes to the new terminal background while the thin separator line keeps
  its configured color. Change the separator thickness as well and confirm
  that only the thin line's configured thickness changes, with the drag area
  remaining at least 5 px wide/tall or growing to the configured thickness when
  that exceeds 5 px.
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
