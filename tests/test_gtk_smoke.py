import importlib.util
import unittest


class GtkSmokeTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("gi"), "GTK bindings are unavailable")
    def test_gtk_application_can_be_constructed(self) -> None:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        application = Gtk.Application(application_id="local.termia.test")
        self.assertEqual(application.get_application_id(), "local.termia.test")
