# Changelog

## Unreleased

## 0.6.0-beta.4 - 2026-10-25

Prepared for final validation; release publication is tracked in `#386`.

### Added

- Measure unittest line and branch coverage with the existing private GTK test
  runner, console/HTML reports and CI artifacts, without a minimum threshold (`#398`).

- Run pinned Ruff and Bandit checks in CI, showing existing findings and
  blocking new diagnostics or failed analysis against the Git baseline (`#390`).

- Publish the observable Ubuntu/XFCE KVM laboratory with real sudo/polkit
  upgrade trials, generated synthetic credentials, per-stage evidence and
  English, Spanish and Catalan reproduction guides (`#383`).

- Publish a portable Docker laboratory with a browser desktop, optional Zenity
  manager, runtime-generated SSH fixtures and lifecycle/memory/visual probes.
  Include matching English, Spanish and Catalan setup guides, allowlisted build
  contexts and privacy regression coverage (`#377`).

- Assign a keyboard shortcut to a saved snippet in its compact editor or in
  keyboard preferences. Share assignments by snippet ID, reject conflicts,
  respect the focused pane's scope, and retain variable prompts and final
  preview confirmation. Copies start without shortcuts (`#330`).

- Nest note categories by dragging within their Personal/server scope, or
  return groups to the root via the scope header. Preserve notes and editor
  tabs, reject cycles and cross-scope drops, and back up older notes files
  before upgrading to schema 3. Add Expand all / Collapse all controls with
  search revealing matching notes and their ancestors (`#331`, `#332`).

- Open the snippet manager as an independent GTK window so terminals remain
  usable while snippets are managed. Fit fixed-size category tiles into the
  available width and wrap them into additional rows, align Create snippet to
  the left, place category actions below Back to snippets, and label the return
  action clearly (`#346`).

- Allow each saved SSH server to run a configured command after authentication
  and keep the remote session open with an interactive shell (`#344`).

- Add a hideable notes toolbar with persistent font, size, text color, and
  background preferences and optional line numbers for the plain-text editor.
  Use the requested dark editor and gutter colors. Open
  the modeless notes window in front of its parent while retaining minimize and
  maximize controls. Keep the compact toolbar's scrollbar clear of its buttons
  and its visibility independent of the smaller-font notes list (`#328`).

- Add a dedicated Disconnect action to the SFTP browser, keep Cancel and
  Reconnect SFTP separate, and align all three actions to the right (`#315`).

- Allow changing the master password for encrypted connections and notes,
  verifying the current password and restoring original files if re-encryption
  fails (`#314`).

- Move saved servers between sidebar groups, nested groups, and Ungrouped by
  dragging, without changing their identities or open sessions (`#299`).
- Add restart-applied switch controls for the bundled Statistics and SFTP add-ons.
  Disabled add-ons are omitted from their menus without deleting stored data
  (`#304`).
- Add right-click note actions for editing, cloning, and deleting; cloning saves
  a new note with the same content, category, and server association (`#289`).
- Add a separate notes workspace with standalone and server-linked notes,
  categories, autosave, protected import/export, backup-before-replace
  behavior, and isolated test-profile copying (`#289`).

### Changed

- Prepare source version `0.6.0-beta.4`, Debian version `0.6.0~beta.4-1`,
  translated feature summaries and package-build instructions for final release
  validation; publication remains pending the review in `#386`.

- Organize Help into translated sections covering current workflows and show
  the user's configured application shortcuts (`#369`).

- Keep the terminal tab strip as an explicitly approved composition of GTK
  boxes, buttons, a scrolled window and a stack. Share available tab width,
  preserve theme-derived selection and hover colors, and retain detached
  windows, split panes and lifecycle callbacks (`#374`; supersedes the terminal
  Notebook trial from `#360`).

- Use a native GTK tree model, expanders, list view, and single selection for
  connections, preserving nested groups, search, context actions, expansion
  state, and private server-to-group drag targets. Keep the original sidebar
  background and highlight only rounded icon/title blocks (`#360`).

- Use `Gtk.TreeListModel`, `Gtk.TreeExpander`, and `Gtk.ListView` for the Notes
  tree while retaining nested groups, search, drafts, scope navigation, menus,
  and private drag targets (`#360`).

- Use `Gtk.Notebook` for Notes editor tabs, including native selection,
  reordering, and overflow with rounded tabs, a window-matched header, and a
  theme-derived highlight alongside GTK's blue underline on the selected tab
  while keeping drafts, save guards, and tab actions (`#360`).

