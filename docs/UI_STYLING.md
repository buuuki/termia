# Current UI styling inventory

This inventory records the current sources and ownership of Termia's visual
rules. It is a baseline for issue #302, not a proposed palette or a promise of
custom themes.

## Quick reference

| Source | Owns | Must not be changed by this inventory |
|---|---|---|
| GTK/GNOME | System surfaces, text, borders, selection, focus, and system appearance | The desktop theme or GTK-managed widget behavior |
| Termia | Scoped structural rules: layout insets, dimensions, and component selectors | GTK-managed application colors or VTE internals |
| Terminal settings | VTE foreground, background, ANSI palette, prompt, and split divider | Application menus, dialogs, or sidebar chrome |

## Appearance modes

Termia's application appearance is selected in General preferences.

| Mode | GTK variant | Termia surface colors |
|---|---|---|
| System | Follows GNOME `color-scheme`; resets the app override when the scheme is unknown | Inherited from GTK |
| Light | Requests GTK's light variant | Inherited from GTK |
| Dark | Requests GTK's dark variant | Inherited from GTK |

The shared application CSS provider is replaced when the appearance changes so
rules from an earlier mode do not remain active.

## Current visual sources

### GTK and GNOME tokens

Most application surfaces remain GTK-owned and use theme tokens rather than
literal colors. The shared CSS currently consumes:

| Token | Current use |
|---|---|
| `@theme_bg_color` | General backgrounds, cards, and note-properties content |
| `@theme_base_color` | Note-properties content and text surfaces outside the Notes editor |
| `@theme_fg_color` | Tab and scrollbar interaction feedback |
| `@theme_selected_bg_color` / `@theme_selected_fg_color` | Sidebar selection, category drop target, and active-pane feedback |
| `@headerbar_backdrop_color` | Header and session-tab background |
| `@borders` | Note editor and card borders |

GTK continues to own normal button, hover, pressed, disabled, and keyboard
focus rendering unless Termia adds a narrowly scoped component rule.

### Explicit Termia values

| Value or rule | Components | Notes |
|---|---|---|
| `@theme_selected_bg_color` | Active note-tab underline | Inherited from GTK |
| `alpha(...)` GTK expressions | Hover, active, dragging, selected, scrollbar, and required-hint feedback | Derived from the active GTK theme |
| `#001B33` and white text defaults | Notes writing surface | User may override these through saved Notes appearance preferences |
| `#0065BF` on `#000D1A` | Notes line-number gutter | Scoped to the Notes editor |

Termia also defines component dimensions, padding, margins, border radii, and
separator treatment in `src/termia/styles.py`.

### Terminal-only values

Terminal foreground/background, ANSI palettes, prompt color, and the split
separator color are user-configurable terminal settings. The split divider
intentionally combines the terminal background for its drag area with the
configured separator color for its thin visual line. These values are not
application-theme tokens.

## Component ownership

This table describes **appearance ownership**. It does not classify whether a
component's interaction uses a standard GTK control. See the
[GTK control policy and inventory](GTK_CONTROLS.md) for that classification.

| Component | Current owner | Current implementation |
|---|---|---|
| Main and context menus | GTK | `styles.py`, menu classes |
| Dialogs | GTK | Individual dialog builders |
| Header and session tabs | GTK tokens with Termia spacing rules | `styles.py` |
| Note tabs and editor | GTK chrome with saved Notes appearance preferences, a scoped line-number gutter, and Termia underline, borders, and spacing | `notes_dialogs.py`, `styles.py`, and settings |
| Sidebar selection and category drop target | GTK selection tokens | `styles.py` |
| Split panes | Terminal preferences | `styles.py` and terminal settings |
| Required-field marker and hint | GTK label foreground and secondary text derived from `@theme_fg_color` | `connection_dialogs.py` and `styles.py` |
| Snippet manager and category tiles | GTK window and buttons with Termia layout and selection rules | `snippet_dialogs.py` and `styles.py` |

### Notes window layout

These are the current Notes window settings in `src/termia/notes_dialogs.py`.
They describe the existing implementation, not a reusable window contract:

- Notes is a reusable, independent, non-modal `Gtk.Window` associated with
  the application. It has no transient parent. Closing it hides the workspace;
  application shutdown destroys it. The default size is **1240 × 660 logical
  px**, not a fixed size. Its root content has 14 px margins on all sides and
  10 px vertical spacing.
- Its `Gtk.HeaderBar` supplies standard GTK title buttons. On the left, the
  notes-list toggle, New note, and Import/Export overflow button appear in
  that order, with 4 px between them and an 8 px start margin. The overflow
  button is hidden for server-scoped notes.
