import unittest

from termia.statistics_view import StatisticsDialog


class StatisticsDialogTests(unittest.TestCase):
    def test_accepts_only_explicit_view_dependencies(self) -> None:
        parent = object()
        presenter = object()
        translate = lambda key: key

        dialog = StatisticsDialog(parent, presenter, translate)

        self.assertIs(dialog.parent, parent)
        self.assertIs(dialog.presenter, presenter)
        self.assertIs(dialog.translate, translate)
