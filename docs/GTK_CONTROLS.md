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
| 13 | Notes editor tab bar | `Gtk.Notebook` | `src/termia/notes_dialogs.py`; shared editor, draft identity, save guards, close action, and tab menu |
| 14 | Connections tree | `Gtk.TreeListModel`, `Gtk.TreeExpander`, `Gtk.ListView`, and `Gtk.SingleSelection` | `src/termia/sidebar.py`, `src/termia/sidebar_projection.py`; Termia supplies projected identities, filtering, expansion preferences, context actions, and private group drop targets; GTK owns selection, disclosure, and navigation |
| 15 | Notes tree | `Gtk.TreeListModel`, `Gtk.TreeExpander`, `Gtk.ListView`, and `Gtk.SingleSelection` | `src/termia/notes_dialogs.py`; Notes supplies hierarchy data, scope actions, saved expansion, menus, and private drag targets |
| 16 | Notes line-number gutter | `GtkSource.View` from GtkSourceView 5 | `src/termia/notes_dialogs.py`; saved visibility and Notes colors |
| 20 | Terminal tab overflow selector | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/tabs.py`; visual order and active marker |

The two unnumbered menus were completed under
[issue #358](https://github.com/buuuki/termia/issues/358). Numbers 1–20 follow
issue #360. Standard menu presentation does not remove the application logic
listed in the final column.

Item 16 uses the standard GtkSourceView widget, which extends GTK 4 and requires
an additional runtime package; it is not a control built into GTK 4 itself.

## Existing custom compositions in the reviewed inventory

| # | Surface | Current composition and responsibility | Source | Review status |
|---:|---|---|---|---|
| 12 | Terminal tabs | `Gtk.Box`, `Gtk.Stack`, `Gtk.ScrolledWindow` and native buttons; Termia owns tab selection and reordering | `src/termia/app.py`, `src/termia/tabs.py` | Explicitly approved laboratory design under #374; preserve overlay scrolling, down-arrow selector and tab appearance |
| 17 | Shortcut capture control | `Gtk.Box`, buttons, and key controllers; Termia captures and validates assignments | `src/termia/keybinding_preferences.py` | Retain as a justified custom capture: GTK 4 has no supported standalone recorder with equivalent behavior |
| 18 | Grouped temporary notifications | `Gtk.Overlay`, `Gtk.Revealer`, frame, icon, and label; Termia owns grouping, severity, and timing | `src/termia/app.py`, `src/termia/notifications.py` | Retain as a justified composition of standard GTK widgets; GTK has no equivalent grouped notification control |
| 19 | Startup unlock panel | In-window `Gtk.Overlay` with `Gtk.PasswordEntry`; Termia owns blocking, focus, and unlock flow | `src/termia/app.py` | Retain as a justified composition of standard GTK widgets; no single GTK 4 control preserves the full in-window interaction |

Item 12 retains the laboratory composition by explicit requester decision under
#374: its horizontal overlay scrollbar, down-arrow selector, tab close buttons
and drag appearance take precedence over the Notebook trial from #360. The
tradeoff is Termia-owned tab selection, geometry, drag reordering and reveal,
covered by tab, lifecycle and pointer regressions. GTK still owns the scrollbar
and native popover menu; this approval does not extend to other custom controls.
Item 14 retains its native GTK control. Items 17–19 have documented reasons for
retaining their current compositions.

### Item 17: justified capture exception

`KeybindingCaptureRow` is shared by preferences and the snippet editor. It uses
standard GTK buttons and event/focus controllers, but Termia owns the recording
interaction: begin capture, normalize the key
combination, cancel with Escape or focus loss, clear the assignment, and pass
the result to conflict and storage validation. `Gtk.ShortcutController` handles
shortcut activation, while `Gtk.ShortcutLabel` only displays one. The GTK 4
widget that can edit accelerators, `Gtk.CellRendererAccel`, is deprecated since
4.10 and belongs to the deprecated cell-renderer/tree-view interface; [GTK
recommends application-owned capture instead](https://docs.gtk.org/gtk4/class.CellRendererAccel.html).
Retain the current capture composition under issue #360. Revisit it if GTK
provides a supported standalone recorder that preserves these behaviors.

### Item 18: justified grouped-notification composition

The in-window notification panel already uses standard `Gtk.Overlay` and
`Gtk.Revealer` widgets with a frame, icon, and label. Termia groups every
message in arrival order, including duplicates, shows the highest severity,
and restarts its five-second hide timer for each new message. The overlay does
not intercept terminal input. [GTK's deprecated `Gtk.InfoBar` documentation](https://docs.gtk.org/gtk4/class.InfoBar.html)
recommends composing `Gtk.Revealer` with ordinary widgets because GTK has no
replacement info-bar control. [`Adw.ToastOverlay`](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/method.ToastOverlay.add_toast.html)
belongs to libadwaita, an additional dependency; it queues separate toasts by
default and would still need Termia-owned grouping and severity logic to
preserve this interaction.
Retain the current composition under issue #360. Revisit it only if a supported
control can preserve the protected behavior in the regression checklist.

### Item 19: justified startup-unlock composition

The password field is the standard `Gtk.PasswordEntry`; the window is a
`Gtk.ApplicationWindow`. Termia composes standard `Gtk.Overlay`, `Gtk.Frame`,
labels, boxes, and buttons to keep the unlock panel centered inside that window.
Application logic disables the underlying content and header actions, directs
focus to the password field, and handles Enter, Escape, validation, errors, and
cancellation. The protected behavior requires the panel to follow the Termia
window across monitors while window-management actions remain available.

A modal [`Gtk.Dialog`](https://docs.gtk.org/gtk4/class.Dialog.html) is a separate
top-level window and is deprecated in GTK 4.10. A
[`Gtk.Popover`](https://docs.gtk.org/gtk4/class.Popover.html) is attached to a
widget and its modal mode automatically hides on outside interaction; that
would change the current centered, persistent unlock flow.
[`Adw.Dialog`](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Dialog.html)
can provide an in-window dialog, but requires libadwaita and an `Adw.Window` or
`Adw.ApplicationWindow`, rather than Termia's current GTK window. No single
control in the supported GTK 4 baseline provides the same interaction without
such changes. Retain this GTK composition under issue #360; revisit it if the
window architecture or supported controls change. This is a justification for
composing standard GTK widgets, not a claim that GTK lacks a password control.

## Review before changing a control

For a listed or new UI surface, identify the GTK control intended to own its
interaction and the behavior Termia must retain. If a proposed change would
replace a standard control with a custom composition, or implement an
interaction covered by an appropriate standard control, report the reason,
alternatives, affected components, and likely regressions and obtain explicit
requester confirmation before editing code. Update this inventory when the
implementation changes; apply the relevant checks in
[Regression Checks](REGRESSION_CHECKS.md).
