# UI styling guidelines and current inventory

This inventory records the current sources and ownership of Termia's visual
rules, originally recorded as a baseline for issue #302. It also defines the
design guidelines below; these do not imply a custom-theme editor.

This local research branch additionally implements the fixed Dark Glow option
described below. It does not implement the custom-theme editor from #303.

## Visual design guidelines

These guidelines define the intended direction for completing the existing
style. The inventory below records current behavior; requirements in this
section are not claims that the corresponding changes are implemented or
validated. Preserve the current layout and interaction patterns rather than
performing a general redesign.

- Maintain a native GTK4 interface that is modern, professional, minimalist,
  and consistent. Reuse existing widgets, components, colors, and CSS classes.
- Take inspiration from Dark UI and Glow Borders through well-defined
  rectangular panels, subtle colored 1px borders, slightly rounded corners
  (6–10px), and restrained lighting. Use transparency inspired by Glassmorphism
  only where it improves hierarchy and preserves contrast; do not require blur.
- Reuse the existing cyan role for information and CPU, violet for RAM, green
  for active connections and success, yellow for warnings, and red for errors
  and critical states. Do not rely on color alone to communicate meaning.
- Distinguish active, inactive, selected, and keyboard-focused elements.
  Active elements may use a brighter border and soft glow; inactive elements
  should retain the same visual language with lower intensity. Keep keyboard
  focus independently recognizable and disabled controls clearly identifiable.
- Preserve accessibility, readability, resizing, and compatibility with System,
  Light, and Dark appearance. Adapt shared styles to the GTK theme; keep the
  fixed Dark Glow palette confined to its opt-in mode.
- Avoid excessive saturation, decorative effects, unnecessary animations,
  unsolicited redesigns, new dependencies, and custom rendering. Use only
  CSS properties supported by the project's GTK4 runtime, applied through
  `Gtk.CssProvider`; verify `border`, `border-radius`, `background-color`,
  and `box-shadow` support before introducing rules.

### Terminal containers

Apply borders to the GTK containers around each `Vte.Terminal`, preserving
VTE rendering and configured terminal colors. Use brighter active-pane borders
and more subdued inactive borders, with clear separation in horizontal,
vertical, and nested splits. Borders and lighting must not obscure content or
interfere with focus, scrolling, text selection, resizing, or split dividers.

### Menus and dropdowns

Use consistent, subtle selection backgrounds and readable text and icons for
main menus, context menus, submenus, and native dropdowns. Inspect the actual
GTK4 widget hierarchy and CSS nodes before selecting rules for hover, focus,
selection, and pressed states. Preserve disabled states and native keyboard
and pointer navigation.

### Tabs

Give active and inactive terminal and Notes tabs consistent colored borders,
using stronger color and soft lighting for the active tab and subdued borders
for inactive tabs. Inspect any other tab-based navigation before applying
shared rules. Keep normal, hover, focused, and active states coherent without
unnecessary changes to dimensions, spacing, close targets, scrolling,
reordering, or navigation.

### Implementation and validation

Before changing visual code, identify the responsible widgets and containers,
review existing CSS and reusable palette values, inspect the real GTK4 CSS
nodes, and define a consistent state strategy. Centralize shared rules, avoid
duplicates and conflicting selectors, and make incremental changes within the
existing Core/add-on boundaries.

Validate individual terminals, multiple splits, active and inactive tabs,
pane-focus changes, main/context/dropdown menus, keyboard and mouse navigation,
light and dark appearance, and window/panel resizing against the regression
checklist. Report changed files, completed checks, skipped checks, and known
limitations; do not claim visual or functional validation from static review
alone. Follow the user's explicit restrictions on running tests.

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
| Dark Glow (local research) | Requests GTK's dark variant | Fixed opaque palette from `theme_styles.py`, 1px borders, 10px corners and soft active-pane/tab lighting |

The shared application CSS provider is replaced when the appearance changes so
rules from an earlier mode do not remain active.

Dark Glow rules are scoped below `window.termia-dark-glow`. An application-owned
top-level window observer adds/removes that class for existing and future
windows, including detached windows and in-process dialogs. It is disconnected
at application shutdown. This follows the existing process-wide GTK appearance;
it does not change another application's theme or external desktop portals.
Switching back removes the scope class and replaces the CSS provider.

`theme_styles.py` centralizes neutral surfaces and cyan/violet/green/yellow/red
roles. `termia-panel` and `termia-role-*` are reusable internal style classes,
not an add-on interface. Notifications use their existing severity to choose
the border role. Keyboard focus retains an explicit outline. VTE nodes and the
Notes editing surface are not recolored; their configured palettes stay separate.
This is a fixed selectable theme, without a theme editor, animations, background
blur or prototype imports. Tests are prepared but have not been executed.

### Shared interaction styles (#484)

