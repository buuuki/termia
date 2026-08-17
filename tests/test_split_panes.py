import unittest
from types import SimpleNamespace
from unittest.mock import patch

from termia.split_panes import Gtk, SplitPaneController


class FakeWidget:
    def __init__(self, *, width=0, height=0, parent=None) -> None:
        self.width = width
        self.height = height
        self.parent = parent
        self.classes = []

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_parent(self):
        return self.parent

    def add_css_class(self, name):
        self.classes.append(name)


class FakeTerminal:
    def __init__(self) -> None:
        self.focused = False

    def grab_focus(self):
        self.focused = True


class FakePaned(FakeWidget):
    next_handler_id = 1

    def __init__(self, *, orientation, width=0, height=0, parent=None) -> None:
        super().__init__(width=width, height=height, parent=parent)
        self.orientation = orientation
        self.position = 0
        self.start_child = None
        self.end_child = None
        self.handlers = {}

    def set_wide_handle(self, _enabled):
        pass

    def set_hexpand(self, _enabled):
        pass

    def set_vexpand(self, _enabled):
        pass

    def set_resize_start_child(self, _enabled):
        pass

    def set_resize_end_child(self, _enabled):
        pass

    def set_shrink_start_child(self, _enabled):
        pass

    def set_shrink_end_child(self, _enabled):
        pass

    def set_start_child(self, child):
        self.start_child = child
        if child is not None:
            child.parent = self

    def set_end_child(self, child):
        self.end_child = child
        if child is not None:
            child.parent = self

    def set_position(self, position):
        self.position = position

    def get_position(self):
        return self.position

    def connect(self, signal, callback):
        handler_id = self.next_handler_id
        type(self).next_handler_id += 1
        self.handlers[handler_id] = (signal, callback)
        return handler_id

    def disconnect(self, handler_id):
        self.handlers.pop(handler_id)

    def emit_max_position_changed(self):
        for _handler_id, (_signal, callback) in tuple(self.handlers.items()):
            callback(self, object())


class SplitPaneControllerTests(unittest.TestCase):
    def controller(self, target, new_terminal, new_pane, ancestor, outer_ancestor):
        def replace_terminal(_target, replacement):
            ancestor.position = 17
            outer_ancestor.position = 29
            ancestor.set_start_child(replacement)
            return True

        return SplitPaneController(
            lambda _session: new_terminal,
            lambda _session, selected: new_pane if selected is new_terminal else target,
            replace_terminal,
        )

    def test_nested_split_uses_target_size_and_preserves_ancestor_position(self) -> None:
        outer_ancestor = FakePaned(orientation=object(), width=1200, height=800)
        outer_ancestor.position = 520
        ancestor = FakePaned(
            orientation=object(),
            width=900,
            height=600,
            parent=outer_ancestor,
        )
        outer_ancestor.set_end_child(ancestor)
        ancestor.position = 360
        target = FakeWidget(width=401, height=260, parent=ancestor)
        ancestor.set_start_child(target)
        new_terminal = FakeTerminal()
        new_pane = FakeWidget()
        idle_callbacks = []
        controller = self.controller(
            target,
            new_terminal,
            new_pane,
            ancestor,
            outer_ancestor,
        )

        with (
            patch("termia.split_panes.Gtk.Paned", FakePaned),
            patch(
                "termia.split_panes.GLib.idle_add",
                side_effect=lambda callback, *args: idle_callbacks.append((callback, args)),
            ),
            patch("termia.split_panes.GLib.timeout_add") as timeout_add,
        ):
            result = controller.split_terminal(SimpleNamespace(), object(), "right")

        created_split = ancestor.start_child
        self.assertIs(result, new_terminal)
        self.assertEqual(created_split.position, 200)
        self.assertEqual(ancestor.position, 360)
        self.assertEqual(outer_ancestor.position, 520)
        self.assertTrue(new_terminal.focused)
        timeout_add.assert_not_called()

        ancestor.position = 24
        outer_ancestor.position = 31
        callback, args = idle_callbacks.pop()
        callback(*args)
        self.assertEqual(ancestor.position, 360)
        self.assertEqual(outer_ancestor.position, 520)

    def test_unallocated_split_centers_once_when_gtk_assigns_a_size(self) -> None:
        paned = FakePaned(orientation=Gtk.Orientation.HORIZONTAL)

        SplitPaneController.initialize_split_position(paned, paned.orientation, 0)

        self.assertEqual(paned.position, 0)
        self.assertEqual(len(paned.handlers), 1)
        paned.width = 301
        paned.emit_max_position_changed()
        self.assertEqual(paned.position, 150)
        self.assertEqual(paned.handlers, {})


if __name__ == "__main__":
    unittest.main()
