import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from termia.app import (
    Gtk,
    TermiaWindow,
    gnome_interface_settings,
    system_prefers_dark_theme,
)


class AppThemeTests(unittest.TestCase):
    def host(self, theme: str) -> SimpleNamespace:
        return SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(app=SimpleNamespace(theme=theme))),
            install_tree_styles=Mock(),
        )

    @patch("termia.app.Gtk.Settings.get_default")
    @patch("termia.app.system_prefers_dark_theme", return_value=True)
    def test_system_theme_uses_gnome_dark_preference(
        self,
        system_preference: Mock,
        get_default: Mock,
    ) -> None:
        settings = Mock()
        get_default.return_value = settings
        host = self.host("system")

        TermiaWindow.apply_app_theme(host)

        system_preference.assert_called_once_with(None)
        settings.set_property.assert_called_once_with("gtk-application-prefer-dark-theme", True)
        settings.reset_property.assert_not_called()
        host.install_tree_styles.assert_called_once_with()

    @patch("termia.app.Gtk.Settings.get_default")
    @patch("termia.app.system_prefers_dark_theme", return_value=None)
    def test_system_theme_resets_termia_override_when_desktop_scheme_is_unknown(
        self,
        system_preference: Mock,
        get_default: Mock,
    ) -> None:
        settings = Mock()
        get_default.return_value = settings
        host = self.host("system")

        TermiaWindow.apply_app_theme(host)

        system_preference.assert_called_once_with(None)
        settings.reset_property.assert_called_once_with("gtk-application-prefer-dark-theme")
        settings.set_property.assert_not_called()
        host.install_tree_styles.assert_called_once_with()

    @patch("termia.app.Gtk.Settings.get_default")
    def test_explicit_themes_keep_their_requested_gtk_variant(self, get_default: Mock) -> None:
        settings = Mock()
        get_default.return_value = settings

        TermiaWindow.apply_app_theme(self.host("dark"))
        TermiaWindow.apply_app_theme(self.host("light"))

        self.assertEqual(
            settings.set_property.call_args_list,
            [
                (("gtk-application-prefer-dark-theme", True),),
                (("gtk-application-prefer-dark-theme", False),),
            ],
        )

    @patch("termia.app.Gio.Settings.new_full")
    @patch("termia.app.Gio.SettingsSchemaSource.get_default")
    def test_gnome_color_scheme_is_mapped_to_a_dark_preference(
        self,
        get_source: Mock,
        new_settings: Mock,
    ) -> None:
        schema = Mock()
        schema.has_key.return_value = True
        source = Mock()
        source.lookup.return_value = schema
        get_source.return_value = source
        new_settings.return_value.get_string.return_value = "prefer-dark"

        self.assertTrue(system_prefers_dark_theme())

    @patch("termia.app.Gio.SettingsSchemaSource.get_default")
    def test_default_gnome_color_scheme_leaves_the_gtk_theme_unchanged(self, get_source: Mock) -> None:
        schema = Mock()
        schema.has_key.return_value = True
        source = Mock()
        source.lookup.return_value = schema
        get_source.return_value = source
        with patch("termia.app.Gio.Settings.new_full") as new_settings:
            new_settings.return_value.get_string.return_value = "default"

            self.assertIsNone(system_prefers_dark_theme())

    @patch("termia.app.gnome_interface_settings")
    def test_connects_to_gnome_color_scheme_changes(self, interface_settings: Mock) -> None:
        settings = Mock()
        interface_settings.return_value = settings
        host = SimpleNamespace(on_system_color_scheme_changed=Mock())

        TermiaWindow.connect_system_theme_changes(host)

        self.assertIs(host._gnome_interface_settings, settings)
        settings.connect.assert_called_once_with(
            "changed::color-scheme",
            host.on_system_color_scheme_changed,
        )

    def test_gnome_color_scheme_change_reapplies_only_system_theme(self) -> None:
        system_host = SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(app=SimpleNamespace(theme="system"))),
            apply_app_theme=Mock(),
        )
        dark_host = SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(app=SimpleNamespace(theme="dark"))),
            apply_app_theme=Mock(),
        )

        TermiaWindow.on_system_color_scheme_changed(system_host)
        TermiaWindow.on_system_color_scheme_changed(dark_host)

        system_host.apply_app_theme.assert_called_once_with()
        dark_host.apply_app_theme.assert_not_called()

    @patch("termia.app.Gio.Settings.new_full")
    @patch("termia.app.Gio.SettingsSchemaSource.get_default")
    def test_builds_gnome_settings_only_when_the_schema_is_available(
        self,
        get_source: Mock,
        new_settings: Mock,
    ) -> None:
        schema = Mock()
        schema.has_key.return_value = True
        source = Mock()
        source.lookup.return_value = schema
        get_source.return_value = source

        self.assertIs(gnome_interface_settings(), new_settings.return_value)

    @patch("termia.app.Gtk.StyleContext.add_provider_for_display")
    @patch("termia.app.Gtk.StyleContext.remove_provider_for_display")
    @patch("termia.app.Gtk.CssProvider")
    @patch("termia.app.Gdk.Display.get_default")
    def test_application_styles_replace_the_previous_provider(
        self,
        get_display: Mock,
        css_provider: Mock,
        remove_provider: Mock,
        add_provider: Mock,
    ) -> None:
        display = Mock()
        previous_provider = Mock()
        provider = Mock()
        get_display.return_value = display
        css_provider.return_value = provider
        host = SimpleNamespace(
            store=SimpleNamespace(
                data=SimpleNamespace(
                    app=SimpleNamespace(theme="system"),
                    terminal=SimpleNamespace(
                        background="#202020",
                        split_separator_color="#008712",
                        split_separator_thickness=1,
                    ),
                ),
            ),
            _application_css_provider=previous_provider,
        )

        TermiaWindow.install_tree_styles(host)

        css = provider.load_from_data.call_args.args[0].decode()
        self.assertNotIn("termia_menu_bg", css)
        remove_provider.assert_called_once_with(display, previous_provider)
        add_provider.assert_called_once_with(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.assertIs(host._application_css_provider, provider)


if __name__ == "__main__":
    unittest.main()
