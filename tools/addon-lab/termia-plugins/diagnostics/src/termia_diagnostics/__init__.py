# SPDX-License-Identifier: GPL-3.0-or-later
API_VERSION = 2


def create(*, context, attach_window, apply_style):
    from .diagnostics import DiagnosticContext, ManagedProcess
    from .diagnostics_view import DiagnosticsTool

    def snapshot():
        data = context()
        return DiagnosticContext(
            sessions=data["sessions"],
            terminals=data["terminals"],
            ssh_clients=data["ssh_clients"],
            local_terminals=data["local_terminals"],
            processes=tuple(ManagedProcess(**item) for item in data["processes"]),
        )

    return DiagnosticsTool(attach_window, snapshot, apply_style)
