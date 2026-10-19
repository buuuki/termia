# GTK control policy and inventory

Termia uses standard GTK controls for UI interactions when GTK provides an
appropriate control. Before replacing a standard control with a custom one, or
building custom interaction where a standard control is appropriate, explain
the reason, affected behavior, GTK alternatives, and regression risks to the
requester and obtain explicit confirmation. Preserve existing behavior and
validate the affected interaction before adopting any replacement.

This policy applies to new work. The existing custom compositions below are a
record of current implementation, not an instruction to replace them without
functional comparison or a standing exception for future custom controls.
Issue [#360](https://github.com/buuuki/termia/issues/360) tracks that comparison.

## Classification

- **Standard control:** GTK owns the interaction pattern through a purpose-made
  widget or menu model. Termia may supply actions, data, labels, and scoped
  styling without making the control custom.
- **Custom composition:** Termia assembles GTK primitives and implements the
  interaction pattern itself. Using `Gtk.Box`, `Gtk.Button`, `Gtk.Stack`, CSS, or
  GTK theme colors does not by itself make the resulting tab bar, tree, or other
  composite a standard control.
- **Custom behavior on a standard control:** Keep this visible in the inventory.
  For example, a `Gtk.PopoverMenu` remains a standard menu while Termia owns
  action validation or additional pointer handling.

The inventory describes interaction ownership, not the origin of colors. See
[the UI styling inventory](UI_STYLING.md) for appearance ownership and
[the regression checklist](REGRESSION_CHECKS.md) for behavior to preserve.
Control changes must also respect [the Core/add-on architecture](architecture/overview.md)
and [its dependency rules](architecture/addons.md): `app.py` composes concrete
add-ons, while other Core modules use narrow, add-on-neutral contracts. Choosing
a standard GTK control does not justify crossing those boundaries.

## Standard GTK controls in the reviewed inventory

| # | Surface | Standard GTK control | Source and Termia-owned behavior |
|---:|---|---|---|
| — | Main menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/main_menu.py`; actions and submenu reset |
| — | Notes Import/Export menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/notes_dialogs.py`; scope and write guards |
| 1 | Terminal context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/terminal_menus.py`; scoped actions |
| 2 | Terminal Split submenu | Nested GTK menu model | `src/termia/terminal_menus.py`; submenu leave handling |
| 3 | Terminal Tab submenu | Nested GTK menu model | `src/termia/terminal_menus.py`; session-dependent actions and leave handling |
| 4 | Server, Favorites, and Recent context menus | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/sidebar.py`; scoped target validation |
| 5 | Group and subgroup context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/sidebar.py`; write guards and target validation |
| 6 | Local-terminal profile context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/sidebar.py`; scoped actions |
| 7 | Saved workspace context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/sidebar.py`; scoped actions |
| 8 | Terminal-tab context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/tabs.py`; clicked-session validation |
| 9 | Note-list item context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/notes_dialogs.py`; note identity and write guards |
| 10 | Notes category context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/notes_dialogs.py`; category identity and write guards |
| 11 | Notes editor-tab context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/notes_dialogs.py`; saved-note and draft identity |
| 20 | Terminal tab overflow selector | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/tabs.py`; visual order and active marker |

The two unnumbered menus were completed under
[issue #358](https://github.com/buuuki/termia/issues/358). Numbers 1–20 follow
issue #360. Standard menu presentation does not remove the application logic
listed in the final column.

## Existing custom compositions in the reviewed inventory

| # | Surface | Current composition and responsibility | Source | Review status |
|---:|---|---|---|---|
| 12 | Terminal tab bar | `Gtk.Box` and `Gtk.Stack`; Termia owns selection, ordering, drag, overflow visibility, and session lifecycle | `src/termia/app.py`, `src/termia/tabs.py` | Compare `Gtk.Notebook` with the full behavior before any replacement |
| 13 | Notes editor tab bar | GTK boxes and buttons; Termia owns activation, closing, ordering, and draft identity | `src/termia/notes_dialogs.py` | Compare native tab controls with the full behavior |
| 14 | Connections tree | `Gtk.Expander` and boxes; Termia owns hierarchy, selection, navigation, drag, and expansion state | `src/termia/sidebar.py` | Compare `Gtk.TreeListModel` and `Gtk.TreeExpander` based views with the full behavior |
| 15 | Notes tree | `Gtk.ListBox` rows and indentation; Termia owns hierarchy, selection, expansion, and note moves | `src/termia/notes_dialogs.py` | Compare native tree controls with the full behavior |
| 16 | Notes line-number gutter | `Gtk.DrawingArea` aligned with `Gtk.TextView`; Termia draws line numbers | `src/termia/notes_dialogs.py` | Existing feature-specific GTK composition |
| 17 | Shortcut capture control | `Gtk.Box`, buttons, and key controllers; Termia captures and validates assignments | `src/termia/keybinding_preferences.py` | Existing feature-specific GTK composition |
| 18 | Grouped temporary notifications | `Gtk.Revealer` and child widgets; Termia owns grouping and timing | `src/termia/app.py`, `src/termia/notifications.py` | Existing feature-specific GTK composition |
| 19 | Startup unlock panel | In-window `Gtk.Overlay` with standard password entry; Termia owns blocking and focus | `src/termia/app.py` | Existing feature-specific GTK composition |

Items 12–15 were compared with native tab or tree controls under issue #360;
equivalent behavior has not been demonstrated. Items 16–19 currently remain
feature-specific compositions. This status is not a claim that GTK lacks useful
primitives for them.

## Review before changing a control

For a listed or new UI surface, identify the GTK control intended to own its
interaction and the behavior Termia must retain. If a proposed change would
replace a standard control with a custom composition, or implement an
interaction covered by an appropriate standard control, report the reason,
alternatives, affected components, and likely regressions and obtain explicit
requester confirmation before editing code. Update this inventory when the
implementation changes; apply the relevant checks in
[Regression Checks](REGRESSION_CHECKS.md).