- Use GtkSourceView 5 for native Notes line numbers while preserving plain-text
  content, saved visibility, and editor colors; install its runtime dependency
  on supported distributions (`#360`).

- Document the standard GTK control policy and inventory, including the
  confirmation required before introducing custom replacements and the
  existing Core/add-on architecture boundaries (`#360`).

- Use native GTK menus for local-terminal profiles, saved workspaces, terminal
  actions and their Split/Tab submenus, and the tab overflow selector. Preserve
  long titles, scoped dispatch, optional actions and submenu leave-to-close
  behavior; retire the obsolete sidebar menu-row builder (`#360`).

- Use standard GTK popover menus with native arrows for the main menu and
  notes import/export, retaining component-owned actions, optional statistics
  visibility, and write restrictions (`#358`).

- Add a local sandbox test runner with private Xvfb and D-Bus services so the
  complete GTK and SFTP suite can run without a desktop session. Use software
  rendering to avoid DRI3 warnings from the virtual display (`#300`).

- Store notes as plain text and retain only appearance controls in the notes
  toolbar. Preserve existing note content literally, including Markdown-looking
  characters; use round GTK window controls and normal-weight note titles (`#328`).

- Document separate prerelease and stable patch workflows, including the
  criteria for declaring a stable release (`#322`).

- Let built-in System, Light, and Dark appearance inherit GTK colors for
  menus, dialogs, buttons, text, selection, and error feedback. Keep only
  Termia layout rules and terminal-specific colors (`#302`).

- Render note, category, and tab context actions as standard GTK menu rows
  rather than custom framed buttons, with a uniform GTK foreground and no
  unintended initial focus outline (`#302`).

- Use shared eight-pixel spacing and sixteen-pixel insets around dialog action
  areas through the shared dialog-actions helper, including Save workspace
  (`#302`).

- Reuse the shared action-area layout in the independent Notes workspace
  footer (`#302`).

- Apply the shared dialog action layout to note renaming, category editing, and
  password prompts (`#302`).

- Apply the shared action layout to SFTP file selection, prompts, confirmations,
  and the Cancel/Reconnect row (`#302`).

- Apply the shared dialog action layout to Connection History and both
  Statistics dialogs (`#302`).

- Apply the shared action-area spacing and insets to the master-password
  unlock panel, note properties and export-protection windows, and update
  window (`#302`).

- Use standard GTK styling for the Clear history action instead of the
  destructive-action emphasis (`#302`).

- Reduce the bottom inset below the connection-history list while preserving
  the shared dialog action layout (`#302`).

- Apply the shared dialog action layout to the encryption-activation and
  update-install confirmation dialogs (`#302`).

- Replace the Personal/Servers selector and server dropdown with a hierarchical
  notes tree: Personal categories, then servers with notes and their categories.
  Keep categories scoped to their owner, omit empty Uncategorized groups, and
  identify note ownership in tabs. Number new note titles independently by
  scope. Select the existing title when renaming, keep the new-note action in
  the header while the list is hidden, and compact the note Properties window
  (`#309`). Eliminate excess Properties spacing and do not auto-select the first
  note when navigating the tree. Enable server
  creation controls only after a server is selected. Keep servers with saved
  empty categories and the active server scope in the tree, showing unsaved
  drafts under Uncategorized without persisting them. Match notes menus and
  Properties to the main menu's theme-aware surface (`#309`). Size the
  Properties window to its natural content height and inset the bottom Close
  button to eliminate excess blank space; prevent automatic selection of the
  title value. Reduce the outer vertical spacing and pad the details text
  inside its contrasting panel (`#309`).

- Document the initial Core and built-in add-on boundaries, their known pilot
  couplings, and the `app.py` composition-root exception (`#306`).

- Show the selected server in the notes window title instead of a small in-view
  scope label, and keep the general notes title for the unscoped workspace
  (`#289`).
- Replace the note editor's misleading Cancel button with Close tab, using the
  same save, discard, or keep-editing flow as the tab close icon (`#289`).
- Mark the active notes tab with a thin, full-width dark-blue underline without
  side glow; align notes search with the writing area and balance their divider
  insets (`#289`).
- Delineate the notes writing area with a theme-aware background, border, and
  comfortable text insets (`#289`).
- Replace the separate note-category manager with Add category and New note
  buttons together above search, plus folder-row actions for renaming,
  duplicating, and deleting categories; align Add category with the title-bar
  list toggle (`#289`).
