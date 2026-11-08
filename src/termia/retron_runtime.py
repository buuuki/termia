# SPDX-License-Identifier: GPL-3.0-or-later
"""Own one Retron customization provider and one reversible edit session."""
from __future__ import annotations

from copy import deepcopy

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .retron_profile import (
    BACKGROUND_KEYS,
    build_profile_css,
    overrides,
    resolved,
    validate_profile,
)
from .retron_store import MAX_PRESETS, preset_name
from .theme_styles import build_dark_glow_css, build_interaction_css


class RetronRuntime:
    def __init__(self, store, display, context, backgrounds_changed):
        self.store = store
        self.display = display
        self.context = context
        self.backgrounds_changed = backgrounds_changed
        self.profile = store.load(context()["accent"])
        self.opening = None
        self.provider = None
        self.enabled = False
        self.editor = None
        self.closed = False
        self._last_background = None

    def style_context(self, profile=None):
        return {**self.context(), "accent": (self.profile if profile is None else profile)["accent"]}

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.apply(self.profile)
        if self.editor is not None:
            self.editor.update_status()

    def apply(self, profile: dict) -> None:
        if self.closed:
            return
        profile = validate_profile(profile)
        candidate = None
        if self.enabled:
            context = self.style_context(profile)
            css = build_dark_glow_css(context["accent"]) + build_interaction_css(
                "dark_glow", context["terminal_background"], self.context().get("terminal_foreground", "#839496"), context["accent"],
            ) + build_profile_css(profile, **{key: value for key, value in context.items() if key != "terminal_foreground"})
            if css:
                candidate = Gtk.CssProvider()
                errors = []
                handler = candidate.connect("parsing-error", lambda _p, _s, error: errors.append(str(error)))
                candidate.load_from_string(css)
                candidate.disconnect(handler)
                if errors:
                    raise ValueError("Invalid Retron CSS")
        previous = self.provider
        if candidate is not None:
            Gtk.StyleContext.add_provider_for_display(self.display, candidate, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
        if previous is not None:
            Gtk.StyleContext.remove_provider_for_display(self.display, previous)
        self.provider = candidate
        self.profile = deepcopy(profile)
        background = self.terminal_background()
        if background != self._last_background:
            self._last_background = deepcopy(background)
            self.backgrounds_changed()

    def terminal_background(self) -> dict | None:
        if not self.enabled or not set(overrides(self.profile, "terminal", "normal")) & set(BACKGROUND_KEYS):
            return None
        values = resolved(self.profile, "terminal", "normal", **{key: value for key, value in self.style_context().items() if key != "terminal_foreground"})
        return {key: values[key] for key in ("background_color", "background_opacity")}

    def begin(self) -> dict:
        if self.opening is None:
            self.opening = deepcopy(self.profile)
        return deepcopy(self.profile)

    def cancel(self) -> None:
        if self.opening is not None:
            original = self.opening
            self.opening = None
            self.apply(original)

    def save(self, profile: dict, name: str | None = None) -> None:
        presets = deepcopy(self.store.presets)
        if name is not None:
            if name not in presets:
                raise ValueError("Unknown Retron preset")
            presets[name] = validate_profile(profile)
        self.apply(profile)
        self.store.save(self.profile, presets=presets, active_name=name)
        self.opening = None

    def save_as(self, profile: dict, name: str) -> str:
        name = self.available_name(name)
        if len(self.store.presets) >= MAX_PRESETS:
            raise ValueError("retron_preset_limit")
        presets = {**self.store.presets, name: validate_profile(profile)}
        self.apply(profile)
        self.store.save(self.profile, presets=presets, active_name=name)
        self.opening = None
        return name

    def available_name(self, name: str, original: str | None = None) -> str:
        name = preset_name(name)
        if any(existing != original and existing.casefold() == name.casefold() for existing in self.store.presets):
            raise ValueError("retron_name_duplicate")
        return name

    def rename_preset(self, original: str, name: str) -> str:
        name = self.available_name(name, original)
        if original not in self.store.presets:
            raise ValueError("Unknown Retron preset")
        presets = {name if key == original else key: value for key, value in self.store.presets.items()}
        active = name if self.store.active_name == original else self.store.active_name
        self.store.save(self.store.saved_profile, presets=presets, active_name=active)
        return name

    def delete_preset(self, name: str) -> None:
        if name not in self.store.presets:
            raise ValueError("Unknown Retron preset")
        presets = {key: value for key, value in self.store.presets.items() if key != name}
        active = None if self.store.active_name == name else self.store.active_name
        self.store.save(self.store.saved_profile, presets=presets, active_name=active)

    def show_editor(self, parent, translate):
        if self.closed or not self.enabled:
            return None
        if self.editor is None:
            from .retron_editor import RetronEditor

            self.editor = RetronEditor(self, parent, translate)
            self.editor._connect(self.editor, "destroy", self._editor_destroyed, field=False)
        self.editor.present()
        return self.editor

    def _editor_destroyed(self, _editor) -> None:
        if self.editor is _editor:
            self.cancel()
            self.editor = None

    def close(self, *_args) -> None:
        if self.closed:
            return
        if self.editor is not None:
            self.editor.destroy()
            self.editor = None
        self.opening = None
        self.enabled = False
        if self.provider is not None:
            Gtk.StyleContext.remove_provider_for_display(self.display, self.provider)
            self.provider = None
        self.backgrounds_changed()
        self.closed = True
