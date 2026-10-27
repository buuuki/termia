import unittest
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from termia.i18n import translate_key
from termia.update_controller import CheckResult, PreparedUpdate
from termia.update_dependencies import DependencyPlan, Requirement
from termia.update_installers import Installation
from termia.update_service import Release, Version
from termia.update_view import UpdateDialog, attach_updates


class UpdateViewTests(unittest.TestCase):
    def test_initial_focus_is_on_check_button_not_selectable_version(self):
        self.dialog.present()
        for _ in range(20):
            GLib.MainContext.default().iteration(False)
        self.assertIs(self.dialog.get_focus(), self.dialog.check_button)
        self.assertTrue(self.dialog.status.get_selectable())

    def test_status_messages_remain_selectable_when_text_changes(self):
        self.assertTrue(self.dialog.status.get_selectable())
        self.assertTrue(self.dialog.installation_label.get_selectable())
        command = "bash scripts/termia-setup.sh install"
        self.dialog.status.set_text(command)
        self.assertTrue(self.dialog.status.get_selectable())
        self.assertEqual(self.dialog.status.get_text(), command)

    def test_live_output_keeps_installation_busy_and_can_be_copied(self):
        self.dialog.working("update_applying")
        self.dialog.completed("output", "Reading package lists…\n")
        self.assertTrue(self.dialog.spinner.get_spinning())
        self.assertFalse(self.dialog.check_button.get_sensitive())
        self.assertFalse(self.dialog.log_view.get_editable())
        clipboard = Mock()
        with patch.object(self.dialog, "get_clipboard", return_value=clipboard):
            self.dialog.copy_log()
        clipboard.set.assert_called_once_with("Reading package lists…\n")

    def test_log_is_bounded_and_new_check_clears_previous_output(self):
        from termia.update_output import MAX_LOG_CHARS

        self.dialog.completed("output", "old" + "x" * MAX_LOG_CHARS)
        self.assertEqual(self.dialog.log_buffer.get_char_count(), MAX_LOG_CHARS)
        self.dialog.check()
        self.assertEqual(self.dialog.log_buffer.get_char_count(), 0)
        self.assertFalse(self.dialog.log_expander.get_visible())

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

    def dependency_update(self, kind="update_source", missing=True, assisted=True):
        requirement = ((Requirement("gir1.2-gtksource-5"),),)
        plan = DependencyPlan(requirement, ("gir1.2-gtksource-5",),
                              ("gir1.2-gtksource-5",) if missing else (),
                              ("gir1.2-gtksource-5",) if missing else (),
                              "sudo apt update\nsudo apt install gir1.2-gtksource-5" if missing else "",
                              assisted)
        result = CheckResult(Release("v0.6.1-beta", Version.parse("0.6.1-beta"), None),
                             Installation(Mock(kind=kind), ""))
        return PreparedUpdate(result, "synthetic-artifact", plan)

    def test_detected_installation_is_shown_even_before_release_result(self):
        for kind, expected in (("update_source", "Git"), ("update_debian", ".deb")):
            self.dialog.completed("installation", Installation(Mock(kind=kind), ""))
            self.assertIn(expected, self.dialog.installation_label.get_text())
        self.dialog.completed("installation", Installation(None, "update_unknown_installation"))
        self.assertIn("unknown", self.dialog.installation_label.get_text())

    def test_missing_dependencies_warn_and_manual_mode_shows_exact_commands(self):
        prepared = self.dependency_update()
        self.dialog.completed("done", prepared)
        self.assertIn("will not start", self.dialog.status.get_text())
        self.assertIn("gir1.2-gtksource-5", self.dialog.dependency_label.get_text())
        self.assertTrue(self.dialog.assisted_button.get_visible())
        self.assertTrue(self.dialog.manual_button.get_visible())
        self.assertFalse(self.dialog.continue_button.get_visible())
        self.dialog.show_manual()
        self.assertIn(prepared.dependencies.manual_commands, self.dialog.manual_label.get_text())
        self.assertTrue(self.dialog.copy_button.get_visible())
        self.assertTrue(self.dialog.continue_button.get_visible())
        self.factory.return_value.install.assert_not_called()
        self.dialog.apply_prepared(False)
        self.factory.return_value.install.assert_called_once_with(prepared, assisted=False)

    def test_debian_plan_explains_apt_transaction(self):
        self.dialog.completed("done", self.dependency_update("update_debian"))
        self.assertIn("one transaction", self.dialog.status.get_text())

    def test_ready_plan_needs_explicit_continue_without_dependency_install(self):
        self.dialog.completed("done", self.dependency_update(missing=False))
        self.assertFalse(self.dialog.assisted_button.get_visible())
        self.assertFalse(self.dialog.manual_button.get_visible())
        self.assertTrue(self.dialog.continue_button.get_visible())
        self.factory.return_value.install.assert_not_called()

    def test_unavailable_assisted_mode_keeps_manual_option(self):
        self.dialog.completed("done", self.dependency_update(assisted=False))
        self.assertFalse(self.dialog.assisted_button.get_visible())
        self.assertTrue(self.dialog.manual_button.get_visible())

    def test_copy_commands_uses_exact_plan_and_does_not_install(self):
        prepared = self.dependency_update()
        self.dialog.completed("done", prepared)
        clipboard = Mock()
        with patch.object(self.dialog, "get_clipboard", return_value=clipboard):
            self.dialog.copy_commands()
        clipboard.set.assert_called_once_with(prepared.dependencies.manual_commands)
        self.factory.return_value.install.assert_not_called()

    def test_new_check_hides_previous_manual_commands(self):
        self.dialog.completed("done", self.dependency_update())
        self.dialog.show_manual()
        self.dialog.check()
        self.assertFalse(self.dialog.manual_label.get_visible())
        self.assertFalse(self.dialog.copy_button.get_visible())
        self.assertFalse(self.dialog.plan_box.get_visible())
