# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned Retron values and bounded CSS generation, without GTK objects."""
from __future__ import annotations

import math
import re
from copy import deepcopy
from dataclasses import dataclass

from . import retron_style_values as retron

SCHEMA_VERSION = 1
MAX_PROFILE_BYTES = 65536
ACCENT = retron.DEFAULT_DARK_GLOW_BORDER_COLOR
SURFACE = retron.DARK_GLOW_SURFACE_COLOR
STATES = ("normal", "focus", "hover", "selected", "pressed", "backdrop", "held", "disabled")
ROOT = f"window.{retron.DARK_GLOW_CLASS}:not(.message):not(.termia-retron-editor)"


@dataclass(frozen=True)
class Component:
    selectors: tuple[str, ...]
    states: tuple[str, ...] = ("normal", "focus")
    inset: bool = False
    background: str = SURFACE
    opacity: float = 1.0
    # Selectors are internal constants; profiles can never provide selectors.
    background_children: tuple[str, ...] = ()


COMPONENTS = {
    "window": Component(("&.termia-main-window",), ("normal", "backdrop", "held"), background=retron.DARK_GLOW_COLORS["canvas"], opacity=retron.WINDOW_OPACITY),
    "header": Component(("headerbar",), ("normal", "focus", "backdrop")),
    "sidebar": Component((".termia-sidebar", ".termia-notes-tree"), background_children=(".termia-sidebar listview",)),
    "tabs": Component((".termia-tab-label", ".termia-notes-notebook > header > tabs > tab"),
                      ("normal", "hover", "selected", "focus"), inset=True, opacity=0.0),
    "panels": Component((".termia-panel", ".termia-surface-panel:not(.termia-notes-tree)", ".stat-card", "frame.card",
                         "frame.termia-preference-frame", "frame.termia-notes-toolbar-frame"), inset=True),
    "buttons": Component(("button:not(.termia-tab-close):not(.minimize):not(.maximize):not(.close)",
                          "windowcontrols button.minimize > image",
                          "windowcontrols button.maximize > image",
                          "windowcontrols button.close > image"),
                         ("normal", "hover", "pressed", "focus", "disabled"), background=retron.DARK_GLOW_COLORS["control"]),
    "fields": Component(("entry", "spinbutton"), ("normal", "focus", "disabled"),
                        background=retron.DARK_GLOW_COLORS["control"]),
    "menus": Component(("popover > contents",)),
    "dialogs": Component((".termia-dialog-panel",), inset=True),
    "secondary": Component(("&:not(.termia-main-window)",), ("normal", "backdrop", "held"), background=retron.DARK_GLOW_COLORS["canvas"], opacity=retron.WINDOW_OPACITY),
    "terminal": Component((".termia-terminal-pane > scrolledwindow",)),
    "content": Component((".termia-content-frame", ".termia-text-surface"),
                         background_children=(".termia-text-surface textview", ".termia-text-surface textview > text")),
    "notes": Component(("frame.termia-notes-editor",), inset=True,
                       background_children=(".termia-notes-editor textview", ".termia-notes-editor textview text")),
}

# UI and validation share one property inventory. Numeric units are logical px,
# percentages use 0..1, and all colors are canonical opaque hex plus alpha.
NUMBERS = {
    "border_opacity": (0.0, 1.0, 0.01), "border_width": (0.0, 8.0, 1.0),
    "radius": (0.0, 48.0, 1.0), "background_opacity": (0.0, 1.0, 0.01),
    "gradient_angle": (0.0, 360.0, 1.0),
}
CHOICES = {"border_style": ("none", "solid", "dashed", "dotted", "double"),
           "background_mode": ("solid", "linear", "radial")}
COLORS = ("border_color", "background_color", "gradient_color")
PROPERTIES = (*COLORS, *NUMBERS, *CHOICES, "shadows")
BORDER_KEYS = ("border_color", "border_opacity", "border_width", "border_style", "radius")
BACKGROUND_KEYS = ("background_color", "background_opacity", "background_mode", "gradient_color", "gradient_angle")
SHADOW_NUMBERS = {"opacity": (0, 1, 0.01), "blur": (0, 32, 1), "spread": (-8, 16, 1),
                  "x": (-24, 24, 1), "y": (-24, 24, 1)}


def empty_profile(accent: str = ACCENT) -> dict:
    return {"schema_version": SCHEMA_VERSION, "theme": retron.DARK_GLOW_THEME, "accent": color(accent), "common": {}, "components": {}}


def new_shadow() -> dict:
    return {"color": ACCENT, "opacity": retron.GLOW_OPACITY, "blur": retron.GLOW_BLUR, "spread": 0.0,
            "x": 0.0, "y": 0.0, "inset": False}