`build_interaction_css()` in `theme_styles.py` centralizes terminal-container,
terminal/Notes tab and native menu states. System/Light/Dark use GTK theme
colors; Dark Glow uses its existing cyan accent and fixed surface colors.
Rules target `.termia-terminal-pane`, `.termia-tab-label`, native Notebook
`header > tabs > tab`, `.termia-menu-popover modelbutton`, and rows below
`dropdown.termia-choice popover listview`. The shared dropdown factory supplies
`termia-choice`; native selection and activation remain GTK-owned.

Terminal containers reserve a constant 1px border on every side; focus within
brightens it and adds a 4px, low-opacity outer shadow. This reduces available
terminal content space by 2px per axis compared with borderless containers.
Tab borders use inset shadows to retain their current allocations. Active tabs
also receive a soft outer shadow, while keyboard focus has a separate outline.
Pane focus follows GTK's `:focus-within`, including focus on a pane's toolbar;
opening a menu removes pane focus emphasis without changing session selection.
Outer shadows may be clipped by existing scrolling/split containers. Static
review does not establish contrast, performance or regression-free rendering;
automated and interactive validation remain pending in this research phase.

## Technical specification: palette, CSS values and cascade

This section records the current local implementation, not a proposed design.
Keep it synchronized whenever visual values or selectors change. Sources:
[`theme_styles.py`](../src/termia/theme_styles.py),
[`styles.py`](../src/termia/styles.py),
[`app.py`](../src/termia/app.py),
[`choice_widgets.py`](../src/termia/choice_widgets.py), and the component
sources linked below. CSS dimensions are logical pixels unless another unit
is specified. A value inherited from GTK is theme-dependent; it has no single
fixed hexadecimal equivalent in Termia.

### Complete Dark Glow palette

All hexadecimal colors in this table are opaque (alpha 1). Their alpha is
reduced only where an explicit `alpha(...)` expression is used.

| Key | Exact value | Role/application |
|---|---|---|
| `canvas` | `#0D1420` | Window and `.termia-main-surface` background |
| `surface` | `#182231` | Header, sidebar, panels, cards, lists, popover contents and Notes tab header |
| `control` | `#1C2A3C` | All button backgrounds, entries and spin buttons |
| `hover` | `#23364B` | Hover backgrounds and enabled menu/dropdown focus |
| `selection` | `#29475A` | Selected rows, active tabs and pressed/selected menu items |
| `text` | `#EDF3F8` | Primary foreground |
| `muted` | `#B3C1D1` | Secondary labels and disabled-control foreground |
| `border` | `#345667` | Neutral panel/control/popover border |
| `cyan` | `#55BAC9` | Information role, interaction accent, pane/tab borders and focus outlines |
| `violet` | `#A194D6` | RAM role available to styled components |
| `green` | `#78BD97` | Success role and suggested-action border |
| `yellow` | `#D2B36F` | Warning role |
| `red` | `#D8848D` | Error role and destructive-action border |
| Additional literal | `#264C3A` | `button.suggested-action` background |
| Additional literal | `#5A2C37` | `button.destructive-action` background |

Role definitions do not imply that CPU, RAM or active-connection indicators
currently consume them. Notifications map information/success/warning/error to
cyan/green/yellow/red in `TermiaWindow.show_toast()`.

### Provider order and scope

`build_application_css()` concatenates the base structural CSS, then the fixed
Dark Glow CSS only for `theme == "dark_glow"`, then the shared interaction CSS.
The application provider uses `Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION` (600).
Notes has an independent editor provider at application priority + 1 (601).
Providers apply to the display; selectors determine which widgets they affect.

Dark Glow prefixes its rules with `window.termia-dark-glow`. The top-level
observer adds/removes that class on existing and future windows. Ordinary
System/Light/Dark shared rules target the Termia component classes without
the fixed-palette window prefix. GTK specificity applies before source order;
later rules win only at equal specificity and provider priority.

| Shared interaction variable | Dark Glow | System/Light/Dark |
|---|---|---|
| `accent` | `#55BAC9` | `@theme_selected_bg_color` |
| `foreground` | `#EDF3F8` | `@theme_fg_color` |
| `hover` | `#23364B` | `alpha(@theme_fg_color, 0.06)` |
| `selected` | `#29475A` | `alpha(@theme_fg_color, 0.13)` |
| `muted` | `#B3C1D1` | `alpha(@theme_fg_color, 0.45)` |

`alpha(color, factor)` multiplies the input alpha; it is not a global widget
opacity. The rendered result depends on the surface behind it. No fixed final
pixel color is promised for GTK-derived or translucent values.

### Dark Glow surfaces and controls

Selectors below are relative to `window.termia-dark-glow`. Palette names refer
to the exact values above. Properties not listed remain inherited from GTK or
other component rules; this is not a complete replacement GTK theme.

