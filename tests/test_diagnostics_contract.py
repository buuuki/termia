# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class DiagnosticsContractTests(unittest.TestCase):
    def test_context_combines_windows_and_filters_retired_panes(self):
        from termia.app import TermiaApp

        class MainWindow:
            pass

        def process(pid):
            return SimpleNamespace(pid=pid, start_time=str(pid), session_members=())

        def window(panes, orphans=()):
            result = MainWindow()
            result.session_registry = SimpleNamespace(sessions=lambda: [SimpleNamespace(panes=panes)])
            result.orphaned_terminal_processes = orphans
            return result

        shell = SimpleNamespace(retired=False, server_id=None, connected=True, child_process=process(10))
        ssh = SimpleNamespace(retired=False, server_id="synthetic", connected=True, child_process=process(11))
        offline = SimpleNamespace(retired=False, server_id="synthetic", connected=False, child_process=None)
        app = SimpleNamespace(get_windows=lambda: [
            window({1: shell, 2: SimpleNamespace(retired=True)}),
            window({1: ssh, 2: offline}, [process(12)]), object()])
        with patch("termia.app.TermiaWindow", MainWindow):
            context = TermiaApp.diagnostic_context(app)
        self.assertEqual((context.sessions, context.terminals, context.ssh_clients, context.local_terminals),
                         (2, 3, 1, 1))
        self.assertEqual([(p.pid, p.kind, p.possible_orphan) for p in context.processes],
                         [(10, "shell", False), (11, "ssh", False), (12, "child", True)])


    def test_host_keeps_legacy_context_alias_and_returns_fresh_snapshots(self):
        from termia.app import TermiaApp
        from termia.diagnostics_contract import DiagnosticContext

        with patch("termia.app.PluginRuntime") as runtime_factory:
            app = TermiaApp()
        capabilities = runtime_factory.call_args.args[2]
        self.assertIs(capabilities["context"], capabilities["diagnostics_context"])
        with patch.object(app, "diagnostic_context", return_value=DiagnosticContext(sessions=2)):
            legacy = capabilities["context"]()
            legacy["sessions"] = 99
            current = capabilities["diagnostics_context"]()
        self.assertEqual(current["sessions"], 2)
        self.assertIsNot(legacy, current)
