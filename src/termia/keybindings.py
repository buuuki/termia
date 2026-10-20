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
    "filter_servers": "Ctrl+F",
    "toggle_sidebar": "Ctrl+Shift+B",
    "toggle_main_menu": "F10",
    "new_local_terminal": "Ctrl+Shift+T",
    "focus_next_region": "Ctrl+F6",
    "focus_previous_region": "Ctrl+Shift+F6",
    "focus_split_left": "Ctrl+Left",
    "focus_split_right": "Ctrl+Right",
    "focus_split_up": "Ctrl+Up",
    "focus_split_down": "Ctrl+Down",
}

KEYBINDING_ACTIONS: tuple[tuple[str, str], ...] = (
    ("copy", "keybinding_action_copy"),
    ("paste", "keybinding_action_paste"),
    ("previous_tab", "keybinding_action_previous_tab"),
    ("next_tab", "keybinding_action_next_tab"),
    ("font_increase", "keybinding_action_font_increase"),
    ("font_decrease", "keybinding_action_font_decrease"),
    ("send_password", "keybinding_action_send_password"),
    ("filter_servers", "keybinding_action_filter_servers"),
    ("toggle_sidebar", "keybinding_action_toggle_sidebar"),
    ("toggle_main_menu", "keybinding_action_toggle_main_menu"),
    ("new_local_terminal", "keybinding_action_new_local_terminal"),
    ("focus_next_region", "keybinding_action_focus_next_region"),
    ("focus_previous_region", "keybinding_action_focus_previous_region"),
    ("focus_split_left", "keybinding_action_focus_split_left"),
    ("focus_split_right", "keybinding_action_focus_split_right"),
    ("focus_split_up", "keybinding_action_focus_split_up"),
    ("focus_split_down", "keybinding_action_focus_split_down"),
)

_MODIFIER_ORDER = ("Ctrl", "Shift", "Alt", "Super")
SNIPPET_ACTION_PREFIX = "snippet:"


class KeybindingError(ValueError):
    def __init__(self, message: str, shortcut: str = "") -> None:
        super().__init__(message)
        self.shortcut = shortcut


def snippet_action(snippet_id: str) -> str:
    return f"{SNIPPET_ACTION_PREFIX}{snippet_id}"


def is_snippet_action(action: str) -> bool:
    return isinstance(action, str) and action.startswith(SNIPPET_ACTION_PREFIX) and len(action) > len(SNIPPET_ACTION_PREFIX)


def validate_keybindings(keybindings: dict[str, str]) -> None:
    seen: set[str] = set()
    for action, shortcut in keybindings.items():
        shortcut = normalize_keybinding(shortcut)
        if not shortcut:
            continue
        if is_snippet_action(action) and not any(
            modifier in shortcut.split("+")[:-1] for modifier in ("Ctrl", "Alt", "Super")
        ):
            raise KeybindingError("snippet_shortcut_modifier_required")
        # +/- actions without Shift also match shifted variants in VTE dispatch.
        conflict_key = shortcut.replace("Shift+", "") if shortcut.endswith(("+", "-")) else shortcut
        if conflict_key in seen:
            raise KeybindingError("keybindings_conflict", shortcut)
        seen.add(conflict_key)


