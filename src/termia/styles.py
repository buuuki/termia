# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations


def build_application_css(menu_background: str) -> bytes:
    return (
        f"@define-color termia_menu_bg {menu_background}; "
        ".termia-tree-item { border-radius: 4px; } "
        ".termia-server-item { padding-top: 2px; padding-bottom: 2px; } "
        ".prompt-preset-button { padding: 1px 6px; min-height: 24px; } "
        "headerbar { background: @headerbar_backdrop_color; border-bottom-width: 0; box-shadow: none; } "
        "headerbar:backdrop { background: @headerbar_backdrop_color; } "
        ".termia-session-tabs { background: @headerbar_backdrop_color; padding: 4px 4px 3px 4px; "
        "border: 0; box-shadow: none; } "
        ".termia-terminal-stack { border: 0; box-shadow: none; } .termia-menu-separator { min-height: 0; border-top: 1px solid rgba(128, 128, 128, 0.35); margin: 4px 12px; } "
        "popover.termia-menu-popover > contents { background: @termia_menu_bg; "
        "background-color: @termia_menu_bg; background-image: none; opacity: 1; } "
        ".termia-menu-panel { background: @termia_menu_bg; "
        "background-color: @termia_menu_bg; background-image: none; opacity: 1; } "
        ".termia-menu-panel list { background: transparent; background-color: transparent; } "
        ".termia-tab-label { padding: 7px 10px; margin: 0 2px; border-radius: 8px; "
        "background: transparent; border: 0; box-shadow: none; } "
        ".termia-tab-label:hover { background: alpha(@theme_fg_color, 0.06); } "
        ".termia-tab-label.active { background: alpha(@theme_fg_color, 0.13); } "
        ".termia-tab-label.dragging { background: alpha(@theme_selected_bg_color, 0.25); opacity: 0.72; } "
        ".termia-tab-title { font-size: 1.05em; } "
        ".termia-tab-close { padding: 0; min-width: 18px; min-height: 18px; } "
        ".termia-status-hide { padding: 0 6px; min-height: 18px; font-size: 0.85em; } "
        ".termia-disconnect-button { padding: 0 6px; min-height: 18px; font-size: 0.85em; } "
        ".stat-card { padding: 10px 12px; border: 1px solid @borders; border-radius: 6px; "
        "background: alpha(@theme_bg_color, 0.58); } "
        ".stat-card-title { font-size: 0.82em; } "
        ".stat-card-value { font-size: 1.55em; font-weight: 700; } "
        ".stat-card-subtitle { font-size: 0.82em; } "
        ".stat-row { padding: 6px 8px; border-bottom: 1px solid alpha(@borders, 0.55); } "
        ".termia-tree-item.selected { "
        "background-color: @theme_selected_bg_color; "
        "color: @theme_selected_fg_color; }"
    ).encode()