- The notes-list pane starts at **330 logical px** and restores its last width
  after being hidden. Its search entry requests at least 300 px and has a 6 px
  end margin. The editor side keeps a 6 px inset beside the divider while the
  list is visible; hiding the list removes that inset so tabs and editor align.
- Note tabs stay above the editor toolbar. The editor text has 12 px internal
  margins on all sides. The editor surface has a 1 px theme border and an 8 px
  corner radius. The editor's default foreground and background are white and
  `#001B33`; saved Notes appearance preferences can replace them.
- `termia-notes-window` marks the window; no window-frame CSS rule currently
  targets that class. `termia-note-tab`, `termia-notes-tab-scroller`, and
  `termia-notes-editor` have scoped rules in `src/termia/styles.py`. The
  `termia-notes-toolbar` and `termia-notes-list` rules are applied by the
  editor appearance provider in `notes_dialogs.py`. GTK owns ordinary button
  and title-control colors, focus, and interaction states.

The protected behavior, including focus, reuse, resizing, and the title-bar
control order, is recorded in [Regression Checks](REGRESSION_CHECKS.md#notes).

### Snippet manager layout (#346)

These are the intended layout rules for the snippet manager. They describe its
current design, not a reusable component API:

- The manager uses a standard, independent GTK window. Its content keeps the
  category, snippet-list, and preview columns. **Create snippet** is aligned
  to the left edge above the snippet list.
- On **Manage categories**, **Back to snippets** is at the top left. The
  **Add category**, **Rename category**, **Duplicate category**, and
  **Delete category** buttons form a left-aligned row directly below it, in
  that order, with 6 px between buttons. The page has 16 px outer margins and
  10 px vertical spacing. **Cancel** stays alone at the bottom right.
- Each framed category card is intended to measure **170 × 112 logical px**.
  A window resize changes how many cards fit on a row; it must not stretch or
  shrink the cards. The grid starts at the top left, uses 12 px between rows
  and columns, wraps onto more rows, and scrolls vertically without a
  horizontal scrollbar. The card icon, name, and snippet count are centered;
  long names are ellipsized.
- The card uses `termia-snippet-category-tile` on the `Gtk.FlowBoxChild` and
  `termia-snippet-category-frame` on its `Gtk.Frame`. Their scoped CSS in
  `src/termia/styles.py` supplies rounded corners and selection feedback from
  GTK theme colors. GTK continues to style the buttons and keyboard focus.

Implementation detail to verify before calling the size invariant enforced:
`src/termia/snippet_dialogs.py` currently uses
`frame.set_size_request(170, 112)`. GTK treats this as a minimum request, so
that call alone does not guarantee an exact 170 × 112 allocation. The grid's
current start alignment avoids ordinary stretching, but the fixed-size rule
still needs visual validation and, if necessary, an explicit layout fix.

### SFTP explorer (#327)

- The explorer is an independent, non-modal application window without a
  transient parent. Existing transfer ownership still links its cleanup to the
  originating terminal session or application.
- A private GTK window group confines modal SFTP prompts/selectors to the
  explorer. Other terminal and application windows remain accessible.
- The default size remains 820 × 560 logical px. Cancel, Reconnect SFTP and
  Disconnect remain right-aligned in that order.
- File-list sizes use B, kB, MB or GB automatically, with one decimal for
  scaled units. Transfer progress remains in MB and speed in MB/s.
- Progress text includes the filename, per-file MB, recent MB/s and completed
  files. Accumulated operation MB appear only in the tooltip. Long text is
  ellipsized with the full text in a tooltip. Speed uses a recent three-second
  window across files and resets for each operation.
  Folder totals remain unknown while the tree is discovered during transfer.

## Known inconsistencies and decisions pending

- Termia does not yet have a complete semantic palette for its own components.
  It mixes GTK tokens, a small number of literals, and per-component spacing.
- The shared `headerbar` selector is broad within Termia's application CSS;
  any standardization must keep future selectors scoped to Termia classes when
  practical.
- No custom theme editor, saved palette, or terminal-palette change is in the
  scope of #302.

## Validation baseline

Before changing a visual rule, verify the relevant checks in
[REGRESSION_CHECKS.md](REGRESSION_CHECKS.md), especially application
appearance, menus and popovers, tabs, dialogs, selection, focus, and split
divider behavior. Test System, Light, and Dark appearance without changing the
desktop GTK theme or terminal palette.