| Selector | Explicit styling |
|---|---|
| Window itself; `.termia-main-surface` | Background `canvas`, foreground `text` |
| `headerbar` | Background `surface`, foreground `text`, shadow `none` |
| `.termia-session-tabs`, `.termia-session-tab-controls` | Background `transparent`, foreground `text`, shadow `none`; the main canvas `#0D1420` shows through both containers. Individual tab backgrounds, borders and active lighting remain independently styled. |
| `.termia-sidebar`, `.termia-panel`, `.stat-card`, `frame.card` | Background `surface`, foreground `text`, border `1px solid border`, radius `10px`, shadow `none` |
| `listview`, `listbox` | Background `surface`, foreground `text` |
| `row` | Transparent background |
| `row:hover` | Background `hover` |
| `row:selected`; selected connection-row `.termia-sidebar-object` | Background `selection`, foreground `text`, radius `10px` |
| `popover > contents` | Background `surface`, foreground `text`, border `1px solid border`, radius `10px`, shadow `none` |
| `button` | Background image `none`, background `control`, foreground `text`, border color `border`, radius `10px`, box/text shadows `none`; includes flat buttons |
| `button:not(.flat)`, `entry`, `spinbutton` | Background `control`, foreground `text`, border `1px solid border`, radius `10px`, shadow `none` |
| `button:hover` | Background `hover`, border color `cyan` |
| `button:active`, `button:checked` | Background `selection`, border color `cyan` |
| `button.suggested-action` | Background `#264C3A`, border color `green`, foreground `text` |
| `button.destructive-action` | Background `#5A2C37`, border color `red`, foreground `text` |
| `button:disabled` | Background `surface`, foreground `muted`, border color `border`, box/text shadows `none` |
| `entry:disabled` | Foreground `muted`, border color `border` |
| `button:focus-visible`, `entry:focus-within`, `spinbutton:focus-within` | Outline `2px solid cyan`, offset `2px` |
| `.termia-tab-label` | Transparent background, transparent `1px solid` border, radius `10px`; shared shadows below apply afterwards |
| `.termia-notes-notebook > header` and its `> tabs` | Background `surface` |
| `.dim-label` | Foreground `muted`, widget opacity `1` |
| `.termia-panel.termia-role-ROLE`, `.termia-notification.termia-role-ROLE` | Border color from cyan/violet/green/yellow/red role; no extra glow |
| `.termia-role-ROLE progressbar > trough > progress` | Background and border color from the same role |

The action-specific background selectors have the same specificity as the
generic `button:hover`/`:active` background rules and are emitted later, so
their colored backgrounds remain in those states. The disabled-button rule
is emitted after action-specific rules at equal specificity and replaces the
background with `#182231`, foreground with `#B3C1D1`, and border with `#345667`.

All button CSS nodes, including flat/header/sidebar buttons, toggle buttons,
window controls and inner buttons of MenuButton/DropDown/SpinButton, receive
the common background. `background-image: none` removes theme gradients/images
that could obscure `background-color`; this is a static diagnosis of a possible
cause, not a verified runtime finding. Existing flat/framed border widths,
padding, sizes and interactions remain unchanged. No new border width is
assigned to flat buttons. Enabled ordinary buttons use `#1C2A3C`, hover
`#23364B`, pressed/checked `#29475A`, with text `#EDF3F8`; hover and
pressed/checked borders use `#55BAC9`. Focus outline remains `2px solid
#55BAC9` at offset `2px`. Suggested/destructive backgrounds remain `#264C3A`
and `#5A2C37`, with green/red borders, except when disabled. Dark Glow scope
is unchanged; System/Light/Dark retain their GTK button colors.

Progress trough geometry and unspecified icon colors remain GTK-owned.
Symbolic icons normally inherit widget foreground; multicolor image assets
are not recolored. Menu items use their separate modelbutton rules.

### Terminal borders, tab lighting and keyboard focus

In this table `A`, `H` and `S` mean `accent`, `hover` and `selected` from the
interaction-variable table. Shadow syntax is horizontal offset, vertical
offset, blur radius, optional spread radius, and color; `inset` draws inward.

| Component/state | Exact declarations |
|---|---|
| `.termia-terminal-pane`, normal | `border: 1px solid alpha(A, 0.35)` |
| `.termia-terminal-pane:focus-within` | `border-color: A; box-shadow: 0 0 4px alpha(A, 0.18)` |
| Terminal tab and Notes `header > tabs > tab`, normal | `box-shadow: inset 0 0 0 1px alpha(A, 0.35)` |
| Both tab types, `:hover` | `background-color: H; box-shadow: inset 0 0 0 1px alpha(A, 0.65)` |
| Terminal `.active` or Notes `:checked` | `background-color: S; box-shadow: inset 0 0 0 1px A, 0 0 4px alpha(A, 0.18)` |
| Both tab types, `:focus-visible` or `:focus-within` | `outline: 2px solid A; outline-offset: -3px` |
| Terminal tab `.dragging` | Background `alpha(A, 0.25)`, whole-widget opacity `0.72` |

