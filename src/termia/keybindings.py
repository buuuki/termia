# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

DEFAULT_KEYBINDINGS: dict[str, str] = {
    "copy": "Ctrl+Shift+C",
    "paste": "Ctrl+Shift+V",
    "previous_tab": "Ctrl+PageUp",
    "next_tab": "Ctrl+PageDown",
    "font_increase": "Ctrl++",
    "font_decrease": "Ctrl+-",
    "send_password": "Ctrl+P",
}

KEYBINDING_ACTIONS: tuple[tuple[str, str], ...] = (
    ("copy", "keybinding_action_copy"),
    ("paste", "keybinding_action_paste"),
    ("previous_tab", "keybinding_action_previous_tab"),
    ("next_tab", "keybinding_action_next_tab"),
    ("font_increase", "keybinding_action_font_increase"),
    ("font_decrease", "keybinding_action_font_decrease"),
    ("send_password", "keybinding_action_send_password"),
)

KEYBINDING_CHOICES: tuple[str, ...] = (
    "",
    "Ctrl+Shift+C",
    "Ctrl+Shift+V",
    "Ctrl+PageUp",
    "Ctrl+PageDown",
    "Ctrl++",
    "Ctrl+-",
    "Ctrl+P",
    "Ctrl+Shift+P",
    "Alt+Left",
    "Alt+Right",
    "Alt+C",
    "Alt+V",
)

_MODIFIER_ORDER = ("Ctrl", "Shift", "Alt", "Super")
_MODIFIER_ALIASES = {
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "primary": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "mod1": "Alt",
    "super": "Super",
    "meta": "Super",
}
_KEY_ALIASES = {
    "pageup": "PageUp",
    "page_up": "PageUp",
    "prior": "PageUp",
    "pagedown": "PageDown",
    "page_down": "PageDown",
    "next": "PageDown",
    "plus": "+",
    "equal": "+",
    "kp_add": "+",
    "minus": "-",
    "underscore": "-",
    "kp_subtract": "-",
    "left": "Left",
    "right": "Right",
}
_KEYVAL_ALIASES = {
    "PageUp": {"page_up", "kp_page_up"},
    "PageDown": {"page_down", "kp_page_down"},
    "+": {"plus", "equal", "kp_add"},
    "-": {"minus", "underscore", "kp_subtract"},
    "Left": {"left", "kp_left"},
    "Right": {"right", "kp_right"},
}


def normalize_keybinding(accelerator: str) -> str:
    raw = accelerator.replace("<", "").replace(">", "+").strip()
    if raw.endswith("+"):
        parts = [part.strip() for part in raw[:-1].split("+")]
        parts.append("+")
    else:
        parts = [part.strip() for part in raw.split("+")]
    modifiers: list[str] = []
    key = ""
    for part in parts:
        if not part:
            continue
        alias = _MODIFIER_ALIASES.get(part.lower())
        if alias is not None:
            if alias not in modifiers:
                modifiers.append(alias)
            continue
        key = _KEY_ALIASES.get(part.lower(), part.upper() if len(part) == 1 else part)
    if not key:
        return ""
    ordered = [modifier for modifier in _MODIFIER_ORDER if modifier in modifiers]
    return "+".join([*ordered, key])


def normalize_keybindings(keybindings: dict[str, str] | None) -> dict[str, str]:
    normalized = DEFAULT_KEYBINDINGS.copy()
    if not isinstance(keybindings, dict):
        return normalized
    for action in DEFAULT_KEYBINDINGS:
        value = normalize_keybinding(str(keybindings.get(action, normalized[action])))
        normalized[action] = value
    return normalized


def keybinding_label(accelerator: str, disabled_label: str) -> str:
    normalized = normalize_keybinding(accelerator)
    return normalized or disabled_label


def keybinding_matches(accelerator: str, keyval: int, state: object) -> bool:
    normalized = normalize_keybinding(accelerator)
    if not normalized:
        return False

    from gi.repository import Gdk

    if normalized.endswith("++"):
        parts = [part for part in normalized[:-1].split("+") if part]
        parts.append("+")
    else:
        parts = normalized.split("+")
    key = parts[-1]
    modifiers = set(parts[:-1])
    modifier_masks = {
        "Ctrl": Gdk.ModifierType.CONTROL_MASK,
        "Shift": Gdk.ModifierType.SHIFT_MASK,
        "Alt": Gdk.ModifierType.ALT_MASK,
        "Super": Gdk.ModifierType.SUPER_MASK,
    }
    relevant_mask = (
        Gdk.ModifierType.CONTROL_MASK
        | Gdk.ModifierType.SHIFT_MASK
        | Gdk.ModifierType.ALT_MASK
        | Gdk.ModifierType.SUPER_MASK
    )
    required_mask = Gdk.ModifierType(0)
    for modifier in modifiers:
        required_mask |= modifier_masks[modifier]

    pressed_mask = state & relevant_mask
    if key in {"+", "-"} and "Shift" not in modifiers:
        pressed_mask &= ~Gdk.ModifierType.SHIFT_MASK
    if pressed_mask != required_mask:
        return False

    key_name = (Gdk.keyval_name(keyval) or "").lower()
    if len(key) == 1 and key.isalpha():
        return key_name == key.lower()
    return key_name in _KEYVAL_ALIASES.get(key, {key.lower()})
