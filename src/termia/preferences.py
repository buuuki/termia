# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from .general_preferences import GeneralPreferencesMixin
from .keybinding_preferences import KeybindingCaptureRow, KeybindingPreferencesMixin
from .prompt_preferences import PromptPreferencesMixin
from .security_preferences import SecurityPreferencesMixin
from .terminal_preferences import TerminalPreferencesMixin


class PreferencesMixin(
    GeneralPreferencesMixin,
    TerminalPreferencesMixin,
    PromptPreferencesMixin,
    SecurityPreferencesMixin,
    KeybindingPreferencesMixin,
):
    pass
