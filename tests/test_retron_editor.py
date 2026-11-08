# SPDX-License-Identifier: GPL-3.0-or-later
import gc
import tempfile
import time
import unittest
import weakref
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gi.repository import GLib

from termia.app import Gdk, Gtk, TermiaApp, TermiaWindow, WindowThemeScope
from termia.i18n import translate_key
from termia.retron_editor import ORIGINAL_PRESET
from termia.retron_profile import (
    COMPONENTS,
    build_profile_css,
    empty_profile,
    new_shadow,
    validate_profile,
)
from termia.retron_runtime import RetronRuntime
from termia.retron_store import RetronStore
from termia.stores import ConnectionStore
from termia.styles import build_application_css
from termia.terminal_sessions import TerminalSessionsMixin


class RetronHeaderTests(unittest.TestCase):
    def test_header_entry_tracks_theme_language_lock_and_reuses_editor(self):
        app = TermiaApp()
        app.set_application_id("local.termia.RetronHeaderTest")
        self.assertTrue(app.register(None))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConnectionStore(root / "connections.json", root / "settings.json",
                                    root / "statistics.json", root / "lock", root / "history")
            store.data.app.open_local_terminal_on_startup = False
            store.data.app.restore_sessions_on_startup = False
            store.data.app.theme = "dark_glow"
            with patch("termia.app.ConnectionStore", return_value=store), \
                    patch("termia.app.RETRON_PROFILE_FILE", root / "retron.json"), \
                    patch("termia.app.SESSION_SNAPSHOT_FILE", root / "session.json"):
                window = TermiaWindow(app)
            try:
                button = window.tool_launcher
                self.assertTrue(button.get_visible())
                self.assertIs(button.get_ancestor(Gtk.HeaderBar), window.header)
                window.tool_registry.activate("appearance")
                editor = window.retron_runtime.editor
                self.assertIsNotNone(editor)
                window.on_retron_editor()
                window.tool_registry.activate("appearance")
                self.assertIs(window.retron_runtime.editor, editor)
                for language in ("en", "es", "ca"):
                    store.data.app.language = language
                    window.refresh_translated_chrome()
                    self.assertEqual(button.get_tooltip_text(), translate_key("tools", language))
                for theme in ("light", "dark", "system", "dark_glow"):
                    store.data.app.theme = theme
                    window.apply_app_theme()
                    self.assertEqual("appearance" in button.buttons, theme == "dark_glow")
                    self.assertEqual(window.retron_runtime.provider is not None, theme == "dark_glow")
                window.set_unlock_header_actions_sensitive(False)
                self.assertFalse(button.get_sensitive())
                window.set_unlock_header_actions_sensitive(True)
                self.assertTrue(button.get_sensitive())
                editor.response(Gtk.ResponseType.CANCEL)
                self.assertIsNone(window.retron_runtime.editor)
                self.assertFalse((root / "retron.json").exists())
            finally:
                window.shutdown_in_progress = True
                window.prepare_terminal_sessions_for_shutdown()
                window.snippet_dialogs.shutdown()
                window.notes_dialogs.shutdown()
                window.retron_runtime.close()
                window.destroy()
                store.close()
                app._window_theme_scope.close()
                app.quit()


class RetronEditorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "retron.json"
        self.parent = Gtk.Window()
        self.scope = WindowThemeScope()
        self.scope.set_enabled(True)
        self.writable = True
        self.context = {"accent": "#55BAC9", "terminal_background": "#182231", "notes_background": "#001B33"}
        self.changed = Mock()
        self.runtime = RetronRuntime(RetronStore(self.path, lambda: self.writable),
                                     Gdk.Display.get_default(), lambda: self.context, self.changed)
        self.runtime.set_enabled(True)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.runtime.close()
        self.scope.close()
        self.parent.destroy()
        self.directory.cleanup()

    def editor(self):
        return self.runtime.show_editor(self.parent, lambda key: translate_key(key, "en"))

    def test_text_fields_edit_save_reload_cancel_and_theme_switch(self):
        entry = Gtk.Entry()
        self.parent.set_child(entry)
        self.parent.present()
        self.settle()
        original_border = entry.get_style_context().get_border().top
        editor = self.editor()
        row = editor.component_list.get_row_at_index(editor.component_ids.index("fields"))
        editor.component_list.select_row(row)
        self.assertEqual(editor.state_ids, ("normal", "focus", "disabled"))
        editor._set("border_width", 4)
        editor.state_choice.set_selected(editor.state_ids.index("focus"))
        editor._set("border_color", "#ABCDEF")
        editor._set("shadows", [new_shadow()])
        editor.response(Gtk.ResponseType.OK)
        self.settle()
        self.assertEqual(entry.get_style_context().get_border().top, 4)
        saved = RetronStore(self.path, lambda: True).load()
        self.assertEqual(saved["components"]["fields"]["focus"]["border_color"], "#ABCDEF")
        self.assertEqual(saved["components"]["fields"]["normal"]["border_width"], 4)
        for language, label in (("en", "Text fields"), ("es", "Campos de texto"), ("ca", "Camps de text")):
            self.assertEqual(translate_key("retron_component_fields", language), label)
        self.runtime.set_enabled(False)
        self.settle()
        self.assertEqual(entry.get_style_context().get_border().top, original_border)
        self.runtime.set_enabled(True)
        self.settle()
        self.assertEqual(entry.get_style_context().get_border().top, 4)
        editor = self.editor()
        editor.component_list.select_row(editor.component_list.get_row_at_index(editor.component_ids.index("fields")))
        editor._set("border_width", 6)
        editor.response(Gtk.ResponseType.APPLY)
        self.settle()
        self.assertEqual(entry.get_style_context().get_border().top, 6)
        editor.response(Gtk.ResponseType.CANCEL)
        self.settle()
        self.assertEqual(self.runtime.profile, saved)
        self.assertEqual(entry.get_style_context().get_border().top, 4)

    def test_singleton_close_cancel_and_pending_source_cleanup(self):
        editor = self.editor()
        self.assertIs(editor, self.editor())
        opening = deepcopy(self.runtime.profile)
        editor._set("border_width", 3)
        self.assertIsNotNone(editor._source)
        editor.response(Gtk.ResponseType.APPLY)
        self.assertEqual(self.runtime.profile["common"]["normal"]["border_width"], 3)
        editor.response(Gtk.ResponseType.CANCEL)
        self.assertIsNone(editor._source)
        self.assertEqual(self.runtime.profile, opening)
        self.assertIsNone(self.runtime.editor)
        self.assertFalse(self.path.exists())
        reference = weakref.ref(editor)
        del editor
        gc.collect()
        self.assertIsNone(reference())
        next_editor = self.editor()
        next_editor._set("radius", 20)
        next_editor._apply()
        next_editor.close()
        self.assertEqual(self.runtime.profile, opening)
        self.assertIsNone(self.runtime.editor)

    def test_editor_exposes_native_window_controls(self):
        editor = self.editor()
        header = editor.get_titlebar()
        self.assertIsInstance(header, Gtk.HeaderBar)
        buttons = set()

        def visit(widget):
            if isinstance(widget, Gtk.Button):
                buttons.update(set(widget.get_css_classes()) & {"minimize", "maximize", "close"})
            child = widget.get_first_child()
            while child is not None:
                visit(child)
                child = child.get_next_sibling()

        visit(header)
        self.assertEqual(buttons, {"minimize", "maximize", "close"})
        editor.close()
        self.assertIsNone(self.runtime.editor)
        self.assertIsNone(self.runtime.opening)

    @staticmethod
    def settle(seconds=0.12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.002)

    def test_override_checkboxes_keep_focus_controls_and_scroll(self):
        editor = self.editor()
        self.settle()
        controls = dict(editor.controls)
        checkboxes = dict(editor.inherit_controls)
        adjustment = editor.fields.get_ancestor(Gtk.ScrolledWindow).get_vadjustment()
        for key in ("border_color", "border_width", "border_opacity", "border_style",
                    "background_color", "gradient_color", "gradient_angle"):
            checkbox = checkboxes[key]
            checkbox.grab_focus()
            # Let GTK finish scrolling the focused row into view first.
            self.settle(0.35)
            scroll = adjustment.get_value()
            for active in (True, False):
                with self.subTest(key=key, active=active):
                    checkbox.set_active(active)
                    self.settle()
                    self.assertIs(editor.get_focus(), checkbox)
                    self.assertEqual(editor.controls, controls)
                    self.assertEqual(editor.inherit_controls, checkboxes)
                    self.assertEqual(controls[key].get_sensitive(), active)
                    self.assertEqual(key in editor._patch(), active)
                    self.assertAlmostEqual(adjustment.get_value(), scroll, delta=1)

    def test_disabling_overrides_refreshes_inherited_values_without_writing_them(self):
        editor = self.editor()
        cases = (("border_color", "#123456"), ("border_width", 7),
                 ("border_opacity", 0.73), ("border_style", "dashed"))
        for key, value in cases:
            editor.inherit_controls[key].set_active(True)
            editor._set(key, value)
        editor.component_list.select_row(editor.component_list.get_row_at_index(editor.component_ids.index("panels")))
        for key, _value in cases:
            editor.inherit_controls[key].set_active(True)
        color = Gdk.RGBA()
        color.parse("#ABCDEF")
        editor.controls["border_color"].set_rgba(color)
        editor.controls["border_width"].set_value(2)
        editor.controls["border_opacity"].set_value(25)
        editor.controls["border_style"].set_selected(0)
        for key, _value in cases:
            editor.inherit_controls[key].set_active(False)
            self.assertNotIn(key, editor._patch())
        expected = Gdk.RGBA()
        expected.parse("#123456")
        self.assertTrue(editor.controls["border_color"].get_rgba().equal(expected))
        self.assertEqual(editor.controls["border_width"].get_value(), 7)
        self.assertEqual(editor.controls["border_opacity"].get_value(), 73)
        self.assertEqual(editor.controls["border_style"].get_selected_item().get_string(), "Dashed")

    def test_glow_checkboxes_keep_focus_and_release_replaced_rows(self):
        editor = self.editor()
        customize = editor.inherit_controls["shadows"]
        enabled = editor.glow_active
        self.settle()
        customize.grab_focus()
        customize.set_active(True)
        self.settle()
        self.assertIs(editor.get_focus(), customize)
        baseline_connections = len(editor._field_connections)
        for _ in range(3):
            enabled.grab_focus()
            enabled.set_active(True)
            self.settle()
            self.assertIs(editor.get_focus(), enabled)
            frame = weakref.ref(editor.shadow_fields.get_first_child())
            enabled.set_active(False)
            self.settle()
            gc.collect()
            self.assertIsNone(frame())
            self.assertEqual(len(editor._field_connections), baseline_connections)
            self.assertIs(editor.get_focus(), enabled)
        customize.grab_focus()
        customize.set_active(False)
        self.settle()
        self.assertIs(editor.get_focus(), customize)
        self.assertIs(editor.glow_active, enabled)
        self.assertFalse(editor.shadow_box.get_sensitive())
        self.assertNotIn("shadows", editor._patch())

    def test_save_reload_defaults_and_failed_save(self):
        editor = self.editor()
        editor._set("radius", 22)
        editor.response(Gtk.ResponseType.OK)
        self.assertIsNone(self.runtime.editor)
        saved = RetronStore(self.path, lambda: True).load()
        self.assertEqual(saved["common"]["normal"]["radius"], 22)
        editor = self.editor()
        editor.response(Gtk.ResponseType.REJECT)
        editor.response(Gtk.ResponseType.APPLY)
        self.assertEqual(self.runtime.profile, empty_profile())
        editor.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(self.runtime.profile, saved)
        editor = self.editor()
        editor._set("radius", 30)
        with patch.object(self.runtime.store, "save", side_effect=OSError("synthetic failure")):
            editor.response(Gtk.ResponseType.OK)
        self.assertIs(self.runtime.editor, editor)
        self.assertTrue(editor.error.get_text())
        editor.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(self.runtime.profile, saved)

    def test_replacements_remove_previous_provider_and_other_themes_suspend(self):
        with patch.object(Gtk.StyleContext, "add_provider_for_display", wraps=Gtk.StyleContext.add_provider_for_display) as add, \
             patch.object(Gtk.StyleContext, "remove_provider_for_display", wraps=Gtk.StyleContext.remove_provider_for_display) as remove:
            for width in (2, 3, 4):
                profile = empty_profile()
                profile["common"] = {"normal": {"border_width": width}}
                previous = self.runtime.provider
                self.runtime.apply(profile)
                self.assertIs(remove.call_args.args[1], previous)
                self.assertIsNot(self.runtime.provider, previous)
            self.assertEqual((add.call_count, remove.call_count), (3, 3))
            editor = self.editor()
            self.runtime.set_enabled(False)
            self.scope.set_enabled(False)
            self.assertIsNone(self.runtime.provider)
            self.assertFalse(self.parent.has_css_class("termia-dark-glow"))
            self.assertIsNone(self.runtime.show_editor(self.parent, lambda key: key))
            editor._set("radius", 24)
            editor.response(Gtk.ResponseType.APPLY)
            self.assertIsNone(self.runtime.provider)
            editor.response(Gtk.ResponseType.CANCEL)
            self.assertIsNone(self.runtime.provider)
            self.runtime.set_enabled(True)
            self.assertIsNotNone(self.runtime.provider)
        for theme in ("system", "light", "dark"):
            self.assertEqual(build_application_css("#000000", "#008712", 1, theme),
                             build_application_css("#000000", "#008712", 1, theme, include_retron=False))

    def test_all_components_states_and_maximum_effects_parse(self):
        profile = empty_profile()
        for component, spec in COMPONENTS.items():
            profile["components"][component] = {
                state: {"border_style": "dashed", "border_width": 3, "radius": 24, "shadows": [new_shadow()] * 3}
                for state in spec.states
            }
            if component != "terminal":
                profile["components"][component]["normal"].update(background_mode="radial", background_opacity=0.3)
        provider = Gtk.CssProvider()
        errors = []
        provider.connect("parsing-error", lambda _p, _s, error: errors.append(str(error)))
        provider.load_from_data(build_profile_css(profile).encode())
        self.assertEqual(errors, [])
        self.runtime.apply(profile)

    def test_terminal_background_restores_without_reapplying_fonts_or_palette(self):
        terminal = Mock()
        host = SimpleNamespace(retron_runtime=self.runtime, store=SimpleNamespace(data=SimpleNamespace(
            terminal=SimpleNamespace(background="#182231"))))
        self.runtime.begin()
        profile = empty_profile()
        profile["components"] = {"terminal": {"normal": {"background_color": "#123456", "background_opacity": 0.4}}}
        self.runtime.apply(profile)
        TerminalSessionsMixin.apply_retron_terminal_background(host, terminal)
        color = terminal.set_color_background.call_args.args[0]
        self.assertAlmostEqual(color.alpha, 0.4)
        terminal.set_colors.assert_not_called()
        terminal.set_font.assert_not_called()
        self.runtime.cancel()
        TerminalSessionsMixin.apply_retron_terminal_background(host, terminal)
        self.assertAlmostEqual(terminal.set_color_background.call_args.args[0].alpha, 1)
        calls = self.changed.call_count
        profile = empty_profile()
        profile["common"] = {"normal": {"radius": 12}}
        self.runtime.apply(profile)
        self.assertEqual(self.changed.call_count, calls)

    def test_read_only_preview_never_writes_and_shutdown_releases_provider(self):
        self.writable = False
        editor = self.editor()
        self.assertFalse(editor.save_button.get_sensitive())
        editor._set("radius", 20)
        editor._apply()
        self.runtime.close()
        self.assertIsNone(editor._source)
        self.assertIsNone(self.runtime.provider)
        self.assertIsNone(self.runtime.editor)
        self.assertFalse(self.path.exists())

    def test_native_alerts_editor_and_future_windows_have_isolated_borders(self):
        def settle():
            until = time.monotonic() + 0.06
            while time.monotonic() < until:
                for _ in range(100):
                    if not GLib.MainContext.default().pending():
                        break
                    GLib.MainContext.default().iteration(False)
                time.sleep(0.005)

        self.parent.add_css_class("termia-main-window")
        self.parent.present()
        alert = Gtk.Window()
        alert.add_css_class("message")
        alert.add_css_class("dialog")
        alert.present()
        self.addCleanup(alert.destroy)
        editor = self.editor()
        settle()
        original_alert = alert.get_style_context().get_border().top
        original_editor = editor.get_style_context().get_border().top
        editor._set("border_width", 5)
        editor._apply()
        future = Gtk.Window()
        future.present()
        self.addCleanup(future.destroy)
        settle()
        self.assertEqual(self.parent.get_style_context().get_border().top, 5)
        self.assertEqual(future.get_style_context().get_border().top, 5)
        self.assertEqual(alert.get_style_context().get_border().top, original_alert)
        self.assertEqual(editor.get_style_context().get_border().top, original_editor)
        editor.response(Gtk.ResponseType.CANCEL)
        settle()
        self.assertEqual(self.parent.get_style_context().get_border().top, 1)

    def test_repeated_rebuilds_and_reopens_release_widgets_and_callbacks(self):
        for _ in range(4):
            editor = self.editor()
            for index in range(len(editor.component_ids)):
                editor.component_list.select_row(editor.component_list.get_row_at_index(index))
                for state in range(len(editor.state_ids)):
                    editor.state_choice.set_selected(state)
            editor._set("border_width", 2)
            editor.destroy()
            self.assertEqual(editor._connections, [])
            self.assertEqual(editor._field_connections, [])
            reference = weakref.ref(editor)
            del editor
            gc.collect()
            self.assertIsNone(reference())
        self.assertIsNone(self.runtime.opening)
        self.assertIsNone(self.runtime.editor)

    def test_named_presets_save_switch_overwrite_rename_delete_and_reload(self):
        editor = self.editor()
        editor._set("radius", 22)
        editor._store_name("  Soft  ")
        first = deepcopy(editor.draft)
        self.assertEqual(editor.selection, "Soft")
        editor._set("radius", 30)
        editor._store_name("Neon")
        self.assertEqual(set(self.runtime.store.presets), {"Soft", "Neon"})
        editor.preset_choice.set_selected(editor.preset_ids.index("Soft"))
        self.assertEqual(editor.draft, first)
        editor._set("radius", 23)
        self.assertTrue(editor._save_current())
        self.assertEqual(self.runtime.store.presets["Soft"]["common"]["normal"]["radius"], 23)
        editor._store_name("Calm", rename=True)
        self.assertEqual(self.runtime.store.active_name, "Calm")
        self.assertNotIn("Soft", self.runtime.store.presets)
        editor._delete_confirmed("Neon")
        self.assertEqual(set(self.runtime.store.presets), {"Calm"})
        store = RetronStore(self.path, lambda: True)
        profile = store.load()
        self.assertEqual(profile, self.runtime.store.saved_profile)
        self.assertEqual(store.active_name, "Calm")
        self.assertEqual(set(store.presets), {"Calm"})
        editor.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(self.runtime.profile, profile)

    def test_switch_prompt_cancel_discard_and_save_and_original_is_immutable(self):
        editor = self.editor()
        editor._set("radius", 22)
        editor._store_name("Soft")
        saved = deepcopy(self.runtime.profile)
        editor._set("radius", 30)
        with patch.object(editor, "_ask") as ask:
            editor.preset_choice.set_selected(editor.preset_ids.index(ORIGINAL_PRESET))
        self.assertEqual(editor.selection, "Soft")
        answer = ask.call_args.args[2]
        answer(0)
        self.assertEqual(editor.draft["common"]["normal"]["radius"], 30)
        answer(1)
        self.assertIs(editor.selection, ORIGINAL_PRESET)
        self.assertEqual(validate_profile(editor.draft), empty_profile())
        editor._apply()
        editor.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(self.runtime.profile, saved)
        editor = self.editor()
        editor._set("radius", 31)
        editor._finish_switch(ORIGINAL_PRESET, 2)
        self.assertEqual(self.runtime.store.presets["Soft"]["common"]["normal"]["radius"], 31)
        editor._set("radius", 7)
        self.assertTrue(editor._save_current())
        self.assertIsNone(editor.selection)
        editor._load_selection(ORIGINAL_PRESET)
        self.assertEqual(validate_profile(editor.draft), empty_profile())
        self.assertEqual(self.runtime.store.presets["Soft"]["common"]["normal"]["radius"], 31)

    def test_name_validation_and_failed_operations_preserve_draft_and_presets(self):
        editor = self.editor()
        editor._store_name("Soft")
        for name in ("soft", "SOFT", "", " ", "x" * 65, "bad\nname"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                editor._store_name(name)
        editor._set("radius", 30)
        draft = deepcopy(editor.draft)
        raw = self.path.read_bytes()
        with patch.object(self.runtime.store, "save", side_effect=OSError("synthetic failure")):
            editor._finish_switch(ORIGINAL_PRESET, 2)
            self.assertEqual(editor.selection, "Soft")
            self.assertEqual(editor.draft, draft)
            with self.assertRaises(OSError):
                editor._store_name("Another")
            with self.assertRaises(OSError):
                editor._store_name("Renamed", rename=True)
            editor._delete_confirmed("Soft")
        self.assertEqual(set(self.runtime.store.presets), {"Soft"})
        self.assertEqual(self.path.read_bytes(), raw)
        self.writable = False
        editor.update_status()
        for button in (editor.save_button, editor.save_as_button, editor.rename_button, editor.delete_button):
            self.assertFalse(button.get_sensitive())
        with self.assertRaises(PermissionError):
            editor._store_name("Read only")

    def test_delete_selected_keeps_appearance_and_rename_does_not_commit_draft(self):
        editor = self.editor()
        editor._set("radius", 17)
        editor._store_name("Soft")
        saved = deepcopy(self.runtime.profile)
        editor._set("radius", 30)
        editor._store_name("Calm", rename=True)
        self.assertEqual(self.runtime.store.saved_profile, saved)
        self.assertIsNotNone(editor._source)
        editor._delete_confirmed("Calm")
        self.assertEqual(self.runtime.store.presets, {})
        self.assertIsNone(self.runtime.store.active_name)
        self.assertEqual(self.runtime.store.saved_profile, saved)
        editor.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(self.runtime.profile, saved)

    def test_name_dialog_and_pending_confirmation_retire_with_editor(self):
        editor = self.editor()
        editor._name_prompt(False)
        dialog = editor._name_dialog
        editor.response(Gtk.ResponseType.CANCEL)
        self.assertIsNone(editor._name_dialog)
        self.assertFalse(dialog.get_visible())
        self.assertIsNone(dialog.get_transient_for())
        self.assertEqual(editor._name_connections, [])
        editor = self.editor()
        editor._ask("Synthetic confirmation", ["Cancel", "Delete"], Mock())
        cancellable = editor._prompt_cancel
        editor.destroy()
        self.assertTrue(cancellable.is_cancelled())
        deadline = time.monotonic() + 1
        while editor._prompt_cancel is not None and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
        self.assertIsNone(editor._prompt_cancel)
        self.assertIsNone(editor._prompt_dialog)


if __name__ == "__main__":
    unittest.main()
