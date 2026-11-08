# SPDX-License-Identifier: GPL-3.0-or-later
"""Native GTK controls for a single transactional Retron editing window."""
from __future__ import annotations

from copy import deepcopy

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from .choice_widgets import constrain_choice
from .dialog_actions import add_dialog_action_button, configure_dialog_content
from .dialog_window import DialogWindow
from .retron_profile import (
    BACKGROUND_KEYS,
    BORDER_KEYS,
    CHOICES,
    COLORS,
    COMPONENTS,
    NUMBERS,
    SHADOW_NUMBERS,
    STATES,
    defaults,
    empty_profile,
    new_shadow,
    resolved,
    validate_profile,
)
from .retron_store import MAX_PRESETS

ORIGINAL_PRESET = object()


class RetronEditor(DialogWindow):
    def __init__(self, runtime, parent, translate):
        super().__init__(title=translate("retron_editor"), modal=False,
                         application=parent.get_application())
        self.add_css_class("termia-retron-editor")
        self.set_default_size(820, 640)
        self.set_resizable(True)
        header = Gtk.HeaderBar(show_title_buttons=True)
        header.set_decoration_layout(":minimize,maximize,close")
        self.set_titlebar(header)
        self.runtime = runtime
        self._connections = []
        self._field_connections = []
        self._retired = False
        self.t = translate
        self.draft = runtime.begin()
        self.selection = runtime.store.active_name
        self._selection_baseline = deepcopy(self.draft)
        self._selection_loading = False
        self._prompt_cancel = None
        self._prompt_dialog = None
        self._name_dialog = None
        self._name_connections = []
        self._source = None
        self._loading = False
        self.component = "common"
        self.state = "normal"
        self.controls = {}
        self.inherit_controls = {}
        content = configure_dialog_content(self.get_content_area(), spacing=8)
        self.status = Gtk.Label(xalign=0, wrap=True)
        content.append(self.status)
        presets = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        content.append(presets)
        label = Gtk.Label(label=self.t("retron_presets"), xalign=0)
        presets.append(label)
        self.preset_choice = Gtk.DropDown(hexpand=True)
        constrain_choice(self.preset_choice, 14, 22)
        label.set_mnemonic_widget(self.preset_choice)
        self.preset_choice.update_property([Gtk.AccessibleProperty.LABEL], [self.t("retron_presets")])
        self._connect(self.preset_choice, "notify::selected", self._preset_changed, field=False)
        presets.append(self.preset_choice)
        self.save_as_button = Gtk.Button(label=self.t("retron_save_as"))
        self.rename_button = Gtk.Button(label=self.t("retron_rename"))
        self.delete_button = Gtk.Button(label=self.t("retron_delete"))
        for button, callback in ((self.save_as_button, self._save_as_clicked),
                                 (self.rename_button, self._rename_clicked), (self.delete_button, self._delete_clicked)):
            self._connect(button, "clicked", callback, field=False)
            presets.append(button)
        self._refresh_presets()
        self.preview = Gtk.CheckButton(label=self.t("retron_live_preview"), active=True)
        self._connect(self.preview, "toggled", self._preview_toggled, field=False)
        content.append(self.preview)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16, vexpand=True)
        content.append(body)
        self.component_ids = ("common", *COMPONENTS)
        self.component_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        for key in self.component_ids:
            label = Gtk.Label(label=self.t("retron_component_" + key), xalign=0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(8)
            label.set_margin_end(8)
            self.component_list.append(label)
        nav = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, min_content_width=170)
        nav.set_child(self.component_list)
        body.append(nav)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        body.append(right)
        self.state_choice = Gtk.DropDown()
        self._connect(self.state_choice, "notify::selected", self._state_changed, field=False)
        right.append(self.state_choice)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroller.set_overlay_scrolling(True)
        self.fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.fields.set_margin_end(40)
        scroller.set_child(self.fields)
        right.append(scroller)
        self.error = Gtk.Label(xalign=0, wrap=True)
        self.error.add_css_class("error")
        content.append(self.error)
        self.restore_button = add_dialog_action_button(self, self.t("retron_restore"), Gtk.ResponseType.REJECT)
        add_dialog_action_button(self, self.t("cancel"), Gtk.ResponseType.CANCEL)
        self.apply_button = add_dialog_action_button(self, self.t("retron_apply"), Gtk.ResponseType.APPLY)
        self.save_button = add_dialog_action_button(self, self.t("save"), Gtk.ResponseType.OK)
        self.save_button.add_css_class("suggested-action")
        self._connect(self, "response", self._response, field=False)
        self._connect(self.component_list, "row-selected", self._component_changed, field=False)
        self.component_list.select_row(self.component_list.get_row_at_index(0))
        self.update_status()

    def _refresh_presets(self):
        self._selection_loading = True
        try:
            ids = [None, ORIGINAL_PRESET, *self.runtime.store.presets]
            if ids != getattr(self, "preset_ids", None):
                self.preset_ids = ids
                labels = [self.t("retron_current"), self.t("retron_original"), *self.runtime.store.presets]
                self.preset_choice.set_model(Gtk.StringList.new(labels))
            self.preset_choice.set_selected(self.preset_ids.index(self.selection))
        finally:
            self._selection_loading = False

    def _preset_changed(self, choice, _spec):
        if self._selection_loading or self._retired:
            return
        index = choice.get_selected()
        if index >= len(self.preset_ids):
            return
        target = self.preset_ids[index]
        if target == self.selection:
            return
        # Keep the old selection until the unsaved-edit decision completes.
        self._refresh_presets()
        if validate_profile(self.draft) == self._selection_baseline:
            self._load_selection(target)
        else:
            self._ask(self.t("retron_switch_unsaved"),
                      [self.t("cancel"), self.t("retron_discard"), self.t("save")],
                      lambda response: self._finish_switch(target, response))

    def _finish_switch(self, target, response):
        if response == 1 or (response == 2 and self._save_current()):
            self._load_selection(target)

    def _load_selection(self, target):
        self._stop_source()
        if target is ORIGINAL_PRESET:
            profile = empty_profile()
        elif target is None:
            profile = self.runtime.store.saved_profile
        else:
            profile = self.runtime.store.presets[target]
        self.selection = target
        self.draft = deepcopy(profile)
        self._selection_baseline = deepcopy(self.draft)
        self._refresh_presets()
        self._rebuild()
        self._changed()

    def _ask(self, message, buttons, finished):
        if self._prompt_cancel is not None or self._retired:
            return
        dialog = Gtk.AlertDialog(message=message, buttons=buttons, cancel_button=0, default_button=0)
        cancellable = Gio.Cancellable()
        self._prompt_cancel = cancellable
        self._prompt_dialog = dialog

        def answered(alert, result):
            self._prompt_cancel = None
            self._prompt_dialog = None
            try:
                response = alert.choose_finish(result)
            except GLib.Error:
                return
            if not self._retired:
                finished(response)

        dialog.choose(self, cancellable, answered)

    def _save_current(self):
        self._stop_source()
        name = self.selection if isinstance(self.selection, str) else None
        try:
            self.runtime.save(self.draft, name)
        except (OSError, ValueError, GLib.Error):
            self.error.set_text(self.t("retron_save_error"))
            return False
        self.draft = self.runtime.begin()
        self._selection_baseline = deepcopy(self.draft)
        # The immutable original remains available after editing a copy.
        if self.selection is ORIGINAL_PRESET and self.draft != empty_profile():
            self.selection = None
        self._refresh_presets()
        self.error.set_text("")
        self.update_status()
        return True

    def _save_as_clicked(self, _button):
        self._name_prompt(False)

    def _rename_clicked(self, _button):
        if isinstance(self.selection, str):
            self._name_prompt(True)

    def _name_prompt(self, rename):
        if self._name_dialog is not None or self._retired:
            return
        dialog = DialogWindow(title=self.t("retron_rename" if rename else "retron_save_as"),
                              transient_for=self, modal=True)
        self._name_dialog = dialog
        content = configure_dialog_content(dialog.get_content_area(), spacing=8)
        label = Gtk.Label(label=self.t("retron_name"), xalign=0)
        entry = Gtk.Entry(max_length=64, activates_default=True)
        label.set_mnemonic_widget(entry)
        entry.update_property([Gtk.AccessibleProperty.LABEL], [self.t("retron_name")])
        if rename:
            entry.set_text(self.selection)
        error = Gtk.Label(xalign=0, wrap=True)
        error.add_css_class("error")
        for widget in (label, entry, error):
            content.append(widget)
        add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL)
        add_dialog_action_button(dialog, self.t("save"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        def answered(_dialog, response):
            if response != Gtk.ResponseType.OK:
                self._close_name_dialog()
                return
            try:
                self._store_name(entry.get_text(), rename)
            except ValueError as exc:
                key = str(exc)
                error.set_text(self.t(key if key in ("retron_name_invalid", "retron_name_duplicate", "retron_preset_limit")
                                      else "retron_save_error"))
                return
            except (OSError, GLib.Error):
                error.set_text(self.t("retron_save_error"))
                return
            self._close_name_dialog()

        self._name_connections.append((dialog, dialog.connect("response", answered)))
        dialog.present()
        entry.grab_focus()

    def _store_name(self, name, rename=False):
        if rename:
            self.selection = self.runtime.rename_preset(self.selection, name)
        else:
            self._stop_source()
            self.selection = self.runtime.save_as(self.draft, name)
            self.draft = self.runtime.begin()
            self._selection_baseline = deepcopy(self.draft)
        self._refresh_presets()
        self.error.set_text("")
        self.update_status()

    def _close_name_dialog(self):
        self._disconnect(self._name_connections)
        dialog, self._name_dialog = self._name_dialog, None
        if dialog is not None:
            dialog.set_transient_for(None)
            dialog.destroy()

    def _delete_clicked(self, _button):
        if not isinstance(self.selection, str):
            return
        name = self.selection
        self._ask(self.t("retron_delete_confirm").format(name=name),
                  [self.t("cancel"), self.t("retron_delete")],
                  lambda response: self._delete_confirmed(name) if response == 1 else None)

    def _delete_confirmed(self, name):
        try:
            self.runtime.delete_preset(name)
        except (OSError, ValueError):
            self.error.set_text(self.t("retron_save_error"))
            return
        self.selection = None
        self._refresh_presets()
        self.update_status()

    def _connect(self, widget, signal, callback, *, field=True):
        connections = self._field_connections if field else self._connections
        connections.append((widget, widget.connect(signal, callback)))

    @staticmethod
    def _disconnect(connections):
        for widget, handler in connections:
            widget.disconnect(handler)
        connections.clear()

    def _patch(self) -> dict:
        states = self.draft["common"] if self.component == "common" else self.draft["components"].setdefault(self.component, {})
        return states.setdefault(self.state, {})

    def _values(self) -> dict:
        context = {key: value for key, value in self.runtime.style_context(self.draft).items() if key != "terminal_foreground"}
        if self.component == "common":
            return {**defaults("common", self.state, **context), **self.draft["common"].get("normal", {}), **self._patch()}
        return resolved(self.draft, self.component, self.state, **context)

    def _component_changed(self, _list, row):
        if row is None:
            return
        self.component = self.component_ids[row.get_index()]
        self.state_ids = STATES if self.component == "common" else COMPONENTS[self.component].states
        self._loading = True
        self.state_choice.set_model(Gtk.StringList.new([self.t("retron_state_" + value) for value in self.state_ids]))
        self.state_choice.set_selected(0)
        self.state = self.state_ids[0]
        self._loading = False
        self._rebuild()

    def _state_changed(self, choice, _spec):
        if self._loading:
            return
        index = choice.get_selected()
        if index < len(self.state_ids):
            self.state = self.state_ids[index]
            self._rebuild()

    def _rebuild(self):
        self._loading = True
        self._disconnect(self._field_connections)
        child = self.fields.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.fields.remove(child)
            child = following
        self.controls = {}
        self.inherit_controls = {}
        values = self._values()
        patch = self._patch()
        for title, keys in (("retron_borders", BORDER_KEYS), ("retron_backgrounds", BACKGROUND_KEYS)):
            heading = Gtk.Label(label=self.t(title), xalign=0)
            heading.add_css_class("heading")
            self.fields.append(heading)
            for key in keys:
                if self.component == "terminal" and (self.state != "normal" or key in ("background_mode", "gradient_color", "gradient_angle")) and key in BACKGROUND_KEYS:
                    continue
                widget = self._property_widget(key, values[key], lambda value, name=key: self._set(name, value))
                self._property_row(key, widget, key in patch)
        heading = Gtk.Label(label=self.t("retron_glows"), xalign=0)
        heading.add_css_class("heading")
        self.fields.append(heading)
        shadows_enabled = Gtk.CheckButton(label=self.t("retron_customize"), active="shadows" in patch)
        self._connect(shadows_enabled, "toggled", lambda widget: self._inherit("shadows", widget.get_active()))
        self.inherit_controls["shadows"] = shadows_enabled
        self.fields.append(shadows_enabled)
        self.shadow_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.fields.append(self.shadow_box)
        self.glow_active = Gtk.CheckButton(label=self.t("retron_glow_enabled"))
        self._connect(self.glow_active, "toggled", self._toggle_glow)
        self.shadow_box.append(self.glow_active)
        self.shadow_fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.shadow_box.append(self.shadow_fields)
        self._refresh_shadows()
        self._loading = False

    def _refresh_shadows(self):
        loading = self._loading
        self._loading = True
        try:
            self.shadow_box.set_sensitive("shadows" in self._patch())
            self.glow_active.set_active(bool(self._values()["shadows"]))
            # Only the variable glow rows are replaced. Keep their checkboxes
            # and the rest of the form alive, including the focused control.
            retired = [connection for connection in self._field_connections
                       if connection[0].is_ancestor(self.shadow_fields)]
            self._field_connections = [connection for connection in self._field_connections
                                       if connection not in retired]
            self._disconnect(retired)
            while (child := self.shadow_fields.get_first_child()) is not None:
                self.shadow_fields.remove(child)
            self._build_shadow_fields(self._values()["shadows"])
        finally:
            self._loading = loading

    def _build_shadow_fields(self, shadows):
        for index, shadow in enumerate(shadows):
            frame = Gtk.Frame(label=self.t("retron_glow_number").format(number=index + 1))
            grid = Gtk.Grid(column_spacing=8, row_spacing=6)
            frame.set_child(grid)
            self.shadow_fields.append(frame)
            for row, key in enumerate(("color", *SHADOW_NUMBERS, "inset")):
                label = Gtk.Label(label=self.t("retron_shadow_" + key), xalign=0)
                grid.attach(label, 0, row, 1, 1)
                callback = lambda value, i=index, name=key: self._shadow_set(i, name, value)
                if key == "color":
                    widget = self._color_widget(shadow[key], callback)
                elif key == "inset":
                    widget = Gtk.Switch(active=shadow[key], halign=Gtk.Align.START)
                    self._connect(widget, "notify::active", lambda control, _spec, cb=callback: cb(control.get_active()))
                else:
                    widget = self._number_widget(shadow[key], SHADOW_NUMBERS[key], callback, percentage=key == "opacity")
                grid.attach(widget, 1, row, 1, 1)
            remove = Gtk.Button(label=self.t("retron_remove_glow"))
            self._connect(remove, "clicked", lambda _button, i=index: self._remove_shadow(i))
            grid.attach(remove, 0, 7, 2, 1)
        add = Gtk.Button(label=self.t("retron_add_glow"), sensitive=len(shadows) < 3)
        self._connect(add, "clicked", self._add_shadow)
        self.shadow_fields.append(add)

    def _property_row(self, key, widget, customized):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=self.t("retron_" + key), xalign=0, hexpand=True, wrap=True)
        row.append(label)
        row.append(widget)
        widget.set_sensitive(customized)
        label.set_mnemonic_widget(widget)
        override = Gtk.CheckButton(active=customized)
        override.set_tooltip_text(self.t("retron_customize"))
        override.update_property([Gtk.AccessibleProperty.LABEL], [self.t("retron_customize") + ": " + self.t("retron_" + key)])
        self._connect(override, "toggled", lambda control: self._inherit(key, control.get_active()))
        row.append(override)
        self.controls[key] = widget
        self.inherit_controls[key] = override
        self.fields.append(row)

    def _property_widget(self, key, value, callback):
        if key in COLORS:
            return self._color_widget(value, callback)
        if key in NUMBERS:
            return self._number_widget(value, NUMBERS[key], callback, percentage=key.endswith("opacity"))
        choices = CHOICES[key]
        widget = Gtk.DropDown.new_from_strings([self.t("retron_value_" + item) for item in choices])
        widget.set_selected(choices.index(value))
        self._connect(widget, "notify::selected", lambda control, _spec: callback(choices[control.get_selected()]))
        return widget

    def _color_widget(self, value, callback):
        dialog = Gtk.ColorDialog(with_alpha=False)
        widget = Gtk.ColorDialogButton(dialog=dialog)
        rgba = Gdk.RGBA()
        rgba.parse(value)
        widget.set_rgba(rgba)

        def changed(control, _spec):
            selected = control.get_rgba()
            callback("#{:02X}{:02X}{:02X}".format(*(round(getattr(selected, channel) * 255) for channel in ("red", "green", "blue"))))

        self._connect(widget, "notify::rgba", changed)
        return widget

    def _number_widget(self, value, limits, callback, *, percentage=False):
        scale = 100 if percentage else 1
        widget = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, limits[0] * scale, limits[1] * scale, limits[2] * scale,
        )
        widget.set_digits(0)
        widget.set_draw_value(True)
        widget.set_value_pos(Gtk.PositionType.RIGHT)
        widget.set_size_request(170, -1)
        widget.set_value(value * scale)
        self._connect(widget, "value-changed", lambda control: callback(control.get_value() / scale))
        return widget

    def _inherit(self, key, customized):
        if self._loading:
            return
        value = deepcopy(self._values()[key])
        if customized:
            self._patch()[key] = value
        else:
            self._patch().pop(key, None)
        self._loading = True
        try:
            self.inherit_controls[key].set_active(customized)
            if key == "shadows":
                self._refresh_shadows()
            else:
                widget = self.controls[key]
                value = self._values()[key]
                if key in COLORS:
                    rgba = Gdk.RGBA()
                    rgba.parse(value)
                    widget.set_rgba(rgba)
                elif key in NUMBERS:
                    widget.set_value(value * (100 if key.endswith("opacity") else 1))
                else:
                    widget.set_selected(CHOICES[key].index(value))
                widget.set_sensitive(customized)
        finally:
            self._loading = False
        self._changed()

    def _set(self, key, value):
        if not self._loading:
            self._patch()[key] = value
            self._changed()

    def _shadow_set(self, index, key, value):
        if not self._loading:
            self._patch()["shadows"][index][key] = value
            self._changed()

    def _add_shadow(self, _button):
        self._patch()["shadows"].append(new_shadow())
        self._refresh_shadows()
        self._changed()

    def _remove_shadow(self, index):
        del self._patch()["shadows"][index]
        self._refresh_shadows()
        self._changed()

    def _toggle_glow(self, button):
        if not self._loading:
            self._patch()["shadows"] = [new_shadow()] if button.get_active() else []
            self._refresh_shadows()
            self._changed()

    def _preview_toggled(self, _button):
        self._stop_source()
        if self.preview.get_active():
            self._changed()

    def _changed(self):
        self.update_status()
        if self.preview.get_active() and self._source is None:
            self._source = GLib.timeout_add(50, self._preview_now)

    def _preview_now(self):
        self._source = None
        self._apply()
        return GLib.SOURCE_REMOVE

    def _apply(self):
        try:
            self.runtime.apply(self.draft)
        except (ValueError, GLib.Error):
            self.error.set_text(self.t("retron_invalid_preview"))
            return False
        self.error.set_text("")
        return True

    def _stop_source(self):
        if self._source is not None:
            GLib.source_remove(self._source)
            self._source = None

    def update_status(self):
        writable = self.runtime.store.can_write() and not self.runtime.store.load_error
        self.save_button.set_sensitive(writable)
        self.save_as_button.set_sensitive(writable and len(self.runtime.store.presets) < MAX_PRESETS)
        self.rename_button.set_sensitive(writable and isinstance(self.selection, str))
        self.delete_button.set_sensitive(writable and isinstance(self.selection, str))
        message = "retron_editing" if self.runtime.enabled else "retron_suspended"
        if self.runtime.store.load_error:
            message = "retron_load_error"
        elif not writable:
            message = "retron_read_only"
        selected_name = self.selection if isinstance(self.selection, str) else None
        pending = validate_profile(self.draft) != self.runtime.opening or selected_name != self.runtime.store.active_name
        self.status.set_text(self.t(message) + (" " + self.t("retron_unsaved") if pending else ""))

    def _response(self, _dialog, response):
        self._stop_source()
        if response == Gtk.ResponseType.REJECT:
            self.draft = empty_profile()
            self._rebuild()
            self._changed()
        elif response == Gtk.ResponseType.APPLY:
            self._apply()
        elif response == Gtk.ResponseType.OK:
            if self._save_current():
                self.destroy()
        else:
            self.runtime.cancel()
            self.destroy()

    def destroy(self):
        # Gtk.Widget::destroy can be delayed by Python references. Retire the
        # transaction/source before native destruction, not on finalization.
        if self._retired:
            return
        self._retired = True
        self._stop_source()
        if self._prompt_cancel is not None:
            self._prompt_cancel.cancel()
        self._close_name_dialog()
        self._disconnect(self._field_connections)
        self._disconnect(self._connections)
        self.runtime._editor_destroyed(self)
        super().destroy()