For Dark Glow, the accent is RGB `(85, 186, 201)`: the normal border is
`rgba(85, 186, 201, 0.35)`, hover border `rgba(85, 186, 201, 0.65)`, active
border `#55BAC9`, and outer glow `rgba(85, 186, 201, 0.18)`. Glow offsets are
both `0px`, blur `4px`, spread `0px`; it is not an inset glow. The tab's inset
border has zero blur and `1px` spread. There is no configurable glow-strength
setting or reusable `GlowPanel` widget.

The pane border has no explicit radius or background rule. It encloses the
status toolbar and terminal scroller, not VTE's drawing node. Its constant
width reserves 2px per axis; changing focus changes no border width.
`:focus-within` includes toolbar focus, rather than tracking SSH connection
state. Tab selection uses `.active`/`:checked` independently of keyboard focus.
At equal specificity, active tab styling is emitted after hover and wins;
dragging changes background and opacity without removing the active shadow.
Focus outlines are drawn inward on tabs. Shadows/outlines do not reserve extra
layout space, and ancestors may clip outer shadows.

### Native menu and dropdown states

Targets are `.termia-menu-popover modelbutton` and
`dropdown.termia-choice popover listview > row`; the common dropdown factory
adds `termia-choice`. In Dark Glow these selectors also have the window prefix.

| State | Background | Foreground | Outline/shadow |
|---|---|---|---|
| Enabled `:hover` or `:focus` | `H` | `foreground` | No additional shadow rule |
| Enabled `:selected` or `:active` | `S` | `foreground` | Emitted after hover/focus |
| Enabled `:focus-visible` | Inherited from matching state above | Same | `2px solid A`, offset `-2px` |
| `:disabled` | `transparent` | `muted` | `outline: none; box-shadow: none` |

Enabled rules explicitly use `:not(:disabled)`. Normal unselected menu-item
backgrounds, padding, checkmarks and submenu arrows retain native GTK styling.
Selected/pressed rules win over hover/focus at equal specificity; keyboard
focus has an independent inward outline. Label/icon-specific GTK rules may
still affect descendants; no per-icon recoloring is performed here.

### Shared structural CSS values

These are the declarations in `styles.py`. More specific Dark Glow or shared
interaction rules override them as described above. Four-value padding is
top/right/bottom/left; two-value padding is vertical/horizontal.

| Selector/component | Base values |
|---|---|
| `.termia-connections-tree` | Transparent background; rows `padding: 2px 4px`; active row shadow `none`; selected row background transparent, foreground `@theme_fg_color` |
| `.termia-sidebar-object` | Padding `2px 6px`, radius `4px`; selected background `@theme_selected_bg_color`, foreground `@theme_selected_fg_color` |
| `.termia-group-drop-target.drop-target` | Background `alpha(@theme_selected_bg_color, 0.24)`, shadow `inset 0 0 0 1px @theme_selected_bg_color`, radius `4px` |
| `.termia-server-item.dragging` | Widget opacity `0.65` |
| `.prompt-preset-button` | Padding `1px 6px`, minimum height `24px` |
| `.termia-add-icon-badge` | Background `@theme_bg_color`, radius `999px` |
| `headerbar`, including `:backdrop` | Background `@headerbar_backdrop_color`; ordinary header bottom border width `0`, shadow `none` |
| `.termia-session-tab-controls` | Background `@headerbar_backdrop_color`, padding `2px 2px 0 2px` |
| `.termia-session-tabs` | Background `@headerbar_backdrop_color`, padding `2px 2px 1px 2px`, border `0`, shadow `none` |
| `.termia-session-tab-scroller` | Background transparent, border `0`, shadow `none` |
| Tab scroller horizontal scrollbar | Minimum height `5px`, margin `0 2px`, padding `0`; slider minimum height `3px`, minimum width `24px` |
| `.termia-terminal-stack` | Border `0`, shadow `none` |
| `.termia-pane-status.active` | Background `alpha(@theme_selected_bg_color, 0.12)`, including Dark Glow |
| Pane status labels; status bar inside a split | Label minimum width `0`; split status-bar padding `6px` |
| `.termia-read-only-badge` | Font weight `600` |
| `.termia-terminal-paste-preview` | Shared theme surface/selection colors, border `1px solid alpha(accent, 0.35)`, radius `8px`; see region specification below |
| `.termia-tab-label` | Padding `7px 10px`, margin `0 2px`, radius `8px`, background transparent, border `0`; Dark Glow reserves a transparent `1px` border and uses radius `10px` |
| `.termia-tab-title` | Font size `1.05em` |
| `.termia-tab-close` | Padding `0`, minimum width/height `24px`, base radius `9999px`; base hover black alpha `0.16`, active black alpha `0.24`, hover shadow `none` |
| `.termia-tab-overflow-button` | Padding `0`, minimum width `0`, minimum height `24px`, margin `1px 0 6px 0`; inner button horizontal padding `1px`, minimum width `16px` |
| `.termia-status-hide`, `.termia-disconnect-button` | Padding `0 6px`, minimum height `18px`, font size `0.85em` |
| Notes notebook, stack, header and header tabs | Background transparent, border `0`, shadow `none` before the Dark Glow header background override |
| Notes header tab | Radius `8px 8px 0 0`; shared interaction shadows as above |
| `.termia-notes-editor` | Border `1px solid @borders`, radius `8px`, default background `#001B33`; text view foreground `#FFFFFF` and background `#001B33` before saved appearance overrides |
| `.stat-card` | Padding `10px 12px`, border `1px solid @borders`, radius `6px`, background `alpha(@theme_bg_color, 0.58)`; Dark Glow replaces border/background/radius with its surface rule |
| Statistics title/value/subtitle | Font sizes `0.82em` / `1.55em` / `0.82em`; value font weight `700` |
| `.stat-row` | Padding `6px 8px`, bottom border `1px solid alpha(@borders, 0.55)` |
| Snippet category `flowboxchild.termia-snippet-category-tile` | Padding `0`, radius `8px`; selected background transparent, shadow `none`; inner `.termia-snippet-category-frame` radius `8px` |
| Selected snippet inner frame | Background `alpha(@theme_selected_bg_color, 0.2)`, border color `@theme_selected_bg_color`, foreground `@theme_fg_color` |
| `.termia-required-marker`, `.termia-required-hint` | Marker font size `1.2em`, weight `700`; hint foreground `alpha(@theme_fg_color, 0.8)` |