- Start or resume an unsaved note draft when opening the notes workspace and
  size note properties to their content; make the notes tab scrollbar slim and
  translucent (`#289`).
- Mark source checkouts on the active development line as
  `0.6.0-beta.4-dev` (`#297`).
- Allow the notes list to collapse, keep multiple note editors open in tabs,
  preserve the active editor when its note list is empty, retain server
  associations, and let the list fill the available vertical space (`#289`).
- Open notes in a scoped list-and-editor view; keep import/export in the general
  manager and size note search for useful text (`#289`).
- Put note search above the sidebar's category groups and group the list toggle
  with the Import/Export overflow menu on the left of the notes window title
  bar (`#289`).
- Move the notes-list toggle outside the collapsible pane so hiding the list
  removes it completely and align the tab and editor left edges when the list
  is hidden (`#289`).
- Group personal notes under expandable category folders and linked notes in a
  virtual Server notes folder; search across all groups and align the note-tab
  bar with its editor when the list is hidden (`#289`).
- Compact note rows to one line, show server names beside linked note titles,
  add a read-only Properties dialog with metadata and content counts, reduce the
  list/editor gap, and suppress the tab bar's drag target outline (`#289`).
- Remove the separate note preview: selecting a note leaves the editor intact,
  and double-clicking opens or activates its editor tab (`#289`).
- Display note timestamps in local time without fractional seconds while
  retaining the full stored timestamp precision (`#289`).
- Replace note titles and metadata selectors in the editor with an automatically
  named draft and a plain text area; save non-empty edits automatically, while
  leaving empty drafts unpersisted (`#289`).
- Highlight the active note tab and allow open note tabs to be reordered by
  dragging, matching terminal-tab behavior (`#289`).
- Name new notes “New note” without an identifier; allow renaming from note
  tabs and list context menus, and move notes between categories by dragging
  them onto category folders (`#289`).
- Integrate note-tab close icons into the tab card, matching terminal tabs
  (`#289`).
- Always autosave non-empty note edits; close saved note tabs immediately, and
  ask whether to save or discard when closing a modified tab.
  Remove the Done action and give the modeless notes window normal window
  controls (`#289`).
- Explain plain-text and password-encrypted note exports directly in the export
  choice, and clarify that the export password is separate from local storage
  protection (`#289`).

### Fixed

- Declare Git as a Debian build dependency so update tests can run in a clean
  package-build environment without adding a runtime dependency (`#402`).

- Update CI checkout, Python setup and artifact actions to Node.js 24 releases
  while preserving the existing quality checks and coverage reports (`#400`).

- Distinguish credential-related UI message identifiers from persisted
  authentication fields, removing 34 Bandit false positives without changing
  displayed text, translations, saved settings or shortcut action IDs (`#396`).

- Compare Bandit dictionary-password findings by their individual key/value
  entries so unrelated edits do not reclassify existing findings as new.
  Preserve detection of changed entries and additional duplicates (`#393`).

- Ask for encrypted connection-import passwords, allow retry/cancellation,
  and retain the target profile's password, storage protection and notes (`#392`).
  Display password feedback using the theme's normal text color.
  Use the equivalent functools.cache decorator for translation caching.
  Name dialog messages for the unlock operation to distinguish UI text from credentials in static analysis.
  Skip import-dialog widget tests when no graphical display is available.

- Bound connection and notes file sizes, decoded content and encryption work.
  Preserve rejected originals and disable editing until recovery and restart
  instead of treating resource limits as corrupt-file recovery (`#392`).

- Reconnect the original SSH or failed local pane in place without closing
  sibling splits, replacing their layout, or cancelling unrelated transfers.
  Ignore obsolete terminal timer callbacks after retries (`#388`).

- Isolate the shutdown termination test from host process sessions so synthetic
  session IDs cannot cause environment-dependent failures (`#383`, `#385`).

- Fail Docker laboratory diagnostics when resource cleanup fails or visual
  probes leave terminal processes running; cover cleanup outcomes and reject
  previously completed manifests with cleanup errors (`#377`).

- Keep connection headers expandable without selecting them, retain compact
  rounded object selection and remove pressed-row inset shadows. Add native
  arrows to tab/server/group menus, clear initial menu highlighting, restore
  terminal-menu keyboard focus after VTE click handling, and close nested
  Split/Tab menus without hiding and reopening their parent (`#380`).

- Document the local Docker design, memory and lifecycle laboratory, including
  source provenance, safe operation and the validated menu/focus findings
  (`#380`).

