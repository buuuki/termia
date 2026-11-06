# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, opt-in Dark Glow palette. No dependency on optional tools or VTE."""

from .constants import DARK_GLOW_SURFACE_COLOR, DEFAULT_DARK_GLOW_BORDER_COLOR

DARK_GLOW_THEME = "dark_glow"
DARK_GLOW_CLASS = "termia-dark-glow"
DARK_GLOW_COLORS = {
    "canvas": "#0D1420", "surface": DARK_GLOW_SURFACE_COLOR, "control": "#1C2A3C",
    "hover": "#23364B", "selection": "#29475A", "text": "#EDF3F8",
    "muted": "#B3C1D1", "border": "#345667", "cyan": DEFAULT_DARK_GLOW_BORDER_COLOR,
    "violet": "#A194D6", "green": "#78BD97", "yellow": "#D2B36F", "red": "#D8848D",
}


def build_dark_glow_css(border_color: str = DEFAULT_DARK_GLOW_BORDER_COLOR) -> str:
    c = DARK_GLOW_COLORS
    root = f"window.{DARK_GLOW_CLASS}"

    def rule(selectors: str, declarations: str) -> str:
        return ", ".join(f"{root}{' ' if selector else ''}{selector}" for selector in selectors.split(",")) + " { " + declarations + " } "

    css = rule("", f"background-color: {c['canvas']}; color: {c['text']};")
    css += (
        f"{root}.termia-main-window {{ border: 1px solid alpha({border_color}, 0.50); "
        f"border-radius: 10px; box-shadow: 0 0 3px alpha({border_color}, 0.05); }} "
        f"{root}.termia-main-window:backdrop {{ border-color: alpha({border_color}, 0.35); "
        "box-shadow: none; } "
    )
    css += rule("headerbar", f"background-color: {c['surface']}; color: {c['text']}; box-shadow: none;")
    css += rule(".termia-session-tabs,.termia-session-tab-controls", f"background: transparent; color: {c['text']}; box-shadow: none;")
    css += rule(".termia-main-surface", f"background-color: {c['canvas']}; color: {c['text']};")
    css += rule(".termia-sidebar,.termia-panel,.stat-card,frame.card", f"background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; box-shadow: none;")
    css += rule("listview,listbox", f"background-color: {c['surface']}; color: {c['text']};")
    css += rule("row", "background-color: transparent;")
    css += rule("row:hover", f"background-color: {c['hover']};")
    css += rule("row:selected,.termia-connections-tree > row:selected .termia-sidebar-object", f"background-color: {c['selection']}; color: {c['text']}; border-radius: 10px;")
    css += rule("popover > contents", f"background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; box-shadow: none;")
    css += rule("button", f"background-image: none; background-color: {c['control']}; color: {c['text']}; border-color: {c['border']}; border-radius: 10px; box-shadow: none; text-shadow: none;")
    css += rule("button:not(.flat),entry,spinbutton", f"background-color: {c['control']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; box-shadow: none;")
    css += rule("button:hover", f"background-color: {c['hover']}; border-color: {c['cyan']};")
    css += rule("button:active,button:checked", f"background-color: {c['selection']}; border-color: {c['cyan']};")
    css += rule("button.suggested-action", f"background-color: #264C3A; border-color: {c['green']}; color: {c['text']};")
    css += rule("button.destructive-action", f"background-color: #5A2C37; border-color: {c['red']}; color: {c['text']};")
    css += rule("button:disabled", f"background-color: {c['surface']}; color: {c['muted']}; border-color: {c['border']}; box-shadow: none; text-shadow: none;")
    css += rule("entry:disabled", f"color: {c['muted']}; border-color: {c['border']};")
    css += rule("button:focus-visible,entry:focus-within,spinbutton:focus-within", f"outline: 2px solid {c['cyan']}; outline-offset: 2px;")
    css += rule(".termia-tab-label", "background-color: transparent; border: 1px solid transparent; border-radius: 10px; box-shadow: none;")
    css += rule(".termia-notes-notebook > header,.termia-notes-notebook > header > tabs", f"background-color: {c['surface']};")
    css += rule(".dim-label", f"color: {c['muted']}; opacity: 1;")
    for role in ("cyan", "violet", "green", "yellow", "red"):
        css += rule(f".termia-panel.termia-role-{role},.termia-notification.termia-role-{role}", f"border-color: {c[role]};")
        css += rule(f".termia-role-{role} progressbar > trough > progress", f"background-color: {c[role]}; border-color: {c[role]};")
    alert = f"{root}.dialog.message"
    alert_rules = (
        ("", f"background-color: {c['canvas']}; color: {c['text']}; border: 1px solid alpha({border_color}, 0.65); border-radius: 10px; box-shadow: 0 0 4px alpha({border_color}, 0.18);"),
        (":backdrop", f"border-color: alpha({border_color}, 0.35); box-shadow: none;"),
        (" .dialog-vbox", f"background-color: {c['canvas']}; color: {c['text']}; padding: 16px 0 0;"),
        (" .dialog-action-box", "background-image: none; background-color: transparent; border: 0; padding: 0 16px 16px;"),
        (" .dialog-action-area", "border-spacing: 8px;"),
        (" .dialog-action-area button", "min-height: 24px; padding: 4px 12px; border-width: 1px; border-style: solid; border-radius: 8px; font-size: 1em;"),
    )
    for suffix, declarations in alert_rules:
        css += f"{alert}{suffix} {{ {declarations} }} "
    titlebar_selectors = ", ".join(
        f"{alert} {selector}" for selector in (
            "headerbar", ".titlebar:not(headerbar)",
            "headerbar:backdrop", ".titlebar:not(headerbar):backdrop",
        )
    )
    css += f"{titlebar_selectors} {{ background-image: none; background-color: {c['surface']}; color: {c['text']}; border: 0; border-radius: 9px 9px 0 0; box-shadow: none; min-height: 32px; padding: 4px 8px; }} "
    return css