`tabs.py` additionally requests a minimum tab width of `118px`, title width
and maximum width of 8 characters, and title start/end margins of `4px`.
These requests are separate from CSS padding. They are not fixed allocations.

The generic Dark Glow `button` rule is more specific than the base
`.termia-tab-close` radius rule: the close button currently receives `10px`
corners rather than the base circular `9999px` radius. Its hover/pressed
background also follows the more specific Dark Glow button rules. Similarly,
Dark Glow's selected-row rule paints the entire selected connection row as
well as its content block, rather than preserving the ordinary content-only
selection. These are current cascade effects, not additional design approvals.
GTK Notebook underline rendering can be affected by the explicit tab
`box-shadow`; retaining a separate native blue underline is not guaranteed.

### Split separators and independent editor/terminal colors

Let `T = max(1, configured split_separator_thickness)` and `H = max(5, T)`.
Horizontal split separators use minimum width `H` and a left solid border of
width `T`; vertical separators use minimum height `H` and a top solid border
of width `T`. Both use the configured terminal background for the drag area
and configured separator color for the line. On hover only the line becomes
`alpha(configured color, 0.82)`. Default line color is `#008712`, width `1px`;
preferences bound width to `1–32px`.

Dark Glow overrides `.termia-split-pane > separator` and its `:hover` state
with `background: transparent; border-color: transparent; box-shadow: none`.
The shorthand also clears background images. It retains `H`, border width
`T`, native margins/padding/cursor, `wide_handle=False`, split positions and
Gtk.Paned interaction. The retained separator provides the gap; no margins
are added to terminal panels. Both panel borders remain separately visible.
The main canvas (`#0D1420`) shows through the transparent gap where not covered
by another widget. Actual total hit-area size and composition require runtime
inspection; `H` is a CSS minimum, not a measured overall width/height.

Separator color preferences remain stored and visible in System/Light/Dark;
in Dark Glow, changing the configured line color does not produce a visible
line. Thickness still affects the retained border allocation and can increase
minimum separator size above 5px. The existing Terminal preferences separator
preview continues to display the configured color; it is not a screenshot of
the Dark Glow transparent divider. No settings migration is introduced.

Terminal settings default to foreground `#D8DEE9`, background `#1F2430`,
font `JetBrains Mono`, size `13` in the Pango font description, and prompt
color `#EEEEEC` (custom prompt disabled by default). `TerminalViewFactory`
passes saved colors directly to VTE; no Dark Glow rule changes its ANSI colors.
The current default ANSI palette in `models.py`, by index, is:

| Index/name | Normal | Bright index/name | Bright |
|---|---|---|---|
| 0 black | `#2E3436` | 8 bright black | `#646B70` |
| 1 red | `#B45D58` | 9 bright red | `#CF6F68` |
| 2 green | `#6F8F5F` | 10 bright green | `#8FBF77` |
| 3 yellow | `#AA8750` | 11 bright yellow | `#D2B45F` |
| 4 blue | `#5F7F9F` | 12 bright blue | `#82A8C9` |
| 5 magenta | `#8A6F8F` | 13 bright magenta | `#AA8AAA` |
| 6 cyan | `#5F9292` | 14 bright cyan | `#83C4C4` |
| 7 white | `#C9C9C9` | 15 bright white | `#EEEEEC` |

Saved profiles can override this palette. `constants.py` also retains the
historical `LEGACY_ANSI_PALETTE`, which is not the current default. Foreground /
background presets are Ubuntu `#EEEEEC` / `#300A24`, Polaris `#D8DEE9` /
`#1F2430`, Solarized `#839496` / `#002B36`, Tango `#EEEEEC` / `#2E3436`, and
Claro `#2E3436` / `#F6F5F4`. Prompt preset colors are Verde `#8AE234`, Azul
`#729FCF`, Ambar `#FCE94F`, Rojo `#EF2929`, and Blanco `#EEEEEC`.

