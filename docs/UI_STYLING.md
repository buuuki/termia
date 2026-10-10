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
| `@theme_base_color` | Note editor and text surface |
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
| `@error_color` | Required-field marker and hint | Inherited from GTK |
| `alpha(...)` GTK expressions | Hover, active, dragging, selected, and scrollbar feedback | Derived from the active GTK theme |

Termia also defines component dimensions, padding, margins, border radii, and
separator treatment in `src/termia/styles.py`.

### Terminal-only values

Terminal foreground/background, ANSI palettes, prompt color, and the split
separator color are user-configurable terminal settings. The split divider
intentionally combines the terminal background for its drag area with the
configured separator color for its thin visual line. These values are not
application-theme tokens.

## Component ownership

| Component | Current owner | Current implementation |
|---|---|---|
| Main and context menus | GTK | `styles.py`, menu classes |
| Dialogs | GTK | Individual dialog builders |
| Header and session tabs | GTK tokens with Termia spacing rules | `styles.py` |
| Note tabs and editor | GTK tokens with Termia underline, borders, and spacing | `styles.py` |
| Sidebar selection and category drop target | GTK selection tokens | `styles.py` |
| Split panes | Terminal preferences | `styles.py` and terminal settings |
| Required-field marker | GTK `@error_color` token | `connection_dialogs.py` and `styles.py` |

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
