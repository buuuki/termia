# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, opt-in Retron palette. No dependency on optional tools or VTE."""

from . import retron_style_values as retron
from .retron_style_values import (
    DARK_GLOW_CLASS,
    DARK_GLOW_COLORS,
    DARK_GLOW_THEME,
    DEFAULT_DARK_GLOW_BORDER_COLOR,
)


def build_dark_glow_css(border_color: str = DEFAULT_DARK_GLOW_BORDER_COLOR) -> str:
    c = DARK_GLOW_COLORS
    root = f"window.{DARK_GLOW_CLASS}"

    def rule(selectors: str, declarations: str) -> str:
        return ", ".join(f"{root}{' ' if selector else ''}{selector}" for selector in selectors.split(",")) + " { " + declarations + " } "

    css = rule("", f"background-color: alpha({c['canvas']}, {retron.WINDOW_OPACITY:.2f}); color: {c['text']};")
    css += (
        f"{root} {{ border: {retron.BORDER_WIDTH:g}px solid alpha({border_color}, {retron.FOCUS_FRAME_OPACITY:.2f}); "
        f"border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: 0 0 {retron.WINDOW_GLOW_BLUR:g}px alpha({border_color}, {retron.WINDOW_GLOW_OPACITY:.2f}); }} "
        f"{root}:backdrop {{ border-color: alpha({border_color}, {retron.FRAME_OPACITY:.2f}); "
        "box-shadow: none; } "
    )
    css += rule("headerbar", f"background-color: {c['surface']}; color: {c['text']}; box-shadow: none;")
    css += rule(".titlebar:not(headerbar)", f"background-image: none; background-color: {c['surface']}; color: {c['text']}; box-shadow: none;")
    css += rule(".termia-session-tabs,.termia-session-tab-controls", f"background: transparent; color: {c['text']}; box-shadow: none;")
    # The window paints the translucent canvas once; a second layer would
    # raise its effective opacity above the configured value.
    css += rule(".termia-main-surface", f"background-color: transparent; color: {c['text']};")
    css += rule(".termia-sidebar,.termia-panel,.stat-card,frame.card", f"background-color: {c['surface']}; color: {c['text']}; border: {retron.BORDER_WIDTH:g}px solid {c['border']}; border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: none;")
    css += rule("listview,list", f"background-color: {c['surface']}; color: {c['text']};")
    css += rule("row", "background-color: transparent;")
    css += rule("row:hover", f"background-color: {c['hover']};")
    css += rule("row:selected,.termia-connections-tree > row:selected .termia-sidebar-object", f"background-color: {c['selection']}; color: {c['text']}; border-radius: {retron.BORDER_RADIUS:g}px;")
    css += rule("popover > contents", f"background-color: {c['surface']}; color: {c['text']}; border: {retron.BORDER_WIDTH:g}px solid {c['border']}; border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: none;")
    css += rule("button", f"background-image: none; background-color: {c['control']}; color: {c['text']}; border-color: {c['border']}; border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: none; text-shadow: none;")
    css += rule("button:not(.flat),entry,spinbutton", f"background-color: {c['control']}; color: {c['text']}; border: {retron.BORDER_WIDTH:g}px solid {c['border']}; border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: none;")
    css += rule("button:hover", f"background-color: {c['hover']}; border-color: {c['cyan']};")
    css += rule("button:active,button:checked", f"background-color: {c['selection']}; border-color: {c['cyan']};")
    css += rule("button.suggested-action", f"background-color: #264C3A; border-color: {c['green']}; color: {c['text']};")
    css += rule("button.destructive-action", f"background-color: #5A2C37; border-color: {c['red']}; color: {c['text']};")
    css += rule("button:disabled", f"background-color: {c['surface']}; color: {c['muted']}; border-color: {c['border']}; box-shadow: none; text-shadow: none;")
    css += rule("entry:disabled", f"color: {c['muted']}; border-color: {c['border']};")
    css += rule("button:focus-visible,entry:focus-within,spinbutton:focus-within", f"outline: 2px solid {c['cyan']}; outline-offset: 2px;")
    css += rule(".termia-tab-label", f"background-color: transparent; border: {retron.BORDER_WIDTH:g}px solid transparent; border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: none;")
    css += rule(".termia-notes-notebook,.termia-notes-notebook > stack,.termia-notes-notebook > header,.termia-notes-notebook > header > tabs",
                "background: transparent; border: 0; box-shadow: none;")
    css += rule(".dim-label", f"color: {c['muted']}; opacity: 1;")
    # Native controls keep their geometry and interaction; only Retron colors
    # change. Do not target textview globally: Notes owns its editor palette.
    css += rule("scrollbar", "background-color: transparent;")
    css += rule("scrollbar slider", f"background-image: none; background-color: alpha({border_color}, {retron.FRAME_OPACITY:.2f});")
    css += rule("scrollbar slider:hover", f"background-color: alpha({border_color}, {retron.STRONG_FRAME_OPACITY:.2f});")
    css += rule("scrollbar slider:active", f"background-color: {border_color};")
    editor = f"{root}.termia-retron-editor"
    scale_rules = (
        ("trough", f"background-image: none; background-color: alpha({c['muted']}, 0.55);"),
        ("highlight", f"background-image: none; background-color: {c['cyan']};"),
        ("slider", f"background-image: none; background-color: {c['text']}; border-color: {c['muted']};"),
        ("slider:hover", f"background-color: {c['slider_hover']};"),
        ("slider:active", f"background-color: {c['text']}; border-color: {c['cyan']};"),
        ("slider:disabled", f"background-color: {c['muted']}; border-color: {c['border']};"),
        ("trough:disabled", f"background-color: alpha({c['muted']}, 0.25);"),
        ("highlight:disabled", f"background-color: alpha({c['muted']}, 0.40);"),
    )
    for selector, declarations in scale_rules:
        css += f"{editor} scale {selector} {{ {declarations} }} "
    css += rule("checkbutton check,checkbutton radio,switch", f"background-image: none; background-color: {c['control']}; border-color: {c['border']}; color: {c['text']};")
    css += rule("checkbutton check:checked,checkbutton radio:checked,switch:checked", f"background-color: {c['selection']}; border-color: {border_color};")
    css += rule("switch slider", f"background-image: none; background-color: {c['muted']};")
    css += rule("checkbutton:disabled,switch:disabled", f"color: {c['muted']}; opacity: 0.5;")
    css += rule("checkbutton:focus-visible,switch:focus-visible", f"outline: 2px solid {border_color}; outline-offset: 2px;")
    css += rule("link,button.link", f"color: {c['cyan']};")
    css += rule("link:visited,button.link:visited", f"color: {c['violet']};")
    css += rule("progressbar trough,levelbar trough", f"background-color: {c['control']}; border-color: {c['border']};")
    css += rule("progressbar progress,levelbar block.filled", f"background-color: {c['cyan']}; border-color: {c['cyan']};")
    for role in ("cyan", "violet", "green", "yellow", "red"):
        css += rule(f".termia-panel.termia-role-{role},.termia-notification.termia-role-{role}", f"border-color: {c[role]};")
        css += rule(f".termia-role-{role} progressbar > trough > progress", f"background-color: {c[role]}; border-color: {c[role]};")
    alert = f"{root}.dialog.message"
    alert_rules = (
        ("", f"background-color: {c['canvas']}; color: {c['text']}; border: {retron.BORDER_WIDTH:g}px solid alpha({border_color}, {retron.STRONG_FRAME_OPACITY:.2f}); border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: 0 0 4px alpha({border_color}, 0.18);"),
        (":backdrop", f"border-color: alpha({border_color}, {retron.FRAME_OPACITY:.2f}); box-shadow: none;"),
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
    css += f"{titlebar_selectors} {{ background-image: none; background-color: {c['surface']}; color: {c['text']}; border: 0; border-radius: 9px 9px 0 0; box-shadow: none; min-height: 32px; padding: 4px 8px; margin: 0; }} "
    return css


def build_interaction_css(
    theme: str, terminal_background: str, terminal_foreground: str,
    border_color: str = DEFAULT_DARK_GLOW_BORDER_COLOR,
) -> str:
    """Retron pane, tab and native menu states; ordinary themes retain GTK."""
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
    panel_border = f"inset 0 0 0 {retron.BORDER_WIDTH:g}px alpha({accent}, {retron.FRAME_OPACITY:.2f})"
    panel_focus_border = f"inset 0 0 0 {retron.BORDER_WIDTH:g}px alpha({accent}, {retron.FOCUS_FRAME_OPACITY:.2f})"
    prefix = f"window.{DARK_GLOW_CLASS} "
    rules = []

    def rule(selectors: str, declarations: str) -> None:
        scoped = ", ".join(prefix + selector.strip() for selector in selectors.split(","))
        rules.append(f"{scoped} {{ {declarations} }} ")

    rule(".termia-split-pane > separator,.termia-split-pane > separator:hover",
         "background: transparent; border: 0; margin: 0; padding: 0; box-shadow: none;")
    rule(".termia-split-pane.horizontal > separator", "min-width: 8px;")
    rule(".termia-split-pane.vertical > separator", "min-height: 8px;")

    rule("headerbar",
         f"background-image: none; background-color: {surface}; color: {foreground}; "
         f"border: {retron.BORDER_WIDTH:g}px solid alpha({accent}, {retron.HEADER_FRAME_OPACITY:.2f}); border-radius: {retron.BORDER_RADIUS:g}px; "
         "margin: 8px 8px 0; box-shadow: none;")
    rule("headerbar:backdrop",
         f"border-color: alpha({accent}, {retron.HEADER_BACKDROP_OPACITY:.2f}); box-shadow: none;")
    rule(".termia-main-surface", "padding: 8px;")
    rule(".termia-detached-surface", "padding: 8px;")
    rule(".termia-sidebar",
         f"background-color: {surface}; color: {foreground}; "
         f"border: {retron.BORDER_WIDTH:g}px solid alpha({accent}, {retron.FRAME_OPACITY:.2f}); border-radius: {retron.BORDER_RADIUS:g}px; padding: 8px 10px;")
    rule(".termia-sidebar:focus-within",
         f"border-color: alpha({accent}, {retron.STRONG_FRAME_OPACITY:.2f}); "
         f"box-shadow: inset 0 0 {retron.SIDEBAR_GLOW_BLUR:g}px alpha({accent}, {retron.SIDEBAR_GLOW_OPACITY:.2f});")
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

    # Explicit roles opt secondary surfaces into the shared frame treatment.
    # Inset borders avoid resizing or clipping existing scrollable content.
    rule(".termia-surface-panel",
         f"background-color: {surface}; color: {foreground}; border-radius: {retron.BORDER_RADIUS:g}px; "
         f"box-shadow: {panel_border}; padding: 8px;")
    rule(".termia-dialog-panel",
         f"background-color: {surface}; color: {foreground}; border-radius: {retron.BORDER_RADIUS:g}px; "
         f"box-shadow: {panel_border}; margin: 8px; padding: 8px;")
    rule(".termia-dialog-panel:focus-within",
         f"box-shadow: {panel_focus_border};")
    rule(".termia-dialog-panel > .termia-dialog-content",
         "background-color: transparent; border: 0; border-radius: 0; "
         "box-shadow: none; margin: 0; padding: 0;")
    rule(".termia-content-frame,.termia-notes-editor,frame.termia-preference-frame",
         f"border: {retron.BORDER_WIDTH:g}px solid alpha({accent}, {retron.FRAME_OPACITY:.2f}); border-radius: {retron.BORDER_RADIUS:g}px;")
    rule(".termia-surface-panel:focus-within,.termia-content-frame:focus-within,.termia-notes-editor:focus-within",
         f"box-shadow: {panel_focus_border};")
    # Keep opaque scrolling children inside the frame's rounded boundary.
    rule("frame.termia-notes-editor,frame.termia-notes-toolbar-frame",
         f"border: 0; border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: {panel_border}; margin: 3px;")
    rule("frame.termia-notes-editor", "padding: 2px; margin-top: 0;")
    rule(".termia-notes-toolbar-hidden > frame.termia-notes-editor", "margin-top: 8px;")
    rule("frame.termia-notes-toolbar-frame",
         f"background-color: {surface}; padding: 6px; margin-top: 8px; margin-bottom: 0;")
    rule("frame.termia-notes-editor:focus-within,frame.termia-notes-toolbar-frame:focus-within",
         f"box-shadow: {panel_focus_border};")
    rule(".termia-text-surface,.termia-text-surface textview,.termia-text-surface textview > text,.termia-text-surface textview > border",
         f"background-color: {surface}; color: {foreground};")
    rule(".termia-text-surface textview", "padding: 8px;")
    rule(".termia-text-surface textview > text > selection",
         f"background-color: {selected}; color: {foreground};")
    rule("paned.termia-content-paned > separator",
         "background-image: none; background-color: transparent; border: 0; min-width: 4px;")
    rule("paned.termia-content-paned > separator:hover",
         f"background-color: alpha({accent}, 0.12);")
    rule("flowboxchild.termia-snippet-category-tile > frame.termia-snippet-category-frame",
         f"background-color: {surface}; color: {foreground}; border-color: alpha({accent}, {retron.FRAME_OPACITY:.2f});")
    rule("flowboxchild.termia-snippet-category-tile:selected > frame.termia-snippet-category-frame",
         f"background-color: {selected}; color: {foreground}; border-color: {accent};")

    preview = ".termia-terminal-paste-preview"
    rule(f"{preview},{preview} textview,{preview} textview > text,{preview} textview > border",
         f"background-color: {surface}; color: {foreground};")
    rule(preview, f"border: {retron.BORDER_WIDTH:g}px solid alpha({accent}, {retron.FRAME_OPACITY:.2f}); border-radius: 8px;")
    rule(f"{preview} textview", "padding: 8px 10px;")
    rule(f"{preview} textview > text > selection",
         f"background-color: {selection_background}; color: {selection_foreground};")
    rule(f"{preview} scrollbar slider", f"background-image: none; background-color: alpha({accent}, {retron.FRAME_OPACITY:.2f});")
    rule(f"{preview} scrollbar slider:hover", f"background-color: alpha({accent}, {retron.STRONG_FRAME_OPACITY:.2f});")
    rule(f"{preview} scrollbar slider:active", f"background-color: {accent};")

    rule(".termia-terminal-pane", "border: 0; border-radius: 0; box-shadow: none;")
    rule(".termia-terminal-pane > .termia-pane-status,.termia-pane-status.active",
         f"background-color: {terminal_background}; color: {terminal_foreground}; "
         f"border: {retron.BORDER_WIDTH:g}px solid alpha({accent}, {retron.FRAME_OPACITY:.2f}); border-radius: 999px; "
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
         f"border: {retron.BORDER_WIDTH:g}px solid alpha({accent}, {retron.FRAME_OPACITY:.2f}); border-radius: {retron.BORDER_RADIUS:g}px;")
    rule(".termia-terminal-pane vte-terminal", "padding: 6px 8px;")
    rule(".termia-terminal-pane:focus-within > scrolledwindow",
         f"border-color: alpha({accent}, {retron.FOCUS_FRAME_OPACITY:.2f}); box-shadow: 0 0 {retron.GLOW_BLUR:g}px alpha({accent}, {retron.WINDOW_GLOW_OPACITY:.2f});")

    note_tab = ".termia-notes-notebook > header > tabs > tab"
    tabs = (".termia-tab-label", note_tab)
    for tab in tabs:
        rule(tab, f"box-shadow: inset 0 0 0 {retron.BORDER_WIDTH:g}px alpha({accent}, {retron.FRAME_OPACITY:.2f});")
        rule(f"{tab}:hover", f"background-color: {hover}; "
             f"box-shadow: inset 0 0 0 {retron.BORDER_WIDTH:g}px alpha({accent}, {retron.STRONG_FRAME_OPACITY:.2f});")
        active = f"{tab}.active" if tab == ".termia-tab-label" else f"{tab}:checked"
        rule(active, f"background-color: {selected}; "
             f"box-shadow: inset 0 0 0 {retron.BORDER_WIDTH:g}px alpha({accent}, {retron.STRONG_FRAME_OPACITY:.2f}), 0 0 {retron.GLOW_BLUR:g}px alpha({accent}, {retron.GLOW_OPACITY:.2f});")
        rule(f"{tab}:focus-visible,{tab}:focus-within",
             f"outline: 2px solid {accent}; outline-offset: -3px;")
    rule(".termia-tab-label.dragging",
         f"background-color: alpha({accent}, 0.25); opacity: 0.72;")

    # Notes uses its tree panel's exact frame treatment for every container.
    # Keep these rules after tab states so hover/selection cannot add a halo.
    notes_window = f"window.{DARK_GLOW_CLASS}.termia-notes-window"
    notes_frames = [notes_window] + [
        f"{notes_window} {selector}" for selector in (
            "headerbar", ".termia-surface-panel", "frame.termia-notes-editor",
            "frame.termia-notes-toolbar-frame", note_tab,
        )
    ]
    rules.append(
        ", ".join(notes_frames)
        + f" {{ border: 0; border-radius: {retron.BORDER_RADIUS:g}px; box-shadow: {panel_border}; }} "
    )
    rules.append(
        ", ".join(f"{selector}:focus-within" for selector in notes_frames)
        + f" {{ box-shadow: {panel_focus_border}; }} "
    )
    held = f"window.{DARK_GLOW_CLASS}.termia-title-held:not(.message)"
    rules.append(f"{held} {{ border-color: alpha({accent}, {retron.STRONG_FRAME_OPACITY:.2f}); "
                 f"box-shadow: 0 0 {retron.WINDOW_GLOW_BLUR:g}px alpha({accent}, {retron.HELD_GLOW_OPACITY:.2f}); }} ")
    rules.append(f"{held}.termia-notes-window {{ "
                 f"box-shadow: inset 0 0 0 {retron.BORDER_WIDTH:g}px alpha({accent}, {retron.STRONG_FRAME_OPACITY:.2f}), "
                 f"0 0 {retron.WINDOW_GLOW_BLUR:g}px alpha({accent}, {retron.HELD_GLOW_OPACITY:.2f}); }} ")

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