- Release closed SFTP windows and dialogs after their workers stop, disconnect
  owned native signals without colliding with widget actions, and discard the
  traceback retained by Paramiko's optional Invoke import error (`#375`).

- Release retired tab/pane signal handlers without dropping pending process-exit
  accounting, defer split focus until mapping, and cover native widget lifetimes
  (`#374`).

- Restore the approved terminal tab strip with an automatically hiding horizontal
  scrollbar and a persistent native overflow menu refreshed only when opened.
  Retain private drag reordering, edge scrolling, active-tab reveal and the
  laboratory tab appearance (`#374`).

- Propagate mandatory setup-check failures so source upgrades install missing
  dependencies instead of reporting false success; cover setup failures and
  document Debian/Git Docker compatibility trials on Ubuntu 24.04 and 26.04
  (`#371`).

- Keep focus on the clicked terminal or split pane when opening its context
  menu and pasting; render configured Copy, Paste and New tab shortcuts using
  GTK accelerator syntax, including custom and disabled assignments (`#369`).

- Limit sidebar selection colors to a rounded icon/title block with horizontal
  padding instead of highlighting the entire row (`#360`).

- Keep floating tab drag previews at the full exterior tab size and original
  grab point, with the original translucent selection tint and opacity; only
  dim the source tab left in the bar. Retain existing reorder thresholds (`#360`).

- Restore the connections sidebar's original background and place Reattach to
  main window directly below Show/Hide status bar in detached terminals (`#360`).

- Reduce terminal-tab label padding and remove the native header's dark bottom
  border for a more compact tab bar. Suppress the dark bottom shadow when
  hovering inactive terminal tabs, reduce the gap between tabs, and give close
  buttons a larger circular hover (`#360`).

- Investigate GTK Notebook drag timing with deferred moves and isolated
  overflow stress coverage (`#360`); the final terminal strip uses the approved
  GTK box/stack composition instead of Notebook, retaining private dragging,
  edge scrolling and stale-drop guards (`#374`).

- Keep Notes GTK tests safe in headless CI while retaining GtkSourceView
  integration coverage on a private display (`#360`).

- Keep Notes category rows alive until a left-button drag can start, restoring
  category moves into other groups in the native tree (`#360`).

- Defer Notes tree selection and context-menu opening until GTK finishes the
  right-click event, avoiding a crash when targeting another note (`#360`).

- Restore terminal input after leaving the native Split or Tab submenu and
  dismissing the terminal context menu with an outside click (`#360`).

- Use a standard GTK menu for groups and subgroups, preserving scoped start,
  subgroup creation, editing and confirmed deletion, write restrictions and
  popup lifetime across tree rebuilds (`#360`).

- Use a standard GTK menu for servers, Favorites and Recent connections,
  retaining scoped actions, optional SFTP visibility, write restrictions and
  sidebar scrolling while rejecting stale targets (`#360`).

- Use a standard, reusable GTK menu for note categories, retaining scoped
  rename, duplicate and delete actions, keyboard access and write restrictions
  across tree rebuilds (`#360`).

- Use a standard, reusable GTK menu for saved-note list actions, preserving
  note targets across row rebuilds and saves, click anchoring and storage
  permissions (`#360`).

- Use a standard GTK menu anchored to the right-click position on note tabs,
  preserving rename permissions, focus and popup lifetime around dialogs, and
  rejecting stale targets (`#360`).

- Anchor the terminal-tab context menu to the right-click position and use a
  standard GTK menu, retaining tab actions and rejecting stale targets (`#360`).

- Reduce the snippet manager's default width by 25% to 795 logical px while
  retaining its three columns, actions, and resizable layout (`#330`).

- Open the snippet editor at a compact, resizable 600 × 560 logical px size,
  constrain selectors with long labels, and restore the manager's previous
  size after saving, cancelling, or closing the editor (`#355`, `#330`).

- Wait for the previous SFTP service to finish cleanup before reconnecting,
  retry a failed backend close once off the UI thread, and report exhausted
  cleanup without discarding unresolved resources or polling indefinitely.
  Keep a single exit handler across local/SSH split retries and ignore exits
  from inactive or removed panes (`#319`).

- Retain verified terminal process-group identities through tab disconnection,
  closure, and application shutdown, including forced cleanup after the leader
  exits. Observe SCP/SFTP cleanup for a bounded period, and report failed or
  timed-out cleanup without marking it successful. Reuse captured identities
  when terminal-exit callbacks run, release expired uncertain sessions, and
  track the refreshed SCP identity through cancellation (`#351`).