Notes defaults are foreground `#FFFFFF`, background `#001B33`, size `12pt`
and inherited font family unless a saved font is supplied. Its separate
provider styles the editor/text nodes, toolbar buttons (padding `2px 5px`,
minimum width `20px`, minimum height `22px`), toolbar spin buttons (minimum
height `26px`, inner buttons padding `2px`, minimum width `14px`), and list
labels (`0.9em`). The GtkSourceView scheme
[`termia-notes.xml`](../src/termia/assets/termia-notes.xml) sets both ordinary
and current line numbers to foreground `#0065BF`, background `#000D1A`.
Notes appearance is independent of the application palette.

The terminal preferences preview in
[`terminal_preferences.py`](../src/termia/terminal_preferences.py) uses the
selected font, size in `pt`, foreground and background, with radius `6px`.
The split preview uses the selected separator color for both background
properties, a requested width clamped to `1–32px`, and radius `999px`.

### Main regions and multiline-paste preview (#484)

These rules are appended by `build_interaction_css()` in every appearance mode.
They retain the existing widget hierarchy and native controls. Main-window
composition in `app.py` adds `termia-main-header` to the actual `Gtk.HeaderBar`
and `termia-main-paned` to the existing horizontal `Gtk.Paned`. No wrapper is
inserted into the title bar, no event handler changes, and no VTE node is styled.

Let `A` be the shared accent and `F` its foreground from the variable table.
`P` is the panel surface: `#182231` for Dark Glow and `@theme_bg_color` for
System/Light/Dark. Text selection uses `#29475A` / `#EDF3F8` in Dark Glow and
`@theme_selected_bg_color` / `@theme_selected_fg_color` in ordinary modes.
All numerical CSS dimensions below are logical pixels.

| Target/state | Exact values |
|---|---|
| `headerbar.termia-main-header` | Background image `none`, background `P`, foreground `F`, border `1px solid alpha(A, 0.35)`, radius `10px`, shadow `inset 0 0 4px alpha(A, 0.10)` |
| Main header `:backdrop` | Border color `alpha(A, 0.25)`, shadow `none`; same background and foreground |
| `.termia-main-surface` | Top padding `4px`, separating title bar from the body |
| `.termia-sidebar` | Background `P`, foreground `F`, border `1px solid alpha(A, 0.35)`, radius `10px`, padding `8px 10px` |
| Sidebar `:focus-within` | Border color `alpha(A, 0.65)`, shadow `inset 0 0 4px alpha(A, 0.10)` |
| `paned.termia-main-paned > separator` | Background image `none`, background transparent, border color transparent, shadow `none`; no minimum-size, border-width, margin, padding or cursor overrides |
| Main separator `:hover`, `:active`, `:selected` | Background `alpha(A, 0.12)` |
| Main separator `:focus-visible` | Outline `1px solid A`, offset `-1px` |
| `.termia-session-tab-controls` | Bottom margin `4px`; no allocation when the controls are hidden |
| Paste preview scroller, descendant `textview`, direct `text` and `border` nodes | Background `P`, foreground `F` |
| `.termia-terminal-paste-preview` | Border `1px solid alpha(A, 0.35)`, radius `8px` |
| Preview `textview > text > selection` | Theme-specific selection background and foreground defined above |
| Preview scrollbar slider | Background image `none`, background `alpha(A, 0.35)`; hover `alpha(A, 0.65)`; pressed `A`; native geometry retained |

The sidebar's GTK widget margins are top/bottom/start `4px` and end `0px`,
replacing the previous `12px` on each side. Every direct child (action row,
search entry, tree scroller and summary label) shares the parent padding of
10px horizontally; descendants retain their existing indentation. Its vertical
box spacing remains 8px, minimum width request 120px and initial splitter
position 280px. Replacing exterior margins with interior padding limits the
extra horizontal space consumption: outer margins plus border and padding
occupy 26px: previously 24px in ordinary modes or 26px in Dark Glow, which
already supplied a 1px border. Content constraints can still require a wider
sidebar at some font sizes; no controls are shrunk or repositioned.

The sidebar's end margin is zero because the native wide separator itself
provides the gap. In the inspected Yaru resource, its minimum width is 5px,
margin/padding zero. Other themes may choose different hit-area dimensions;
those are retained. Removing its two background-image lines avoids double
borders while keeping resize and native keyboard interaction. The rule cannot
match `.termia-split-pane` separators, whose terminal-specific styling remains
unchanged. Sidebar visibility and remembered-width handling are unchanged.

