# SPDX-FileCopyrightText: 2026 Termia contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from termia.models import AppSettings
from termia.sidebar import SidebarMixin
from termia.stores import ConnectionStore, SettingsStore


class SidebarWidthTests(unittest.TestCase):
    def test_settings_defaults_invalid_values_and_read_only_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            self.assertEqual(SettingsStore(path).app.connection_sidebar_width, 280)
            for value, expected in ((420, 420), (20, 280), (True, 280),
                                    (None, 280), ("420", 280), (420.5, 280)):
                with self.subTest(value=value):
                    original = json.dumps({"app": {"connection_sidebar_width": value}})
                    path.write_text(original, encoding="utf-8")
                    settings = SettingsStore(path, read_only=True)
                    self.assertEqual(settings.app.connection_sidebar_width, expected)
                    settings.save()
                    self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_width_survives_preferences_update_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(root / "connections.json", root / "settings.json",
                                    root / "statistics.json", root / "lock", root / "history")
            try:
                store.data.app.connection_sidebar_width = 420
                store.update_app_settings(AppSettings(language="es"))
                settings = SettingsStore(root / "settings.json")
                self.assertEqual(settings.app.connection_sidebar_width, 420)
                self.assertEqual(settings.app.language, "es")
            finally:
                store.close()

    def host(self, width=1600, preferred=380, minimum=270):
        class Host(SidebarMixin):
            pass
        host = Host()
        host.sidebar_visible = True
        host.sidebar_width = preferred
        host._sidebar_width_source = None
        host._sidebar_setting_position = False
        host._sidebar_layout_changed = False
        host._sidebar_allocated_width = width
        host.body = Mock()
        host.body.get_width.return_value = width
        host.body.get_position.return_value = preferred
        host.sidebar = Mock()
        host.sidebar.measure.return_value = (minimum, minimum, -1, -1)
        host.store = SimpleNamespace(read_only=False, save_settings=Mock(),
                                     data=SimpleNamespace(app=AppSettings()))
        return host

    def test_minimum_toolbar_and_quarter_limits(self):
        for width, requested, controls_minimum, expected in (
                (1600, 50, 270, 280), (1600, 900, 270, 400),
                (1600, 50, 320, 320), (900, 900, 270, 280),
                (900, 900, 320, 320)):
            with self.subTest(width=width, requested=requested, controls=controls_minimum):
                host = self.host(width, requested, controls_minimum)
                host.update_sidebar_width()
                host.body.set_position.assert_called_once_with(expected)
                self.assertEqual(host.sidebar_width, expected)

    def test_temporary_window_limits_preserve_preferred_width(self):
        host = self.host(preferred=380)
        host.body.get_width.return_value = 1000
        host.update_sidebar_width()
        host.body.set_position.assert_called_with(280)
        host.save_sidebar_width()
        self.assertEqual(host.store.data.app.connection_sidebar_width, 380)
        host.body.get_width.return_value = 1600
        host.update_sidebar_width()
        host.body.set_position.assert_called_with(380)

    def test_hidden_and_read_only_instances_do_not_overwrite_settings(self):
        host = self.host()
        host.sidebar_visible = False
        host.body.get_position.return_value = 0
        host.update_sidebar_width()
        self.assertEqual(host.sidebar_width, 380)
        host.body.set_position.assert_not_called()
        host.store.read_only = True
        host.save_sidebar_width()
        host.store.save_settings.assert_not_called()
        self.assertEqual(host.store.data.app.connection_sidebar_width, 280)