def build_interaction_css(
    theme: str, terminal_background: str, terminal_foreground: str,
    border_color: str = DEFAULT_DARK_GLOW_BORDER_COLOR,
) -> str:
    """Dark Glow pane, tab and native menu states; ordinary themes retain GTK."""
    if theme != DARK_GLOW_THEME:
        return ""
    accent = border_color
    foreground = DARK_GLOW_COLORS["text"]
    hover = DARK_GLOW_COLORS["hover"]
    selected = DARK_GLOW_COLORS["selection"]
    muted = DARK_GLOW_COLORS["muted"]
    surface = DARK_GLOW_COLORS["surface"]
    selection_background = DARK_GLOW_COLORS["selection"]
    selection_foreground = DARK_GLOW_COLORS["text"]
    prefix = f"window.{DARK_GLOW_CLASS} "
    rules = []

    def rule(selectors: str, declarations: str) -> None:
        scoped = ", ".join(prefix + selector.strip() for selector in selectors.split(","))
        rules.append(f"{scoped} {{ {declarations} }} ")

    rule(".termia-split-pane > separator,.termia-split-pane > separator:hover",
         "background: transparent; border: 0; margin: 0; padding: 0; box-shadow: none;")
    rule(".termia-split-pane.horizontal > separator", "min-width: 8px;")
    rule(".termia-split-pane.vertical > separator", "min-height: 8px;")

    rule("headerbar.termia-main-header",
         f"background-image: none; background-color: {surface}; color: {foreground}; "
         f"border: 1px solid alpha({accent}, 0.18); border-radius: 10px; "
         "margin: 8px 8px 0; box-shadow: none;")
    rule("headerbar.termia-main-header:backdrop",
         f"border-color: alpha({accent}, 0.12); box-shadow: none;")
    rule(".termia-main-surface", "padding: 8px;")
    rule(".termia-sidebar",
         f"background-color: {surface}; color: {foreground}; "
         f"border: 1px solid alpha({accent}, 0.35); border-radius: 10px; padding: 8px 10px;")
    rule(".termia-sidebar:focus-within",
         f"border-color: alpha({accent}, 0.65); "
         f"box-shadow: inset 0 0 4px alpha({accent}, 0.10);")
    separator = "paned.termia-main-paned > separator"
    rule(separator, "background-image: none; background-color: transparent; "
         "border: 0; min-width: 8px; margin: 0; padding: 0; box-shadow: none;")
    rule(f"{separator}:hover,{separator}:active,{separator}:selected",
         f"background-color: alpha({accent}, 0.12);")
    rule(f"{separator}:focus-visible",
         f"outline: 1px solid {accent}; outline-offset: -1px;")
    rule(".termia-session-tab-controls", "padding: 0; margin-bottom: 8px;")
    rule(".termia-session-tabs", "padding: 0; border-spacing: 8px;")
    rule(".termia-tab-label", "margin: 0;")

    preview = ".termia-terminal-paste-preview"
    rule(f"{preview},{preview} textview,{preview} textview > text,{preview} textview > border",
         f"background-color: {surface}; color: {foreground};")
    rule(preview, f"border: 1px solid alpha({accent}, 0.35); border-radius: 8px;")
    rule(f"{preview} textview", "padding: 8px 10px;")
    rule(f"{preview} textview > text > selection",
         f"background-color: {selection_background}; color: {selection_foreground};")
    rule(f"{preview} scrollbar slider", f"background-image: none; background-color: alpha({accent}, 0.35);")
    rule(f"{preview} scrollbar slider:hover", f"background-color: alpha({accent}, 0.65);")
    rule(f"{preview} scrollbar slider:active", f"background-color: {accent};")

    rule(".termia-terminal-pane", "border: 0; border-radius: 0; box-shadow: none;")
    rule(".termia-terminal-pane > .termia-pane-status,.termia-pane-status.active",
         f"background-color: {terminal_background}; color: {terminal_foreground}; "
         f"border: 1px solid alpha({accent}, 0.35); border-radius: 999px; "
         "box-shadow: none; padding: 3px 12px; margin-bottom: 8px; font-size: 0.9em;")
    rule(".termia-pane-status > label", f"color: {terminal_foreground}; opacity: 1;")
    rule(".termia-pane-status > label,.termia-pane-status button",
         'font-family: "Ubuntu Mono", "DejaVu Sans Mono", monospace;')
    rule(".termia-pane-status button",
         f"background-image: none; background-color: transparent; color: {terminal_foreground}; "
         "border: 0; box-shadow: none; min-height: 18px; padding: 2px 6px; "
         "border-radius: 6px; font-size: 1em;")
    rule(".termia-pane-status button:hover", f"background-color: alpha({terminal_foreground}, 0.08);")
    rule(".termia-pane-status button:active", f"background-color: alpha({terminal_foreground}, 0.13);")
    rule(".termia-pane-status button:disabled", "background-color: transparent; opacity: 0.45;")

    rule(".termia-terminal-pane > scrolledwindow",
         f"border: 1px solid alpha({accent}, 0.35); border-radius: 10px;")
    rule(".termia-terminal-pane vte-terminal", "padding: 6px 8px;")
    rule(".termia-terminal-pane:focus-within > scrolledwindow",
         f"border-color: alpha({accent}, 0.50); box-shadow: 0 0 3px alpha({accent}, 0.05);")

    note_tab = ".termia-notes-notebook > header > tabs > tab"
    tabs = (".termia-tab-label", note_tab)
    for tab in tabs:
        rule(tab, f"box-shadow: inset 0 0 0 1px alpha({accent}, 0.35);")
        rule(f"{tab}:hover", f"background-color: {hover}; "
             f"box-shadow: inset 0 0 0 1px alpha({accent}, 0.65);")
        active = f"{tab}.active" if tab == ".termia-tab-label" else f"{tab}:checked"
        rule(active, f"background-color: {selected}; "
             f"box-shadow: inset 0 0 0 1px alpha({accent}, 0.65), 0 0 3px alpha({accent}, 0.08);")
        rule(f"{tab}:focus-visible,{tab}:focus-within",
             f"outline: 2px solid {accent}; outline-offset: -3px;")
    rule(".termia-tab-label.dragging",
         f"background-color: alpha({accent}, 0.25); opacity: 0.72;")

    menu_items = (".termia-menu-popover modelbutton",
                  "dropdown.termia-choice popover listview > row")
    for item in menu_items:
        enabled = f"{item}:not(:disabled)"
        rule(f"{enabled}:hover,{enabled}:focus",
             f"background-color: {hover}; color: {foreground};")
        rule(f"{enabled}:selected,{enabled}:active",
             f"background-color: {selected}; color: {foreground};")
        rule(f"{enabled}:focus-visible",
             f"outline: 2px solid {accent}; outline-offset: -2px;")
        rule(f"{item}:disabled",
             f"background-color: transparent; color: {muted}; box-shadow: none; outline: none;")
    return "".join(rules)
