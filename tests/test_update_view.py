import unittest
from dataclasses import replace
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
    def test_success_log_separates_restart_message_with_blank_line(self):
        for kind in ("update_source", "update_debian"):
            self.dialog.result = self.dependency_update(kind).result
            self.dialog.log_buffer.set_text("Completed task\n")
            self.dialog.completed("done", None)
            text = self.dialog.log_buffer.get_text(
                self.dialog.log_buffer.get_start_iter(),
                self.dialog.log_buffer.get_end_iter(), False)
            key = "update_installed_source" if kind == "update_source" else "update_installed"
            self.assertEqual(text, "Completed task\n\n" + self.dialog.t(key) + "\n")

    def test_window_grows_for_log_and_content_keeps_footer_at_bottom(self):
        self.assertEqual(self.dialog.get_default_size()[0], 480)
        self.dialog.completed("output", "Preparing…\n")
        self.assertEqual(tuple(self.dialog.get_default_size()), (640, 620))
        self.dialog.log_expander.set_expanded(False)
        self.assertEqual(tuple(self.dialog.get_default_size()), (640, 620))
        content = self.dialog.get_child().get_first_child()
        self.assertTrue(content.get_vexpand())
        self.assertFalse(hasattr(self.dialog, "copy_log_button"))
        self.dialog.check()
        self.assertEqual(self.dialog.get_default_size()[0], 480)
        self.assertFalse(self.dialog.log_expander.get_visible())

    def test_dependency_buttons_do_not_stretch_with_window(self):
        for button in (self.dialog.assisted_button, self.dialog.continue_button):
            self.assertEqual(button.get_halign(), Gtk.Align.START)
            self.assertFalse(button.get_hexpand())
            self.assertEqual(button.get_size_request()[0], 160)

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

    def test_live_output_keeps_installation_busy_and_is_selectable(self):
        self.dialog.working("update_applying")
        self.dialog.completed("output", "Reading package lists…\n")
        self.assertTrue(self.dialog.spinner.get_spinning())
        self.assertFalse(self.dialog.check_button.get_sensitive())
        self.assertFalse(self.dialog.log_view.get_editable())
        self.assertEqual(self.dialog.log_buffer.get_char_count(), len("Reading package lists…\n"))

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
        plan = DependencyPlan(requirement,
                              ("gir1.2-gtksource-5",) if missing else (),
                              ("gir1.2-gtksource-5",) if missing else (),
                              assisted)
        result = CheckResult(Release("v0.6.1-beta", Version.parse("0.6.1-beta"), None),
                             Installation(Mock(kind=kind), ""))
        return PreparedUpdate(result, "synthetic-artifact", plan)

    def test_download_and_review_prepares_without_another_dialog_or_installing(self):
        result = self.dependency_update().result
        self.dialog.completed("done", result)
        with patch("termia.update_view.Gtk.Dialog") as confirmation:
            self.dialog.install_button.emit("clicked")
        confirmation.assert_not_called()
        self.factory.return_value.prepare_update.assert_called_once_with(result)
        self.factory.return_value.install.assert_not_called()
        self.assertFalse(self.dialog.check_button.get_visible())

    def test_detected_installation_is_shown_even_before_release_result(self):
        for kind, expected in (("update_source", "Git"), ("update_debian", ".deb")):
            self.dialog.completed("installation", Installation(Mock(kind=kind), ""))
            self.assertIn(expected, self.dialog.installation_label.get_text())
        self.dialog.completed("installation", Installation(None, "update_unknown_installation"))
        self.assertIn("unknown", self.dialog.installation_label.get_text())

    def test_missing_dependencies_are_named_without_a_manual_installation_button(self):
        prepared = self.dependency_update()
        self.dialog.completed("done", prepared)
        self.assertEqual(self.dialog.status.get_text(),
                         "Updating Termia will automatically install these dependencies:\n"
                         "gir1.2-gtksource-5")
        log = self.dialog.log_buffer.get_text(
            self.dialog.log_buffer.get_start_iter(), self.dialog.log_buffer.get_end_iter(), False)
        self.assertIn("Update prepared and verified; dependencies checked.", log)
        self.assertEqual(log.count("gir1.2-gtksource-5"), 1)
        self.assertTrue(self.dialog.assisted_button.get_visible())
        self.assertFalse(self.dialog.continue_button.get_visible())
        buttons = []

        def visit(widget):
            if isinstance(widget, Gtk.Button):
                buttons.append(widget.get_label())
            child = widget.get_first_child()
            while child is not None:
                visit(child)
                child = child.get_next_sibling()

        visit(self.dialog)
        self.assertNotIn(self.dialog.t("update_manual"), buttons)
        self.factory.return_value.install.assert_not_called()

    def test_debian_plan_omits_apt_transaction_message(self):
        self.dialog.completed("done", self.dependency_update("update_debian"))
        self.assertNotIn("APT", self.dialog.status.get_text())

    def test_ready_plan_lists_requirements_and_needs_explicit_continue(self):
        prepared = self.dependency_update(missing=False)
        plan = replace(prepared.dependencies, required=(
            (Requirement("python3", ">=", "3.10"),),
            (Requirement("gir1.2-gtksource-5"),),
        ))
        prepared = replace(prepared, dependencies=plan)
        self.dialog.completed("done", prepared)
        self.assertEqual(self.dialog.status.get_text(),
                         "All required dependencies are available:\n"
                         "python3 (>= 3.10), gir1.2-gtksource-5")
        self.assertFalse(self.dialog.assisted_button.get_visible())
        self.assertTrue(self.dialog.continue_button.get_visible())
        self.factory.return_value.install.assert_not_called()
        self.dialog.continue_button.emit("clicked")
        self.factory.return_value.install.assert_called_once_with(prepared, assisted=False)

    def test_unavailable_assisted_installation_leaves_missing_update_pending(self):
        self.dialog.completed("done", self.dependency_update(assisted=False))
        self.assertEqual(self.dialog.status.get_text(),
                         "Missing dependencies:\ngir1.2-gtksource-5")
        self.assertFalse(self.dialog.assisted_button.get_visible())
        self.assertFalse(self.dialog.continue_button.get_visible())
        self.factory.return_value.install.assert_not_called()

    def test_multiple_missing_dependencies_are_named_without_changing_the_plan(self):
        prepared = self.dependency_update()
        plan = replace(prepared.dependencies, missing=(
            "gir1.2-gtksource-5", "python3-paramiko (>= 2.12)",
        ))
        prepared = replace(prepared, dependencies=plan)
        self.dialog.completed("done", prepared)
        self.assertEqual(self.dialog.status.get_text(),
                         "Updating Termia will automatically install these dependencies:\n"
                         "gir1.2-gtksource-5, python3-paramiko (>= 2.12)")
        self.assertIs(self.dialog.prepared.dependencies, plan)
        self.factory.return_value.install.assert_not_called()

    def test_dependency_status_is_localized_and_remains_selectable(self):
        for language in ("en", "es", "ca"):
            self.dialog.t = lambda key, language=language: translate_key(key, language)
            for missing in (True, False):
                self.dialog.completed("done", self.dependency_update(missing=missing))
                key = "update_dependencies_automatic" if missing else "update_dependencies_ready"
                expected = translate_key(key, language).format(dependencies="gir1.2-gtksource-5")
                self.assertEqual(self.dialog.status.get_text(), expected)
                self.assertNotIn("{dependencies}", expected)
                self.assertTrue(self.dialog.status.get_selectable())

    def test_final_action_is_translated_and_preserves_installation_mode(self):
        for language, label in (("en", "Update Termia"), ("es", "Actualizar Termia"),
                                ("ca", "Actualitza Termia")):
            dialog = UpdateDialog(
                self.parent, lambda key, language=language: translate_key(key, language),
                self.factory)
            self.addCleanup(dialog.destroy)
            for missing in (True, False):
                prepared = self.dependency_update(missing=missing)
                dialog.completed("done", prepared)
                button = dialog.assisted_button if missing else dialog.continue_button
                self.assertEqual(button.get_label(), label)
                self.factory.return_value.install.assert_not_called()
                button.emit("clicked")
                self.factory.return_value.install.assert_called_once_with(
                    prepared, assisted=missing)
                self.factory.return_value.install.reset_mock()

    def test_new_check_clears_previous_dependency_information(self):
        self.dialog.completed("done", self.dependency_update())
        self.dialog.check()
        self.assertEqual(self.dialog.log_buffer.get_char_count(), 0)
        self.assertFalse(self.dialog.log_expander.get_visible())
        self.assertFalse(self.dialog.plan_box.get_visible())
        self.assertEqual(self.dialog.status.get_text(), self.dialog.t("update_checking"))

    def test_dependency_recovery_message_and_action_keep_terminal_access(self):
        prepared = self.dependency_update()
        result = CheckResult(prepared.result.release, prepared.result.installation, True)
        self.dialog.completed("done", result)
        self.assertIn("already contains", self.dialog.status.get_text())
        self.assertEqual(self.dialog.install_button.get_label(), "Review dependencies")
        self.assertFalse(self.dialog.get_modal())
        self.assertTrue(self.dialog.status.get_selectable())
        self.dialog.confirm_install(None)
        self.factory.return_value.prepare_update.assert_called_once_with(result)

    def test_content_and_actions_share_outer_insets_without_nested_padding(self):
        from termia.dialog_actions import DIALOG_ACTION_INSET_END, DIALOG_ACTION_SPACING

        content = self.dialog.get_child().get_first_child()
        actions = content.get_next_sibling()
        self.assertEqual(content.get_margin_end(), DIALOG_ACTION_INSET_END)
        self.assertEqual(actions.get_margin_end(), DIALOG_ACTION_INSET_END)
        self.assertEqual(content.get_parent().get_margin_end(), 0)
        self.assertEqual(actions.get_spacing(), DIALOG_ACTION_SPACING)