def merge_keybindings(current: dict[str, str], updates: dict[str, str],
                      previous: dict[str, str] | None = None) -> dict[str, str]:
    """Merge edited actions only; do not overwrite a newer edit from another window."""
    result = normalize_keybindings(current)
    for action, value in updates.items():
        if action not in DEFAULT_KEYBINDINGS and not is_snippet_action(action):
            continue
        value = normalize_keybinding(value)
        if previous is not None:
            before = normalize_keybinding(previous.get(action, ""))
            if value == before:
                continue
            if result.get(action, "") != before:
                raise KeybindingError("keybindings_changed")
        result[action] = value
    validate_keybindings(result)
    return result


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
    "kp_page_up": "PageUp",
    "pagedown": "PageDown",
    "page_down": "PageDown",
    "next": "PageDown",
    "kp_page_down": "PageDown",
    "plus": "+",
    "equal": "+",
    "kp_add": "+",
    "minus": "-",
    "underscore": "-",
    "kp_subtract": "-",
    "left": "Left",
    "kp_left": "Left",
    "right": "Right",
    "kp_right": "Right",
    "up": "Up",
    "kp_up": "Up",
    "down": "Down",
    "kp_down": "Down",
}
_KEYVAL_ALIASES = {
    "PageUp": {"page_up", "kp_page_up"},
    "PageDown": {"page_down", "kp_page_down"},
    "+": {"plus", "equal", "kp_add"},
    "-": {"minus", "underscore", "kp_subtract"},
    "Left": {"left", "kp_left"},
    "Right": {"right", "kp_right"},
    "Up": {"up", "kp_up"},
    "Down": {"down", "kp_down"},
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


def keybinding_from_event(keyval: int, state: object) -> str:
    from gi.repository import Gdk

    key_name = (Gdk.keyval_name(keyval) or "").strip()
    if not key_name:
        return ""

    normalized_name = key_name.lower()
    if normalized_name in {
        "shift_l",
        "shift_r",
        "control_l",
        "control_r",
        "alt_l",
        "alt_r",
        "super_l",
        "super_r",
        "meta_l",
        "meta_r",
        "hyper_l",
        "hyper_r",
    }:
        return ""

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
    modifiers: list[str] = []
    pressed_mask = state & relevant_mask
    for modifier, mask in modifier_masks.items():
        if pressed_mask & mask:
            modifiers.append(modifier)

    key = _KEY_ALIASES.get(normalized_name, key_name.upper() if len(key_name) == 1 else key_name)
    if key in {"+", "-"}:
        modifiers = [modifier for modifier in modifiers if modifier != "Shift"]

    ordered = [modifier for modifier in _MODIFIER_ORDER if modifier in modifiers]
    return normalize_keybinding("+".join([*ordered, key]))


def normalize_keybindings(keybindings: dict[str, str] | None) -> dict[str, str]:
    normalized = DEFAULT_KEYBINDINGS.copy()
    if not isinstance(keybindings, dict):
        return normalized
    for action in DEFAULT_KEYBINDINGS:
        value = normalize_keybinding(str(keybindings.get(action, normalized[action])))
        normalized[action] = value
    for action, value in keybindings.items():
        if is_snippet_action(action) and isinstance(value, str):
            normalized[action] = normalize_keybinding(value)
    return normalized


def keybinding_label(accelerator: str, disabled_label: str) -> str:
    normalized = normalize_keybinding(accelerator)
    return normalized or disabled_label


def keybinding_accelerator(accelerator: str) -> str:
    """Convert a stored shortcut to GTK's menu accelerator syntax."""
    normalized = normalize_keybinding(accelerator)
    if not normalized:
        return ""

    from gi.repository import Gdk, Gtk

    if normalized.endswith("+"):
        modifiers = normalized[:-1].rstrip("+").split("+")
        key = "+"
    else:
        *modifiers, key = normalized.split("+")
    if len(key) == 1:
        keyval = Gdk.keyval_to_lower(Gdk.unicode_to_keyval(ord(key)))
    else:
        keyval = Gdk.keyval_from_name({"PageUp": "Page_Up", "PageDown": "Page_Down"}.get(key, key))
    if not keyval or keyval == Gdk.KEY_VoidSymbol:
        return ""
    masks = {
        "Ctrl": Gdk.ModifierType.CONTROL_MASK,
        "Shift": Gdk.ModifierType.SHIFT_MASK,
        "Alt": Gdk.ModifierType.ALT_MASK,
        "Super": Gdk.ModifierType.SUPER_MASK,
    }
    state = Gdk.ModifierType(0)
    for modifier in modifiers:
        if modifier:
            state |= masks[modifier]
    return Gtk.accelerator_name(keyval, state)


def is_unmodified_function_key(keyval: int, state: object) -> bool:
    from gi.repository import Gdk

    relevant_mask = (
        Gdk.ModifierType.CONTROL_MASK
        | Gdk.ModifierType.SHIFT_MASK
        | Gdk.ModifierType.ALT_MASK
        | Gdk.ModifierType.SUPER_MASK
    )
    return Gdk.KEY_F1 <= keyval <= Gdk.KEY_F12 and not (state & relevant_mask)


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
