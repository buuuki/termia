"""GTK regression for reordering live split pane widgets."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.terminal_sessions import Gdk, Gtk, TerminalSessionsMixin
from termia.ui_state import SignalConnections


class SplitReorderTests(unittest.TestCase):
    def test_swap_between_nested_dividers_keeps_leaf_identity_and_positions(self):
        page = Gtk.Box()
        root = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        nested = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        page.append(root)
        root.set_end_child(nested)
        a, b, c = (self.make_pane() for _ in range(3))
        root.set_start_child(a.container)
        nested.set_start_child(b.container)
        nested.set_end_child(c.container)
        root.set_position(320)
        nested.set_position(210)

        panes = {id(pane.terminal): pane for pane in (a, b, c)}
        session = SimpleNamespace(id="fixture", page=page, active_terminal_ids=set(panes),
                                  pane_for_terminal=lambda terminal: panes.get(id(terminal)))
        host = TerminalSessionsMixin()
        host.shutdown_in_progress = False
        host.session_registry = Mock()
        host.session_registry.get.return_value = session
        host.configure_pane_reorder(session, a)
        providers = [controller for controller in a.status_label.observe_controllers()
                     if isinstance(controller, Gtk.DragSource)]
        self.assertEqual(len(providers), 1)
        session.active_panes = lambda: list(panes.values())
        provider = providers[0].emit("prepare", 1.0, 1.0)
        self.assertIsInstance(provider, Gdk.ContentProvider)

        self.assertTrue(host.swap_split_panes(session, a.terminal, b.terminal))
        self.assertIs(root.get_start_child(), b.container)
        self.assertIs(nested.get_start_child(), a.container)
        self.assertIs(nested.get_end_child(), c.container)
        self.assertEqual((root.get_position(), nested.get_position()), (320, 210))
        a.terminal.grab_focus.assert_called_once_with()
        b.retired = True
        self.assertFalse(host.swap_split_panes(session, a.terminal, b.terminal))
        self.assertIs(nested.get_start_child(), a.container)

    @staticmethod
    def make_pane():
        label = Gtk.Label(label="Synthetic")
        container = Gtk.Box()
        container.append(label)
        return SimpleNamespace(terminal=Mock(), container=container, status_label=label,
                               ui_signals=SignalConnections(), retired=False)
