import unittest

from termia.connection_history_view import ConnectionHistoryDialog


class ConnectionHistoryDialogTests(unittest.TestCase):
    def test_accepts_explicit_dialog_dependencies(self) -> None:
        parent = object()
        presenter = object()
        translate = lambda key: key
        clear_history = lambda: None
        configure_write_action = lambda widget: widget
        show_toast = lambda message: None

        dialog = ConnectionHistoryDialog(
            parent,
            presenter,
            translate,
            clear_history,
            configure_write_action,
            show_toast,
        )

        self.assertIs(dialog.parent, parent)
        self.assertIs(dialog.presenter, presenter)
        self.assertIs(dialog.translate, translate)
        self.assertIs(dialog.clear_history, clear_history)
        self.assertIs(dialog.configure_write_action, configure_write_action)
        self.assertIs(dialog.show_toast, show_toast)
