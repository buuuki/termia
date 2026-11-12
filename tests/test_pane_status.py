import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.i18n import translate_key
from termia.terminal_sessions import TerminalSessionsMixin


class PaneStatusTests(unittest.TestCase):
    def setUp(self):
        self.connection = SimpleNamespace(id="server-a", name="Example <A> & B")
        self.profile = SimpleNamespace(id="local-a", name="Local example")
        self.host = SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(
                servers=[self.connection], local_terminals=[self.profile],
            )),
            t=lambda key: translate_key(key, "en"),
        )
        self.pane = SimpleNamespace(
            server_id="server-a", local_profile_id=None, title="Renamed tab",
            history_server_name="Original example", status_detail="",
            connected=True, disconnect_requested=False, child_process=object(),
            status_label=Mock(), disconnect_button=Mock(), retired=False,
        )

    def render(self, detail=None):
        TerminalSessionsMixin.update_pane_status(self.host, self.pane, detail)
        return self.pane.status_label.set_markup.call_args.args[0]

    def test_connected_name_is_escaped_and_process_details_are_in_tooltip(self):
        markup = self.render("PID 123")
        self.assertIn("Connected · Example &lt;A&gt; &amp; B", markup)
        self.assertIn('foreground="#78BD97"', markup)
        self.assertNotIn("Renamed tab", markup)
        self.assertNotIn("PID", markup)
        tooltip = self.pane.status_label.set_tooltip_text.call_args.args[0]
        self.assertIn("PID 123", tooltip)
        self.assertIn("authentication may still be pending", tooltip)

    def test_starting_and_disconnected_states_keep_connection_name(self):
        self.pane.child_process = None
        self.assertIn("Connecting · Example", self.render())
        self.pane.connected = False
        markup = self.render("Synthetic connection failure")
        self.assertIn("Disconnected · Example", markup)
        self.assertIn('foreground="#B3C1D1"', markup)
        self.render()
        self.assertIn("Synthetic connection failure",
                      self.pane.status_label.set_tooltip_text.call_args.args[0])

    def test_requested_disconnect_does_not_remain_green_while_child_exits(self):
        self.pane.disconnect_requested = True
        self.assertIn("Disconnected · Example", self.render())

    def test_local_profile_and_deleted_connection_retain_their_names(self):
        self.host.store.data.servers = []
        self.assertIn("Original example", self.render())
        self.pane.server_id = None
        self.pane.local_profile_id = "local-a"
        self.assertIn("Running · Local example", self.render())
        self.assertNotIn("authentication", self.pane.status_label.set_tooltip_text.call_args.args[0])

    def test_labels_follow_spanish_and_catalan_and_retired_panes_are_untouched(self):
        for language, expected in (("es", "Conectada"), ("ca", "Connectada")):
            self.host.t = lambda key, language=language: translate_key(key, language)
            self.assertIn(expected, self.render())
        self.pane.status_label.reset_mock()
        self.pane.retired = True
        TerminalSessionsMixin.update_pane_status(self.host, self.pane)
        self.pane.status_label.set_markup.assert_not_called()

    def test_local_states_and_action_use_process_language(self):
        self.pane.server_id = None
        for language, running, starting, finished, action in (
            ("en", "Running", "Starting…", "Finished", "End terminal"),
            ("es", "En ejecución", "Iniciando…", "Finalizado", "Finalizar terminal"),
            ("ca", "En execució", "Iniciant…", "Finalitzat", "Finalitzar terminal"),
        ):
            with self.subTest(language=language):
                self.host.t = lambda key, language=language: translate_key(key, language)
                self.pane.connected = True
                self.pane.child_process = object()
                self.assertIn(running, self.render())
                self.pane.disconnect_button.set_label.assert_called_with(action)
                self.pane.child_process = None
                self.assertIn(starting, self.render())
                self.pane.connected = False
                self.assertIn(finished, self.render())


if __name__ == "__main__":
    unittest.main()