def color(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None:
        raise ValueError("Invalid Retron color")
    return value.upper()


def number(value: object, limits: tuple) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("Invalid Retron number")
    if not limits[0] <= value <= limits[1] or not math.isfinite(value):
        raise ValueError("Retron number outside supported range")
    return float(value)


def validate_patch(patch: object) -> dict:
    if not isinstance(patch, dict) or set(patch) - set(PROPERTIES):
        raise ValueError("Unknown Retron property")
    result = {}
    for key, value in patch.items():
        if key in COLORS:
            result[key] = color(value)
        elif key in NUMBERS:
            result[key] = number(value, NUMBERS[key])
        elif key in CHOICES:
            if value not in CHOICES[key]:
                raise ValueError("Invalid Retron choice")
            result[key] = value
        else:
            if not isinstance(value, list) or len(value) > 3:
                raise ValueError("At most three Retron shadows are supported")
            shadows = []
            for shadow in value:
                if not isinstance(shadow, dict) or set(shadow) != set(new_shadow()):
                    raise ValueError("Invalid Retron shadow")
                if not isinstance(shadow["inset"], bool):
                    raise TypeError("Invalid Retron shadow placement")
                shadows.append({"color": color(shadow["color"]), "inset": shadow["inset"],
                                **{name: number(shadow[name], limits) for name, limits in SHADOW_NUMBERS.items()}})
            result[key] = shadows
    return result


def validate_profile(profile: object) -> dict:
    if not isinstance(profile, dict) or set(profile) != set(empty_profile()):
        raise ValueError("Invalid Retron profile")
    if type(profile["schema_version"]) is not int or profile["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported Retron profile version")
    if profile["theme"] != retron.DARK_GLOW_THEME:
        raise ValueError("Invalid Retron theme")

    def states(values, allowed):
        if not isinstance(values, dict) or set(values) - set(allowed):
            raise ValueError("Unknown Retron state")
        validated = {state: validate_patch(patch) for state, patch in values.items()}
        return {state: patch for state, patch in validated.items() if patch}

    components = profile["components"]
    if not isinstance(components, dict) or set(components) - set(COMPONENTS):
        raise ValueError("Unknown Retron component")
    result = empty_profile()
    result["accent"] = color(profile["accent"])
    result["common"] = states(profile["common"], STATES)
    result["components"] = {key: states(value, COMPONENTS[key].states) for key, value in components.items()}
    result["components"] = {key: value for key, value in result["components"].items() if value}
    # VTE backgrounds are solid and state-independent. Common gradients are
    # allowed, but the VTE adapter deliberately reduces them to a solid color.
    for state, patch in result["components"].get("terminal", {}).items():
        if state != "normal" and set(patch) & set(BACKGROUND_KEYS):
            raise ValueError("Terminal backgrounds have no focus states")
        if patch.get("background_mode", "solid") != "solid":
            raise ValueError("VTE supports solid backgrounds only")
    return result


def defaults(component: str, state: str, *, accent: str = ACCENT,
             terminal_background: str = SURFACE, notes_background: str = "#001B33") -> dict:
    spec = COMPONENTS.get(component, COMPONENTS["panels"])
    alpha = retron.FRAME_OPACITY
    if component in ("window", "secondary"):
        alpha = retron.FRAME_OPACITY if state == "backdrop" else retron.FOCUS_FRAME_OPACITY
    elif component == "header":
        alpha = retron.HEADER_BACKDROP_OPACITY if state == "backdrop" else retron.HEADER_FRAME_OPACITY
    elif state in ("focus", "selected", "hover", "held"):
        alpha = retron.FOCUS_FRAME_OPACITY if component in ("terminal", "notes", "panels", "dialogs") else retron.STRONG_FRAME_OPACITY
    background = spec.background
    if component == "terminal":
        background = terminal_background
    elif component == "notes":
        background = notes_background
    elif state in ("hover", "selected", "pressed"):
        background = retron.DARK_GLOW_COLORS["hover" if state == "hover" else "selection"]
    shadows = []
    if component in ("window", "secondary") and state != "backdrop":
        shadows = [{**new_shadow(), "color": accent, "blur": retron.WINDOW_GLOW_BLUR,
                    "opacity": retron.HELD_GLOW_OPACITY if state == "held" else retron.WINDOW_GLOW_OPACITY}]
    elif component == "terminal" and state == "focus":
        shadows = [{**new_shadow(), "color": accent, "opacity": retron.WINDOW_GLOW_OPACITY}]
    elif component == "tabs" and state == "selected":
        shadows = [{**new_shadow(), "color": accent}]
    elif component == "sidebar" and state == "focus":
        shadows = [{**new_shadow(), "color": accent, "blur": retron.SIDEBAR_GLOW_BLUR,
                    "opacity": retron.SIDEBAR_GLOW_OPACITY, "inset": True}]
    border_color = accent
    if component == "fields":
        border_color = accent if state == "focus" else retron.DARK_GLOW_COLORS["border"]
        alpha = 1.0
    return {"border_color": border_color, "border_opacity": alpha, "border_width": retron.BORDER_WIDTH,
            "border_style": "solid", "radius": retron.BORDER_RADIUS, "background_color": background,
            "background_opacity": 1.0 if component == "tabs" and state in ("hover", "selected") else spec.opacity,
            "background_mode": "solid", "gradient_color": retron.DARK_GLOW_COLORS["hover"], "gradient_angle": 90.0,
            "shadows": shadows}


def overrides(profile: dict, component: str, state: str) -> dict:
    common = profile["common"]
    own = profile["components"].get(component, {})
    result = {**common.get("normal", {}), **common.get(state, {}),
              **own.get("normal", {}), **own.get(state, {})}
    if component == "terminal":
        # The terminal's cell background is always resolved from normal.
        for key in BACKGROUND_KEYS:
            result.pop(key, None)
        if state == "normal":
            result.update({key: value for key, value in {**common.get("normal", {}), **own.get("normal", {})}.items()
                           if key in BACKGROUND_KEYS})
    return result


def resolved(profile: dict, component: str, state: str, **context) -> dict:
    return deepcopy({**defaults(component, state, **context), **overrides(profile, component, state)})


def rgba(hex_color: str, opacity: float) -> str:
    return f"alpha({hex_color}, {opacity:g})"


def shadow_css(shadow: dict) -> str:
    inset = "inset " if shadow["inset"] else ""
    return (f"{inset}{shadow['x']:g}px {shadow['y']:g}px {shadow['blur']:g}px {shadow['spread']:g}px "
            f"{rgba(shadow['color'], shadow['opacity'])}")


def selector_for(selector: str, state: str) -> str:
    if selector.endswith(" > image"):
        return selector_for(selector.removesuffix(" > image"), state) + " > image"
    base = ROOT + selector[1:] if selector.startswith("&") else ROOT + " " + selector
    if state == "backdrop":
        return base.replace(ROOT, ROOT + ":backdrop", 1)
    if state == "held":
        return base + ".termia-title-held"
    if state == "focus" and selector == ".termia-terminal-pane > scrolledwindow":
        return base.replace(".termia-terminal-pane >", ".termia-terminal-pane:focus-within >")
    suffix = {"normal": "", "focus": ":focus-within", "hover": ":hover", "pressed": ":active",
              "selected": ".active" if selector == ".termia-tab-label" else ":checked", "disabled": ":disabled"}
    return base + suffix[state]


def build_profile_css(profile: dict, **context) -> str:
    profile = validate_profile(profile)
    rules = []
    for component, spec in COMPONENTS.items():
        for state in spec.states:
            patch = overrides(profile, component, state)
            if not patch:
                continue
            values = resolved(profile, component, state, **context)
            declarations = []
            border_changed = bool(set(patch) & set(BORDER_KEYS))
            if border_changed:
                declarations.extend(((f"border: {values['border_width']:g}px {values['border_style']} "
                                      f"{rgba(values['border_color'], values['border_opacity'])};"),
                                     f"border-radius: {values['radius']:g}px;"))
                if component == "fields" and state == "focus":
                    # The customized focus border replaces the fixed cyan ring.
                    # Background/glow-only edits retain the original focus cue.
                    declarations.append("outline: none;")
            if border_changed or "shadows" in patch:
                shadows = [shadow_css(item) for item in values["shadows"]]
                if spec.inset and not border_changed:
                    shadows.insert(0, f"inset 0 0 0 {values['border_width']:g}px "
                                   f"{rgba(values['border_color'], values['border_opacity'])}")
                declarations.append("box-shadow: " + (", ".join(shadows) or "none") + ";")
            background = []
            if set(patch) & set(BACKGROUND_KEYS):
                first = rgba(values["background_color"], values["background_opacity"])
                second = rgba(values["gradient_color"], values["background_opacity"])
                mode = values["background_mode"] if component != "terminal" else "solid"
                gradient = "none"
                if mode == "linear":
                    gradient = f"linear-gradient({values['gradient_angle']:g}deg, {first}, {second})"
                elif mode == "radial":
                    gradient = f"radial-gradient(circle, {first}, {second})"
                # A gradient over the same translucent solid would paint twice.
                background = [f"background-color: {first if mode == 'solid' and component != 'terminal' else 'transparent'};",
                              f"background-image: {gradient};"]
                declarations.extend(background)
            selectors = ", ".join(selector_for(selector, state) for selector in spec.selectors)
            rules.append(selectors + " { " + " ".join(declarations) + " }")
            if background:
                for selector in spec.background_children:
                    # Paint the parent once. Scrolling children reveal that layer.
                    rules.append(selector_for(selector, state) + " { background: transparent; }")
    return "\n".join(rules)
