# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Modal GTK windows with explicit response actions and native focus handling."""
from __future__ import annotations

from typing import ClassVar
from weakref import ref

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GObject, Gtk


class DialogWindow(Gtk.Window):
    __gsignals__: ClassVar[dict] = {
        "response": (GObject.SignalFlags.RUN_LAST, None, (int,)),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._responses: dict[int, Gtk.Button] = {}
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(outer)
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content.set_vexpand(True)
        outer.append(self._content)
        self._actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._actions.set_halign(Gtk.Align.END)
        outer.append(self._actions)
        window_ref = ref(self)

        def key_pressed(controller, keyval, keycode, state):
            window = window_ref()
            return window._on_key_pressed(controller, keyval, keycode, state) if window else False

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", key_pressed)
        self.add_controller(keys)
        self.connect("close-request", lambda window: window._on_close_request(window))

    def get_content_area(self) -> Gtk.Box:
        return self._content

    def add_button(self, label: str, response: int) -> Gtk.Button:
        button = Gtk.Button(label=label)
        window_ref = ref(self)

        def clicked(_button):
            window = window_ref()
            if window is not None:
                window.response(response)

        button.connect("clicked", clicked)
        self._responses[int(response)] = button
        self._actions.append(button)
        return button

    def get_widget_for_response(self, response: int) -> Gtk.Button | None:
        return self._responses.get(int(response))

    def set_default_response(self, response: int) -> None:
        self.set_default_widget(self.get_widget_for_response(response))

    def set_response_sensitive(self, response: int, sensitive: bool) -> None:
        button = self.get_widget_for_response(response)
        if button is not None:
            button.set_sensitive(sensitive)

    def response(self, response: int) -> None:
        self.emit("response", int(response))

    def _on_key_pressed(self, _controller, keyval, _keycode, _state) -> bool:
        if keyval != Gdk.KEY_Escape:
            return False
        self.response(Gtk.ResponseType.CANCEL)
        return True

    def _on_close_request(self, _window) -> bool:
        self.response(Gtk.ResponseType.DELETE_EVENT)
        return False