- Select SFTP directories with one click so they can be downloaded, and open
  them with a double-click or keyboard activation (`#326`).

- Use neutral, theme-aware required-field markers and hints in connection and
  workspace forms, explain the marker in the workspace dialog, and use normal
  menu text for deleting servers, local terminals, and workspaces (`#342`).

- Use standard GTK controls in the independent Notes window, restore it before
  presenting, and defer server-menu activation until after popover focus settles
  on Wayland. Preserve reusable notes and application shutdown (`#339`).

- Keep terminal tabs, note tabs, and saved-note rows private during drag-and-drop
  so text fields cannot insert their internal IDs. Preserve tab reordering and
  moving saved notes between categories. Skip the two widget integration checks
  when no graphical display is available (`#329`).

- Apply the shared action-area insets once in the startup master-password panel,
  reduce excess button spacing, and show neutral error text while retaining its
  reserved message row (`#336`).

- Show a line number on a newly created empty note line immediately after
  pressing Enter, and apply the dark editor background on a fresh profile
  (`#328`).

- Focus the notes editor after the Notes window opens (`#328`).

- Preserve custom tab titles when saving and restoring the previous session (`#324`).

- Prevent dragging a saved server onto the sidebar search field from inserting
  its internal ID as search text (`#299`).

- Let System appearance inherit GTK menu, popover, and note-properties surfaces
  instead of combining a forced light Termia menu with dark desktop controls.
  Derive GTK's dark variant from GNOME's actual system scheme instead of a
  fixed false preference, and update it when GNOME changes while Termia is
  open. Keep isolated test profiles from overriding GTK and GNOME
  configuration (`#311`).

- Show the export/import password prompt correctly with GTK 4 password fields
  instead of calling an unsupported placeholder method (`#289`).
- Keep note-tab close controls independently clickable after saving by avoiding
  nested GTK buttons (`#289`).
- Keep server-note opening responsive, add an explicit Save action and safe
  discard for incomplete drafts, and keep custom/test notes files beside their
  connection files
  (`#289`).

### Refactored

- Keep the SFTP explorer independent from terminal windows and scope its modal
  prompts to SFTP. Coalesce progress updates, show per-file MB and recent MB/s
  with accumulated MB in a tooltip, format file-list sizes in B/kB/MB/GB,
  reject unexpected byte counts, classify
  failures without exposing backend details, preserve connections when cancelling ordinary
  prompts, and observe asynchronous cancellation/cleanup before reconnecting
  (`#327`).

- Move aggregate statistics recording behind a narrow session observer and
  isolate SFTP launching from terminal-session orchestration (`#304`).

### Removed

- Drop write-only terminal session/pane timer-ID fields while retaining all
  GLib timer scheduling and lifecycle callbacks (`#367`).

- Remove the unused dialog-button `last` parameter and test-only note-search
  and singular host-key parsing helpers; exercise the active presenter and
  plural parser instead (`#367`).

- Remove the legacy Notes list renderer, row/header builders, old row-context
  handler and orphaned category CSS; migrate their behavior checks to the
  native GTK tree (`#367`).

- Retire test-only custom Notes menu helpers and the old tab-overflow click
  handler with their three obsolete tests; retain native-menu coverage (`#367`).

- Remove confirmed unused Notes helpers, the superseded prompt settings method,
  an unregistered session-disconnect handler, unused imports and orphaned menu
  CSS; record the evidence and deferred cleanup candidates (`#367`).

## 0.6.0-beta.3 - 2026-09-30

Changes merged after `0.6.0-beta.2`. This release introduces reusable command
snippets and category management, alongside fixes and documentation updates.

### Added

- Add reusable command snippets with scoped storage, category search, explicit
  variable entry, and mandatory command preview before terminal execution
  (`#270`).
- Add persistent snippet-category management, including empty categories,
  renaming, duplication, and non-destructive deletion (`#288`).

### Fixed

- Keep category-tile selection inside the rounded card instead of highlighting
  its square FlowBox wrapper (`#288`).
- Fix category listing visibility and preserve category selection when creating
  snippets (`#288`).
- Reuse persistent snippet windows and suppress selection callbacks while
  rebuilding lists, avoiding native GTK/Gallium lifecycle crashes and hangs
  during repeated editing and execution (`#270`).
- Treat normal nonzero remote SSH shell exits as clean closures instead of
  incorrectly offering reconnection (`#285`).

### Changed

