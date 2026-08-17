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


class FakeRoot(FakeWidget):
    def __init__(self, child) -> None:
        super().__init__()
        self.child = child
        child.parent = self

    def replace(self, target, replacement):
        if self.child is not target:
            return False
        self.child = replacement
        replacement.parent = self
        return True


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

    def test_every_direction_splits_only_the_target_in_half(self) -> None:
        cases = (
            ("left", Gtk.Orientation.HORIZONTAL, 401, 260, 200, True),
            ("right", Gtk.Orientation.HORIZONTAL, 401, 260, 200, False),
            ("up", Gtk.Orientation.VERTICAL, 401, 261, 130, True),
            ("down", Gtk.Orientation.VERTICAL, 401, 261, 130, False),
        )

        for direction, orientation, width, height, expected, new_first in cases:
            with self.subTest(direction=direction):
                target_terminal = FakeTerminal()
                target = FakeWidget(width=width, height=height)
                root = FakeRoot(target)
                new_terminal = FakeTerminal()
                new_pane = FakeWidget()

                controller = SplitPaneController(
                    lambda _session: new_terminal,
                    lambda _session, selected: (
                        new_pane if selected is new_terminal else target
                    ),
                    root.replace,
                )

                with (
                    patch("termia.split_panes.Gtk.Paned", FakePaned),
                    patch("termia.split_panes.GLib.idle_add"),
                    patch("termia.split_panes.GLib.timeout_add") as timeout_add,
                ):
                    controller.split_terminal(
                        SimpleNamespace(), target_terminal, direction
                    )

                created_split = root.child
                self.assertEqual(created_split.orientation, orientation)
                self.assertEqual(created_split.position, expected)
                self.assertIs(
                    created_split.start_child,
                    new_pane if new_first else target,
                )
                self.assertIs(
                    created_split.end_child,
                    target if new_first else new_pane,
                )
                timeout_add.assert_not_called()

    def test_progressive_second_third_and_fourth_panes_preserve_geometry(self) -> None:
        session = SimpleNamespace()
        first_terminal = FakeTerminal()
        first_pane = FakeWidget(width=801, height=601)
        root = FakeRoot(first_pane)
        panes = {first_terminal: first_pane}
        idle_callbacks = []

        def create_terminal(_session):
            terminal = FakeTerminal()
            panes[terminal] = FakeWidget()
            return terminal

        def replace_terminal(target, replacement):
            parent = target.parent
            if isinstance(parent, FakeRoot):
                replaced = parent.replace(target, replacement)
            elif parent.start_child is target:
                parent.set_start_child(replacement)
                replaced = True
            elif parent.end_child is target:
                parent.set_end_child(replacement)
                replaced = True
            else:
                replaced = False

            current = replacement.parent
            while isinstance(current, FakePaned):
                current.position = -1
                current = current.parent
            return replaced

        controller = SplitPaneController(
            create_terminal,
            lambda _session, terminal: panes[terminal],
            replace_terminal,
        )

        def split_and_check(terminal, direction, expected_position):
            target = panes[terminal]
            ancestors = []
            parent = target.parent
            while isinstance(parent, FakePaned):
                ancestors.append((parent, parent.position))
                parent = parent.parent

            result = controller.split_terminal(session, terminal, direction)
            created_split = target.parent
            self.assertEqual(created_split.position, expected_position)
            for ancestor, position in ancestors:
                self.assertEqual(ancestor.position, position)

            for ancestor, _position in ancestors:
                ancestor.position = -2
            if ancestors:
                callback, args = idle_callbacks.pop()
                callback(*args)
            for ancestor, position in ancestors:
                self.assertEqual(ancestor.position, position)
            return result, created_split

        with (
            patch("termia.split_panes.Gtk.Paned", FakePaned),
            patch(
                "termia.split_panes.GLib.idle_add",
                side_effect=lambda callback, *args: idle_callbacks.append(
                    (callback, args)
                ),
            ),
            patch("termia.split_panes.GLib.timeout_add") as timeout_add,
        ):
            second_terminal, outer = split_and_check(first_terminal, "right", 400)

            outer.position = 347
            first_pane.width = 400
            first_pane.height = 601
            third_terminal, lower_split = split_and_check(
                first_terminal, "down", 300
            )

            outer.position = 347
            lower_split.position = 219
            panes[third_terminal].width = 401
            panes[third_terminal].height = 300
            _fourth_terminal, _inner_split = split_and_check(
                third_terminal, "left", 200
            )

        self.assertIsNotNone(second_terminal)
        self.assertEqual(len(panes), 4)
        self.assertEqual(outer.position, 347)
        self.assertEqual(lower_split.position, 219)
        timeout_add.assert_not_called()

    def test_unallocated_split_centers_for_both_orientations(self) -> None:
        cases = (
            (Gtk.Orientation.HORIZONTAL, 303, 99, 151),
            (Gtk.Orientation.VERTICAL, 99, 305, 152),
        )

        for orientation, width, height, expected in cases:
            with self.subTest(orientation=orientation):
                paned = FakePaned(orientation=orientation)

                SplitPaneController.initialize_split_position(
                    paned, orientation, 0
                )
                paned.width = width
                paned.height = height
                paned.emit_max_position_changed()

                self.assertEqual(paned.position, expected)
                self.assertEqual(paned.handlers, {})

    def test_workspace_reconstruction_skips_provisional_ancestor_restore(self) -> None:
        outer = FakePaned(orientation=Gtk.Orientation.HORIZONTAL)
        outer.position = 0
        target = FakeWidget(width=400, height=300, parent=outer)
        outer.set_end_child(target)
        new_terminal = FakeTerminal()
        new_pane = FakeWidget()

        def replace_terminal(_target, replacement):
            outer.position = 37
            outer.set_end_child(replacement)
            return True

        controller = SplitPaneController(
            lambda _session: new_terminal,
            lambda _session, selected: (
                new_pane if selected is new_terminal else target
            ),
            replace_terminal,
        )

        with (
            patch("termia.split_panes.Gtk.Paned", FakePaned),
            patch("termia.split_panes.GLib.idle_add") as idle_add,
        ):
            controller.split_terminal(
                SimpleNamespace(),
                FakeTerminal(),
                "down",
                preserve_ancestor_positions=False,
            )

        self.assertEqual(outer.position, 37)
        idle_add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
