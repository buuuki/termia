# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from .constants import DEFAULT_NOTES_EDITOR_BACKGROUND, DEFAULT_NOTES_EDITOR_FOREGROUND


def build_application_css(
    terminal_background: str,
    split_separator_color: str,
    split_separator_thickness: int,
) -> bytes:
    thickness = max(1, split_separator_thickness)
    handle_size = max(5, thickness)
    return (
        ".termia-connections-tree { background: transparent; } "
        ".termia-connections-tree > row { padding: 2px 4px; } "
        ".termia-connections-tree > row:selected { background: transparent; color: @theme_fg_color; } "
        ".termia-sidebar-object { padding: 2px 6px; border-radius: 4px; } "
        ".termia-connections-tree > row:selected .termia-sidebar-object { "
        "background: @theme_selected_bg_color; color: @theme_selected_fg_color; } "
        ".termia-group-drop-target.drop-target { background: alpha(@theme_selected_bg_color, 0.24); "
        "box-shadow: inset 0 0 0 1px @theme_selected_bg_color; border-radius: 4px; } "
        ".termia-server-item.dragging { opacity: 0.65; } "
        ".prompt-preset-button { padding: 1px 6px; min-height: 24px; } "
        ".termia-add-icon-badge { background: @theme_bg_color; border-radius: 999px; } "
        "headerbar { background: @headerbar_backdrop_color; border-bottom-width: 0; box-shadow: none; } "
        "headerbar:backdrop { background: @headerbar_backdrop_color; } "
        ".termia-terminal-notebook > header { background: @headerbar_backdrop_color; border-bottom-width: 0; } "
        ".termia-terminal-notebook > header > tabs > tab { background: transparent; border-radius: 8px 8px 0 0; min-height: 28px; padding: 0 6px; margin-left: 2px; margin-right: 2px; } "
        ".termia-terminal-notebook > header > tabs > tab:not(:checked):hover { background: alpha(@theme_fg_color, 0.06); box-shadow: none; } "
        ".termia-terminal-notebook > header > tabs > tab:checked, "
        ".termia-terminal-notebook > header > tabs > tab:checked:hover { background: alpha(@theme_fg_color, 0.13); box-shadow: none; } "
        ".termia-terminal-notebook:drop(active) { outline: none; box-shadow: none; border-color: transparent; } "
        ".termia-pane-status.active { background-color: alpha(@theme_selected_bg_color, 0.12); } "
        ".termia-pane-status > label { min-width: 0; } "
        ".termia-terminal-pane.in-split > .termia-pane-status { padding: 6px; } "
        f".termia-split-pane.horizontal > separator {{ min-width: {handle_size}px; "
        f"background: {terminal_background}; border-left: {thickness}px solid {split_separator_color}; }} "
        f".termia-split-pane.vertical > separator {{ min-height: {handle_size}px; "
        f"background: {terminal_background}; border-top: {thickness}px solid {split_separator_color}; }} "
        f".termia-split-pane.horizontal > separator:hover {{ border-left-color: alpha({split_separator_color}, 0.82); }} "
        f".termia-split-pane.vertical > separator:hover {{ border-top-color: alpha({split_separator_color}, 0.82); }} "
        ".termia-read-only-badge { font-weight: 600; } "
        ".termia-tab-label { padding: 0 10px; margin: 0 2px; border-radius: 8px; "
        "background: transparent; border: 0; box-shadow: none; transition: background-color 120ms ease-out, opacity 120ms ease-out; } "
        ".termia-tab-label.dragging { background: transparent; opacity: 0.72; } "
        ".termia-tab-drag-preview { background: alpha(@theme_selected_bg_color, 0.25); "
        "color: @theme_fg_color; border-radius: 8px; opacity: 0.72; } "
        ".termia-notes-notebook, .termia-notes-notebook > header, "
        ".termia-notes-notebook > header > tabs { background: transparent; border: 0; box-shadow: none; } "
        ".termia-notes-notebook > header > tabs > tab { border-radius: 8px 8px 0 0; } "
        ".termia-notes-notebook > header > tabs > tab:checked { background: alpha(@theme_fg_color, 0.13); } "
        ".termia-notes-editor { border: 1px solid @borders; border-radius: 8px; "
        f"background-color: {DEFAULT_NOTES_EDITOR_BACKGROUND}; }} "
        f".termia-notes-editor textview {{ color: {DEFAULT_NOTES_EDITOR_FOREGROUND}; "
        f"background-color: {DEFAULT_NOTES_EDITOR_BACKGROUND}; }} "
        ".termia-notes-editor textview text { "
        f"background-color: {DEFAULT_NOTES_EDITOR_BACKGROUND}; }} "
        ".termia-tab-title { font-size: 1.05em; } "
        ".termia-tab-close { padding: 0; min-width: 24px; min-height: 24px; border-radius: 9999px; } "
        ".termia-tab-close:hover { background: rgba(0, 0, 0, 0.16); box-shadow: none; } "
        ".termia-tab-close:active { background: rgba(0, 0, 0, 0.24); } "
        ".termia-tab-overflow-button { padding: 0; min-width: 0; min-height: 24px; margin: 1px 0 6px 0; } "
        ".termia-tab-overflow-button > button { padding-left: 1px; padding-right: 1px; min-width: 16px; } "
        ".termia-status-hide { padding: 0 6px; min-height: 18px; font-size: 0.85em; } "
        ".termia-disconnect-button { padding: 0 6px; min-height: 18px; font-size: 0.85em; } "
        ".stat-card { padding: 10px 12px; border: 1px solid @borders; border-radius: 6px; "
        "background: alpha(@theme_bg_color, 0.58); } "
        ".stat-card-title { font-size: 0.82em; } "
        ".stat-card-value { font-size: 1.55em; font-weight: 700; } "
        ".stat-card-subtitle { font-size: 0.82em; } "
        ".stat-row { padding: 6px 8px; border-bottom: 1px solid alpha(@borders, 0.55); } "
        "flowboxchild.termia-snippet-category-tile { padding: 0; border-radius: 8px; } "
        "flowboxchild.termia-snippet-category-tile:selected { "
        "background: transparent; box-shadow: none; } "
        "flowboxchild.termia-snippet-category-tile > frame.termia-snippet-category-frame { "
        "border-radius: 8px; } "
        "flowboxchild.termia-snippet-category-tile:selected > frame.termia-snippet-category-frame { "
        "background: alpha(@theme_selected_bg_color, 0.2); "
        "border-color: @theme_selected_bg_color; color: @theme_fg_color; } "
        ".termia-required-marker { font-size: 1.2em; font-weight: 700; } "
        ".termia-required-hint { color: alpha(@theme_fg_color, 0.8); } "
    ).encode()