- Publish the 0.6.0-beta.3 application and Debian package versions, and clarify
  the package description as a terminal workspace and SSH connection manager
  (`#295`).
- Document configuration compatibility across versions and recommend backups
  and isolated test profiles (`#293`).
- Redesign snippet management as a three-column view with category counts,
  snippet lists, and a read-only command preview; place category and snippet
  creation actions above their columns, with selection guidance beneath the
  list, while retaining global search and category creation from the editor
  (`#288`).
- Simplify the Manage snippets header and group its actions by purpose (`#288`).
- Remove the redundant Manage categories heading and add a footer Cancel action
  that returns to snippet management (`#288`).
- Show persistent categories as uniform icon tiles with snippet counts in the
  category-management view (`#288`).
- Keep “snippet” terminology in the Spanish and Catalan interface and docs
  (`#288`).
- Migrate connection storage to schema 2 for command snippets, preventing older
  versions from silently discarding snippet data (`#270`).
- Mark the active source checkout as `0.6.0-beta.3-dev` for the next release
  development cycle (`#284`).
- Clarify the beta.2 feature list and release status in the root and localized
  README files (`#282`).

## 0.6.0-beta.2 - 2026-09-17

Changes merged after `0.6.0-beta.1`.

### Added

- Add About-based update checks, verified Debian downloads and explicit
  installation, and guarded Git release updates through independent adapters
  with cancellable preparation (`#274`).
- Add a native SFTP explorer with an isolated transport/service/UI architecture,
  directory navigation, uploads/downloads, progress, cancellation, and confirmed
  file operations without changing terminal layouts or SCP behavior (`#269`).

### Fixed

- Keep saved-password preference sensitivity independent from the close-confirmation setting, require its keybinding to be configured, and explain unavailable options (`#272`).

### Changed

- Clarify the active `0.6.0` beta cadence in `ROADMAP.md`.
- Document release-development branches and keep `main` aligned with published
  releases (`#275`).
- Mark the active source checkout as `0.6.0-beta.2-dev` until the next release
  is prepared (`#277`).

## 0.6.0-beta.1 - 2026-09-15

Changes merged after `0.5.0-beta.3` (released 2026-07-30).

### Changed

- Match the split-pane drag area background to the configured terminal background.

### Added

- Add a validated per-transfer SCP destination prompt, defaulting to
  `/tmp/.termia`, with non-destructive destination checks, safe remote command
  quoting, and phase-specific failure feedback (`#256`).
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

- Isolate SCP process trees, cancel them safely from every window-close path,
  prevent late transfer phases, and distinguish cancelled outcomes from errors
  with privacy-safe lifecycle diagnostics (`#253`).
- Open the SCP file selector correctly from saved-server context menus while
  preserving session-window ownership for terminal context actions (`#251`).
- Keep connected and failed sibling splits open when closing an original pane
  that is waiting for reconnection (`#249`).
- Remove explicitly disconnected original split panes and clear completed local
  and SSH process identities before later window or application cleanup (`#247`).
- Restore hidden workspace tabs' split proportions when GTK first allocates
  them so every pane is visible without requiring interaction (`#245`).
- Preserve ancestor divider positions and split only the selected pane 50/50
  when adding a terminal to an existing nested layout.
- Avoid showing the same SSH disconnected notification twice when closing an
  active tab.
- Treat managed terminal exits during application shutdown as intentional,
  suppress reconnect notifications, and avoid duplicate forced termination
  requests (`#233`).
- Inspect SSH known-host files asynchronously so connection and SCP startup
  cannot block the GTK interface while `ssh-keygen -F` runs (`#230`).
- Match OpenSSH known-host resolution for non-standard SSH ports to avoid false
  new-host prompts when a compatible entry is stored without the port (`#258`).
- Add an explicit SCP fingerprint dialog for unknown endpoints, with visible
  identity details, confirmation-gated known_hosts persistence, and safe
  cancellation (`#260`).
- Use one native Termia password dialog for SCP fallback authentication instead
  of repeated system SSH_ASKPASS prompts, while keeping the password in memory
  only for the active transfer (`#262`).
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

## Initial development (0.1.0, untagged) - 2026-06-03 to 2026-06-13

- Introduce Termia with application version `0.1.0` and establish the
  source-checkout launcher, dependency checks, documentation, and issue
  templates. No `0.1.0` or `0.1.0-alpha.1` Git tag exists; the earliest tag in
  the repository is `v0.2.0-alpha.1`, and the first GitHub release is
  `v0.3.0-alpha.1`.
