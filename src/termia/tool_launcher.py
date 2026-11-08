# SPDX-License-Identifier: GPL-3.0-or-later
"""Native launcher for explicitly registered, built-in tool actions."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    icon: str
    action: Callable[[], None]
    available: Callable[[], bool] = lambda: True


class ToolRegistry:
    """Internal action contributions, composed by app.py; no plugin discovery."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.id or tool.id in self._tools:
            raise ValueError("Duplicate or empty tool identifier")
        self._tools[tool.id] = tool

    def unregister(self, tool_id: str) -> None:
        self._tools.pop(tool_id, None)

    def available(self) -> tuple[Tool, ...]:
        return tuple(tool for tool in self._tools.values() if tool.available())

    def activate(self, tool_id: str) -> None:
        tool = self._tools.get(tool_id)
        if tool is not None and tool.available():
            tool.action()


class ToolLauncher(Gtk.MenuButton):
    def __init__(self, registry: ToolRegistry, translate):
        super().__init__(icon_name="view-app-grid-symbolic")
        self.registry = registry
        self.t = translate
        self._pending = None
        self._closed = False
        self._signature = None
        self.buttons: dict[str, Gtk.Button] = {}
        self.set_tooltip_text(self.t("tools"))
        self.update_property([Gtk.AccessibleProperty.LABEL], [self.t("tools")])
        self.panel = Gtk.Popover(autohide=True)
        self.panel.add_css_class("termia-menu-popover")
        self.set_popover(self.panel)
        self.grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=1, max_children_per_line=3,
                                row_spacing=8, column_spacing=8)
        self.grid.add_css_class("termia-tool-grid")
        self.grid.connect("child-activated", lambda _grid, child: child.get_child().emit("clicked"))
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                     vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                     min_content_width=140, max_content_width=360,
                                     max_content_height=360, propagate_natural_width=True,
                                     propagate_natural_height=True)
        scroller.set_child(self.grid)
        self.panel.set_child(scroller)
        self.panel.connect("show", lambda *_: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        if self._closed:
            return
        tools = self.registry.available()
        signature = tuple((tool.id, self.t(tool.name), tool.icon) for tool in tools)
        self.set_tooltip_text(self.t("tools"))
        self.update_property([Gtk.AccessibleProperty.LABEL], [self.t("tools")])
        if signature == self._signature:
            return
        self._signature = signature
        self.grid.set_max_children_per_line(min(3, max(1, len(tools))))
        while (child := self.grid.get_first_child()) is not None:
            self.grid.remove(child)
        self.buttons.clear()
        for tool in tools:
            label = self.t(tool.name)
            button = Gtk.Button(tooltip_text=label)
            button.add_css_class("termia-tool-tile")
            button.update_property([Gtk.AccessibleProperty.LABEL], [label])
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            for edge in ("top", "bottom", "start", "end"):
                getattr(box, "set_margin_" + edge)(10)
            icon = Gtk.Image.new_from_icon_name(tool.icon)
            icon.set_pixel_size(32)
            box.append(icon)
            box.append(Gtk.Label(label=label, wrap=True, justify=Gtk.Justification.CENTER,
                                 max_width_chars=16, width_chars=12))
            button.set_child(box)
            button.connect("clicked", lambda _button, key=tool.id: self._activate(key))
            self.grid.append(button)
            self.buttons[tool.id] = button
        self.set_sensitive(bool(tools))

    def _activate(self, tool_id: str) -> None:
        if self._closed or self._pending is not None:
            return
        self.popdown()

        def dispatch():
            self._pending = None
            if not self._closed:
                self.registry.activate(tool_id)
            return GLib.SOURCE_REMOVE

        # Let the native popup release its grab before presenting a window.
        self._pending = GLib.timeout_add(100, dispatch)

    def close(self) -> None:
        self._closed = True
        if self._pending is not None:
            GLib.source_remove(self._pending)
            self._pending = None
        self.popdown()
