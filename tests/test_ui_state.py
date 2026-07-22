import unittest
from dataclasses import is_dataclass

from gi.repository import GObject
from termia.ui_state import RowObject


class RowObjectTests(unittest.TestCase):
    def test_row_object_is_plain_value_state(self) -> None:
        row = RowObject("server", "server-1", "Web", "admin@example.test:22")

        self.assertEqual(row.kind, "server")
        self.assertEqual(row.item_id, "server-1")
        self.assertEqual(row.title, "Web")
        self.assertEqual(row.subtitle, "admin@example.test:22")
        self.assertEqual(row, RowObject("server", "server-1", "Web", "admin@example.test:22"))
        self.assertTrue(is_dataclass(row))
        self.assertFalse(isinstance(row, GObject.Object))
