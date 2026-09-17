import unittest
from unittest.mock import Mock

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from termia.i18n import translate_key
from termia.update_controller import CheckResult
from termia.update_installers import Installation
from termia.update_service import Release, Version
from termia.update_view import UpdateDialog, attach_updates


class UpdateViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Gtk.init()
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No usable GTK display")

    def setUp(self):
        self.parent = Gtk.AboutDialog()
        self.addCleanup(self.parent.destroy)
        self.factory = Mock()
        self.factory.return_value.busy = False
        self.factory.return_value.applying = False
        self.factory.return_value.closed = False
        self.dialog = UpdateDialog(self.parent, lambda k: translate_key(k, "en"), self.factory)
        self.addCleanup(self.dialog.destroy)

    def test_about_header_action_preserves_metadata(self):
        self.parent.set_program_name("Termia")
        self.parent.set_version("0.6.0-beta.2-dev")
        titlebar = self.parent.get_titlebar()
        attach_updates(self.parent, lambda k: translate_key(k, "en"))
        self.assertIs(self.parent.get_titlebar(), titlebar)
        self.assertEqual(self.parent.get_program_name(), "Termia")
        self.assertEqual(self.parent.get_version(), "0.6.0-beta.2-dev")

    def test_check_only_result_explains_development_restriction(self):
        result = CheckResult(None, Installation(None, "update_checkout_blocked"))
        self.dialog.completed("done", result)
        self.assertIn("Development branches", self.dialog.status.get_text())
        self.assertFalse(self.dialog.install_button.get_visible())

    def test_verified_update_enables_install_and_installed_disables_reapply(self):
        adapter = Mock(kind="update_source")
        result = CheckResult(Release("v0.6.0-beta.2", Version.parse("0.6.0-beta.2"), None), Installation(adapter, ""))
        self.dialog.completed("done", result)
        self.assertTrue(self.dialog.install_button.get_visible())
        self.assertTrue(self.dialog.install_button.get_sensitive())
        self.assertTrue(self.dialog.notes.get_visible())
        self.dialog.completed("done", None)
        self.assertFalse(self.dialog.install_button.get_visible())
        self.assertFalse(self.dialog.check_button.get_sensitive())

    def test_no_digest_keeps_debian_install_unavailable(self):
        result = CheckResult(Release("v0.6.0-beta.2", Version.parse("0.6.0-beta.2"), None), Installation(Mock(kind="update_debian"), ""))
        self.dialog.completed("done", result)
        self.assertFalse(self.dialog.install_button.get_visible())
        self.assertIn("SHA-256", self.dialog.status.get_text())

    def test_close_cancels_preparation_but_cannot_interrupt_applying(self):
        self.assertFalse(self.dialog.close_requested(self.dialog))
        self.factory.return_value.close.assert_called_once()
        self.factory.return_value.close.reset_mock()
        self.factory.return_value.applying = True
        self.assertTrue(self.dialog.close_requested(self.dialog))
        self.factory.return_value.close.assert_not_called()
