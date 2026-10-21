"""Intervención diagnóstica explícita; no cambia la sonda normal."""
import unittest
from unittest.mock import patch

import probe
from termia.split_panes import SplitPaneController
from gi.repository import Vte

original_focus = Vte.Terminal.grab_focus
original_split = SplitPaneController.split_terminal


def mapped_focus(terminal):
    return original_focus(terminal) if terminal.get_mapped() else False


def split_with_mapped_focus(self, *args, **kwargs):
    with patch.object(Vte.Terminal, 'grab_focus', mapped_focus):
        return original_split(self, *args, **kwargs)


print('DIAGNOSTIC: only split creation skips focus for unmapped VTE', flush=True)
with patch.object(SplitPaneController, 'split_terminal', split_with_mapped_focus):
    unittest.main(module=probe)
