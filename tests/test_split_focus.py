import unittest

from termia.split_panes import directional_pane_neighbor


class SplitFocusGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = {
            1: (0, 0, 100, 100),
            2: (100, 0, 100, 100),
            3: (0, 100, 100, 100),
            4: (100, 100, 100, 100),
        }

    def test_moves_in_each_direction_across_a_grid(self) -> None:
        self.assertEqual(directional_pane_neighbor(1, "right", self.grid), 2)
        self.assertEqual(directional_pane_neighbor(1, "down", self.grid), 3)
        self.assertEqual(directional_pane_neighbor(4, "left", self.grid), 3)
        self.assertEqual(directional_pane_neighbor(4, "up", self.grid), 2)

    def test_absent_neighbor_keeps_focus(self) -> None:
        self.assertIsNone(directional_pane_neighbor(1, "left", self.grid))
        self.assertIsNone(directional_pane_neighbor(1, "up", self.grid))

    def test_prefers_overlapping_pane_in_requested_axis(self) -> None:
        rectangles = {
            1: (0, 0, 100, 100),
            2: (120, 10, 100, 80),
            3: (105, 130, 100, 100),
        }

        self.assertEqual(directional_pane_neighbor(1, "right", rectangles), 2)

    def test_handles_nested_unequal_pane_sizes(self) -> None:
        rectangles = {
            1: (0, 0, 160, 200),
            2: (160, 0, 140, 80),
            3: (160, 80, 140, 120),
        }

        self.assertEqual(directional_pane_neighbor(1, "right", rectangles), 3)
        self.assertEqual(directional_pane_neighbor(2, "down", rectangles), 3)

    def test_rejects_unknown_source_and_direction(self) -> None:
        self.assertIsNone(directional_pane_neighbor(99, "right", self.grid))
        self.assertIsNone(directional_pane_neighbor(1, "diagonal", self.grid))
