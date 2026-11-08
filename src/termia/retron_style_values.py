# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared Retron design values, independent of GTK and application state."""
from types import MappingProxyType

DEFAULT_DARK_GLOW_BORDER_COLOR = "#55BAC9"
DARK_GLOW_SURFACE_COLOR = "#182231"
DARK_GLOW_THEME = "dark_glow"
DARK_GLOW_CLASS = "termia-dark-glow"
DARK_GLOW_COLORS = MappingProxyType({
    "canvas": "#0D1420", "surface": DARK_GLOW_SURFACE_COLOR, "control": "#1C2A3C",
    "hover": "#23364B", "selection": "#29475A", "text": "#EDF3F8",
    "muted": "#B3C1D1", "border": "#345667", "cyan": DEFAULT_DARK_GLOW_BORDER_COLOR,
    "violet": "#A194D6", "green": "#78BD97", "yellow": "#D2B36F", "red": "#D8848D",
    "slider_hover": "#FFFFFF",
})

BORDER_WIDTH = 1.0
BORDER_RADIUS = 10.0
FRAME_OPACITY = 0.35
FOCUS_FRAME_OPACITY = 0.50
STRONG_FRAME_OPACITY = 0.65
HEADER_FRAME_OPACITY = 0.18
HEADER_BACKDROP_OPACITY = 0.12
WINDOW_OPACITY = 0.75
WINDOW_GLOW_BLUR = 2.0
WINDOW_GLOW_OPACITY = 0.05
HELD_GLOW_OPACITY = 0.08
GLOW_BLUR = 3.0
GLOW_OPACITY = 0.08
SIDEBAR_GLOW_BLUR = 4.0
SIDEBAR_GLOW_OPACITY = 0.10
