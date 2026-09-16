# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Common ownership contract for SCP controllers and SFTP explorers."""
from typing import Protocol


class ManagedTransfer(Protocol):
    owner_session_id: str | None

    def cancel_active_transfer(self, *, close_dialog: bool = False) -> None: ...
