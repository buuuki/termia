# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, opt-in Dark Glow palette. No dependency on optional tools or VTE."""

DARK_GLOW_THEME = "dark_glow"
DARK_GLOW_CLASS = "termia-dark-glow"
DARK_GLOW_COLORS = {
    "canvas": "#0D1420", "surface": "#182231", "control": "#1C2A3C",
    "hover": "#23364B", "selection": "#29475A", "text": "#EDF3F8",
    "muted": "#B3C1D1", "border": "#345667", "cyan": "#55BAC9",
    "violet": "#A194D6", "green": "#78BD97", "yellow": "#D2B36F", "red": "#D8848D",
}


def build_dark_glow_css() -> str:
    c = DARK_GLOW_COLORS
    root = f"window.{DARK_GLOW_CLASS}"

    def rule(selectors: str, declarations: str) -> str:
        return ", ".join(f"{root}{' ' if selector else ''}{selector}" for selector in selectors.split(",")) + " { " + declarations + " } "

    css = rule("", f"background-color: {c['canvas']}; color: {c['text']};")
    css += rule("headerbar,.termia-session-tabs,.termia-session-tab-controls", f"background-color: {c['surface']}; color: {c['text']}; box-shadow: none;")
    css += rule(".termia-main-surface", f"background-color: {c['canvas']}; color: {c['text']};")
    css += rule(".termia-sidebar,.termia-panel,.stat-card,frame.card", f"background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; box-shadow: none;")
    css += rule("listview,listbox", f"background-color: {c['surface']}; color: {c['text']};")
    css += rule("row", "background-color: transparent;")
    css += rule("row:hover", f"background-color: {c['hover']};")
    css += rule("row:selected,.termia-connections-tree > row:selected .termia-sidebar-object", f"background-color: {c['selection']}; color: {c['text']}; border-radius: 10px;")
    css += rule("popover > contents", f"background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; box-shadow: none;")
    css += rule("button", "border-radius: 10px; box-shadow: none;")
    css += rule("button:not(.flat),entry,spinbutton", f"background-color: {c['control']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; box-shadow: none;")
    css += rule("button:hover", f"background-color: {c['hover']}; border-color: {c['cyan']};")
    css += rule("button:active", f"background-color: {c['selection']};")
    css += rule("button.suggested-action", f"background-color: #264C3A; border-color: {c['green']}; color: {c['text']};")
    css += rule("button.destructive-action", f"background-color: #5A2C37; border-color: {c['red']}; color: {c['text']};")
    css += rule("button:disabled,entry:disabled", f"color: {c['muted']}; border-color: {c['border']};")
    css += rule("button:focus-visible,entry:focus-within,spinbutton:focus-within", f"outline: 2px solid {c['cyan']}; outline-offset: 2px;")
    css += rule(".termia-tab-label", "background-color: transparent; border: 1px solid transparent; border-radius: 10px; box-shadow: none;")
    css += rule(".termia-tab-label:hover", f"background-color: {c['hover']};")
    css += rule(".termia-tab-label.active", f"background-color: {c['selection']}; border-color: {c['cyan']};")
    css += rule(".termia-notes-notebook > header,.termia-notes-notebook > header > tabs", f"background-color: {c['surface']};")
    css += rule(".termia-notes-notebook > header > tabs > tab:checked", f"background-color: {c['selection']}; border-color: {c['cyan']};")
    css += rule(".dim-label", f"color: {c['muted']}; opacity: 1;")
    for role in ("cyan", "violet", "green", "yellow", "red"):
        css += rule(f".termia-panel.termia-role-{role},.termia-notification.termia-role-{role}", f"border-color: {c[role]};")
        css += rule(f".termia-role-{role} progressbar > trough > progress", f"background-color: {c[role]}; border-color: {c[role]};")
    return css