The header border adds 1px per edge around the same native HeaderBar; its
centering, drag region and window controls remain GTK-owned. Header/sidebar
lighting is deliberately inset (zero offsets, 4px blur, zero spread, alpha
0.10) so it does not need extra exterior space or cross a scroller boundary.
This does not establish that every rounded edge renders without clipping;
maximized/restored windows and native controls require visual inspection.
The 4px tab-to-stack margin is outside the tab scroller and applies uniformly
to all sessions/splits. Existing active/inactive tab and pane rules are retained.

`terminal_sessions.py` gives the preview TextView native left/right margins of
10px and top/bottom margins of 8px. These are presentation properties, not
inserted spaces or newlines: the original `set_text(text)` and
`terminal.paste_text(text)` calls and the captured text are unchanged. The
existing 560×320 default dialog size, warning label, content spacing 12px,
content margins 16px (bottom 0), action top margin 8px, read-only monospace view,
Cancel default/focus, validity guards and response lifecycle remain unchanged.
Its controls keep existing GTK/application button styling. No whitespace
normalization, escaping, truncation, text tags, wrapping change or clipboard
write is introduced. Long lines retain native horizontal scrolling.

Native CSS-node references: [HeaderBar](https://docs.gtk.org/gtk4/class.HeaderBar.html#css-nodes),
[Paned](https://docs.gtk.org/gtk4/class.Paned.html#css-nodes), and
[TextView](https://docs.gtk.org/gtk4/class.TextView.html#css-nodes).
Only static code/resource inspection has been performed. Font-dependent minimum
sizes, clipboard-content preservation in execution, native focus, resize areas,
selection contrast, scrollbar states and clipping remain unvalidated at runtime.

### Native confirmation alerts in Dark Glow

Session restoration after unlock and Notes deletion use `Gtk.AlertDialog` in
`app.py` and `notes_dialogs.py`. They do not use Termia's `DialogWindow` form
layout. In the inspected GTK implementation, AlertDialog creates a native
message window. The installed GTK UI resources expose a header bar,
`.dialog-vbox`, `.dialog-action-box` and `.dialog-action-area`; the installed
Yaru CSS targets `window.dialog.message` and adds action-button padding
`10px 14px`. This resource inspection does not establish which desktop theme
is active or replace a runtime rendering check.

The following additional rules are restricted to
`window.termia-dark-glow.dialog.message`, using the existing window observer.
They do not replace the native alert or change its callbacks/default responses.

| Target (relative to alert window) | Exact declarations |
|---|---|
| Window | Background `#0D1420`, foreground `#EDF3F8`, border `1px solid alpha(#55BAC9, 0.65)`, radius `10px`, shadow `0 0 4px alpha(#55BAC9, 0.18)` |
| Window `:backdrop` | Border color `alpha(#55BAC9, 0.35)`, shadow `none` |
| `headerbar`, `.titlebar:not(headerbar)` and both `:backdrop` variants | Background image `none`, background `#182231`, foreground `#EDF3F8`, border `0`, radius `9px 9px 0 0`, shadow `none`, minimum height `32px`, padding `4px 8px` |
| `.dialog-vbox` | Background `#0D1420`, foreground `#EDF3F8`, padding `16px 0 0` |
| `.dialog-action-box` | Background image `none`, background transparent, border `0`, padding `0 16px 16px` |
| `.dialog-action-area` | CSS border spacing `8px` |
| `.dialog-action-area button` | Minimum content height `24px`, padding `4px 12px`, solid border width `1px`, radius `8px`, font size `1em`; existing button state colors still apply |

A button's minimum requested outer height is 34px before any native widget
margins or larger content request (24 + 2×4 padding + 2×1 border). This is
not a fixed allocation. GTK retains native horizontal button allocation;
buttons can still share equal widths. CSS border spacing can be superseded by
an explicit GtkBox spacing property. The inspected message template retains
its own 30px horizontal widget margins around the message, 10px message/detail
spacing, and 20px content-box spacing. The new 16px top inset complements those
existing margins; no label padding or fixed dialog width is introduced.

The same styling affects other native message alerts carrying those classes,
including close/unsaved/import confirmations, while System/Light/Dark and
Termia's separate form-dialog layout keep their existing behavior. Enter,
Escape, modality and button indices remain GTK/application-owned: restoration
keeps default index 1 and cancel index 0; note deletion keeps both default and
cancel index 0. No semantic destructive role is inferred from translated text.

The titlebar rule covers headerbar and non-headerbar client-side GTK
decorations, explicitly in both normal and backdrop states. It removes inherited
background images and keeps the same surface color when focus leaves the alert.
It does not replace the native titlebar or alter global GTK settings. A title bar drawn
by the window manager cannot be recolored by application CSS. Rounded corners,
outer glow, text wrapping, localized button widths and these internal GTK
selectors remain subject to runtime/version validation. There has been no
interactive or automated validation in this research iteration.

### Effects not implemented and validation limits

Dark Glow canvas, surface and control colors have opacity 1. There is no
semitransparent glass panel, background blur, `backdrop-filter`, custom drawing,
or theme-defined animation/transition. Translucency is limited to the alpha
expressions and widget opacities explicitly listed above. GTK may supply its
own animations, metrics, symbolic-icon treatment and inherited effects.

Values describe CSS declarations and their statically identifiable cascade;
they are not runtime measurements or contrast/performance guarantees. Actual
native CSS nodes, theme inheritance, clipping, display scaling and interaction
still require visual validation. Automated and interactive tests have not been
run for this local styling iteration.

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
| `alpha(...)` GTK expressions | Hover, active, dragging, selected, scrollbar, and required-hint feedback | Derived from the active GTK theme |
| `#001B33` and white text defaults | Notes writing surface | User may override these through saved Notes appearance preferences |
| `#0065BF` on `#000D1A` | Notes line-number gutter | GtkSourceView style scheme in `src/termia/assets/termia-notes.xml` |

Termia also defines component dimensions, padding, margins, border radii, and
separator treatment in `src/termia/styles.py`.

### Terminal-only values

Terminal foreground/background, ANSI palettes, prompt color, and the split
separator color are user-configurable terminal settings. The split divider
combines the terminal background for its drag area with the configured line
color in System/Light/Dark. Dark Glow instead makes the background and border
transparent, retaining dimensions and saved preferences as detailed above.
These configurable terminal values are not application-theme tokens.

## Component ownership

This table describes **appearance ownership**. It does not classify whether a
component's interaction uses a standard GTK control. See the
[GTK control policy and inventory](GTK_CONTROLS.md) for that classification.

| Component | Current owner | Current implementation |
|---|---|---|
| Main and context menus | GTK interaction with scoped Termia hover/selection/focus colors | `theme_styles.py`, `styles.py`, menu classes |
| Dialogs | GTK | Individual dialog builders |
| Header and session tabs | Approved custom GTK tab strip with a stack, equal-width labels, an automatically hiding horizontal scrollbar and native down-arrow selector. Scoped theme-derived active, hover and drag colors retain the laboratory appearance. | `app.py`, `tabs.py`, `styles.py` |
| Note tabs and editor | Native `Gtk.Notebook` behavior with scoped rounded corners, inset colored borders, active-tab lighting and focus outlines; header/selection colors depend on appearance mode. Saved Notes appearance preferences, native GtkSourceView line numbers, and editor borders/spacing remain separate. | `notes_dialogs.py`, `styles.py`, `theme_styles.py`, `assets/termia-notes.xml`, and settings |
| Notes tree | GTK `ListView` selection and `TreeExpander` disclosure; Termia row spacing and scoped context/drop feedback | `notes_dialogs.py`, `styles.py` |
| Connections tree selection and group drop target | Native `Gtk.ListView` selection and `Gtk.TreeExpander` disclosure; selection colors confined to rounded content-width icon/title blocks, scoped spacing, and theme-derived drop feedback | `sidebar.py`, `sidebar_projection.py`, `styles.py` |
| Split panes | Terminal preferences | `styles.py` and terminal settings |
| Required-field marker and hint | GTK label foreground and secondary text derived from `@theme_fg_color` | `connection_dialogs.py` and `styles.py` |
| Snippet manager and category tiles | GTK window and buttons with Termia layout and selection rules | `snippet_dialogs.py` and `styles.py` |

### Connections list background

The connections list keeps a transparent background, matching the original
sidebar container and allowing the window background to show through. GTK still
owns selection, but its full-row background is suppressed. Selection colors are
painted on the content-width icon/title block with 6 px horizontal padding and
4 px corner radii, leaving the remaining row background unchanged in
System/Light/Dark. Dark Glow overrides selected rows and their content blocks
with `#29475A`, foreground `#EDF3F8` and `10px` radii, as detailed above.

### Terminal tab selection

The approved terminal strip uses a homogeneous GTK box above a `Gtk.Stack`,
inside a `Gtk.ScrolledWindow`. This is a custom tab interaction composed from
standard GTK widgets, selected explicitly for its laboratory appearance and
horizontal scrolling. Notes keep their separate native Notebook.

Scoped `termia-tab-label` styles use a theme-derived selected background,
softer inactive hover, 7 px vertical and 10 px horizontal padding, 2 px side
margins and 8 px rounded corners (`10px` in Dark Glow). Close buttons have
the base circular radius, overridden to `10px` by Dark Glow as recorded above.
The strip's horizontal scrollbar uses GTK overlay scrolling and hides when idle.
The adjacent native down-arrow menu button appears only when tabs overflow.

During private drag, the source uses GTK's widget paintable, a theme selection
color at 25% alpha and 72% opacity. Reordering and edge scrolling preserve the
laboratory interaction. Menu contents refresh on opening, not on pointer motion.

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
  targets that class. `termia-notes-notebook` keeps GTK's selected-tab and overflow
  behavior, with a transparent header outside Dark Glow, rounded tab corners,
  colored inset borders and active shadows. Selection colors and focus outlines
  come from `theme_styles.py`; the explicit shadows may replace the theme's
  native underline. `termia-notes-editor` has scoped rules in `styles.py`. The
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
