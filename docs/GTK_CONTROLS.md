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

The Retron appearance editor (#486) reuses the non-modal `DialogWindow` shell
and a native titlebar `Gtk.Button`, visible only while Retron is selected.
The titlebar and General preferences share the same editor instance,
with the button disabled while the connection-unlock overlay is active.
The editor uses a native `Gtk.ListBox`, `Gtk.DropDown`, `Gtk.ColorDialogButton`,
`Gtk.Scale`, `Gtk.CheckButton`, `Gtk.Switch` and scrolling containers.
Numeric sliders display their values and retain native keyboard adjustment.
The property scroller uses GTK's automatically hiding overlay scrollbar and
reserves a 40px content end margin to keep override checkboxes clear of it.
The editor is a non-transient application window with a native `Gtk.HeaderBar`
requesting minimize, maximize and close controls. Its runtime still owns
shutdown and cancellation; GTK owns window movement and window-state actions.
GTK owns control interaction. Termia owns per-property inheritance, the single
editor instance, Save/Apply/Cancel transaction and deferred preview cleanup.
The titlebar launcher (`tool_launcher.py`) uses native `Gtk.MenuButton`,
`Gtk.Popover`, adaptive `Gtk.FlowBox` and icon/label buttons. GTK owns wrapping,
focus, activation and dismissal; Termia owns availability and deferred dispatch.
The Notes tile reuses the existing management window; each management
invocation hides its native sidebar while retaining its toggle and width.
Diagnostics (`diagnostics_view.py`) reuses `DialogWindow`, labels, grids,
expanders, text views and scrollers; its controller owns sampling lifetime.
Named configurations use a native `Gtk.DropDown` with bounded labels and standard
buttons. Save as and Rename reuse `DialogWindow` with `Gtk.Entry`; unsaved-switch
and delete confirmations use `Gtk.AlertDialog`. Termia owns name validation,
selection IDs, atomic persistence and cancellation of pending dialogs on close.

Encrypted connection import uses the shared modal `DialogWindow` with
`Gtk.PasswordEntry` and native response buttons in `src/termia/config_actions.py`.
GTK owns dialog presentation; Termia validates the password, handles retry and
cancellation, and rechecks storage limits and write permission before import.

Issue #335 migrates existing forms from deprecated `Gtk.Dialog` to the shared
`Gtk.Window` composition in `dialog_window.py`, retaining their content and
response actions. Termia owns response dispatch, Escape and close handling;
GTK owns window modality, focus and default-widget activation. This is custom
behavior on a standard window, not a new GTK dialog type. Text selectors use
native `Gtk.DropDown` controls; `choice_widgets.py` maps stable stored IDs to
displayed strings and configures bounded labels with native list-item factories.

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
| — | Retron secondary windows | Existing GTK windows, headers, lists, scrolling regions and native controls | `theme_styles.py` shares scoped frames and palette rules; views add presentation roles only. `DialogWindow` exposes `termia-dialog-panel` around content and actions, with `termia-dialog-content` inside. Native message alerts stay separate; Notes retains its saved editor colors and GTK owns all interactions |
| — | Retron title-hold feedback | Existing `Gtk.WindowHandle` and native titlebars | `app.py` observes primary-button events without claiming them. Retron briefly strengthens the outer frame; title controls and message alerts are excluded. GTK/compositor owns movement and maximization |
| — | Retron appearance | Native controls in the shared non-modal window composition | `retron_editor.py`, `retron_runtime.py`; shared/component/state overrides, live preview and independent Save/Cancel. General links to the editor; existing border preferences seed its profile |
| — | Native confirmation alerts (session restore, Notes deletion and related confirmations) | `Gtk.AlertDialog` | `app.py`, `notes_dialogs.py` and other alert callers; GTK retains modal/keyboard behavior and response indices; `theme_styles.py` scopes Retron message-window colors, border and compact spacing without replacing the native control |
| — | Main header and sidebar separators | `Gtk.HeaderBar`, `Gtk.Paned` | `app.py` composes the main controls; `sidebar.py` and `notes_dialogs.py` retain sidebar widths without fixed minimums or percentage caps; GTK owns the layout limits and pointer/keyboard resizing. `theme_styles.py` styles borders, spacing and separator feedback while GTK owns centering and window dragging/controls |
| — | Connection private SSH key selection | `Gtk.FileDialog`, `Gtk.Entry` and native icon button | `src/termia/connection_dialogs.py`; fills only a local file path, preserves manual entry and ignores results after the form closes |
| — | Multiline terminal paste confirmation | Existing `DialogWindow`, editable `Gtk.TextView`, `Gtk.ScrolledWindow` and native buttons | `src/termia/terminal_sessions.py`; Paste receives initial focus and is the default; native editor Enter inserts a newline and Tab navigates to actions. Termia sends the edited buffer once after validating the original pane/process, preserves clipboard contents and intercepts middle-button primary pastes while protection is enabled |
| — | Update dependency review | Selectable `Gtk.Label`, `Gtk.ScrolledWindow`, native `Gtk.Button`, `Gtk.Expander` and read-only `Gtk.TextView` | `src/termia/update_view.py`; installation type, requirements, assisted installation, recheck dispatch and bounded copyable diagnostics; shared content/action insets without nested padding |
| — | Main menu | `Gtk.PopoverMenu` with `Gio.Menu` and native nested submenus | `src/termia/main_menu.py`; actions, submenu reset, delayed leave-to-close on the submenu row/panel, and initial-highlight clearing without removing keyboard focus |
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
| 11 | Notes editor-tab context menu | `Gtk.PopoverMenu` with `Gio.Menu` | `src/termia/notes_dialogs.py`; saved-note and draft identity; Rename, Delete, Clone, Save and Close tab dispatch |
| 13 | Notes editor tab bar | `Gtk.Notebook` | `src/termia/notes_dialogs.py`; shared editor, draft identity, save guards, close action, and tab menu |
| — | Notes editor and appearance toolbar | `Gtk.Frame`, `Gtk.ScrolledWindow`, `GtkSource.View`, and `Gtk.ToggleButton` | `src/termia/notes_dialogs.py`; native frames contain the scrolling editor and toolbar. The toggle points up to hide and down to show; Retron supplies rounded glow borders without changing saved editor colors |
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

Under #474, item 14 restores selectable group/section headers, revising #380.
Content clicks select, focus and toggle a header once; native activation toggles
it with Enter. Compact selection and flat pressed-row styling remain. Search
notifications already applied by keyboard navigation do not rebuild the model.
Main/tab/server/group/terminal menus clear their initial selected state once;
terminal menus restore focus after VTE click handling. Nested terminal menus
leave dismissal to the root and restore parent focus without reopening it.
These are Termia-owned adjustments around the standard GTK controls, not new
menu widgets. Tab/server/group arrows are drawn and positioned by GTK.
See [the laboratory record](DOCKER_LABORATORY.md) for the investigations.

### Item 17: justified capture exception

Keyboard Shortcuts uses an independent non-modal, resizable `DialogWindow`
with full-width capture labels; the snippet editor retains compact labels.
The settings window closes when its owning main window is destroyed.

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
