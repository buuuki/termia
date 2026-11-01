import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_test_instance.sh"


class TestInstanceLauncherTests(unittest.TestCase):
    def test_filter_keeps_other_diagnostics_pid_and_application_exit_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "python3"
            executable.write_text('''#!/bin/bash
printf '%s\\n' '(python3:123): Gtk-DEBUG: 12:34:56.789: snapshot symbolic icon using mask'
printf '%s\\n' 'Gtk-DEBUG: snapshot symbolic icon using mask'
printf '%s\\n' 'Gtk-DEBUG: snapshot symbolic icon using color-matrix'
printf '%s\\n' 'Other-DEBUG: snapshot symbolic icon using mask'
printf '%s\\n' 'Gtk-WARNING: snapshot symbolic icon using mask'
printf '%s\\n' 'Gtk-CRITICAL: snapshot symbolic icon using mask'
printf '%s\\n' 'Gtk-ERROR: snapshot symbolic icon using mask'
printf '%s\\n' 'Termia debug event'
printf 'Application PID: %s\\n' "$$"
printf 'Debug domains: %s\\n' "$G_MESSAGES_DEBUG"
printf '%s\\n' 'Gtk-WARNING: snapshot symbolic icon using mask' >&2
printf '%s\\n' 'Traceback: synthetic failure' >&2
exit "$TEST_EXIT_STATUS"
''')
            executable.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                PATH=str(root) + os.pathsep + environment.get("PATH", ""),
                TERMIA_TEST_DATA_DIR=str(root / "profile"),
                G_MESSAGES_DEBUG="all",
            )
            for status in (0, 17):
                with self.subTest(status=status):
                    environment["TEST_EXIT_STATUS"] = str(status)
                    result = subprocess.run(
                        ["bash", str(SCRIPT)], env=environment, capture_output=True,
                        text=True, timeout=10, check=False,
                    )
                    self.assertEqual(result.returncode, status, result.stderr)
                    lines = result.stdout.splitlines()
                    self.assertNotIn(
                        '(python3:123): Gtk-DEBUG: 12:34:56.789: snapshot symbolic icon using mask',
                        lines,
                    )
                    self.assertNotIn('Gtk-DEBUG: snapshot symbolic icon using mask', lines)
                    for line in (
                        'Gtk-DEBUG: snapshot symbolic icon using color-matrix',
                        'Other-DEBUG: snapshot symbolic icon using mask',
                        'Gtk-WARNING: snapshot symbolic icon using mask',
                        'Gtk-CRITICAL: snapshot symbolic icon using mask',
                        'Gtk-ERROR: snapshot symbolic icon using mask',
                        'Termia debug event',
                        'Debug domains: all',
                    ):
                        self.assertIn(line, lines)
                    launcher_pid = next(line.removeprefix("PID: ").strip() for line in lines
                                        if line.startswith("PID: "))
                    self.assertIn("Application PID: " + launcher_pid, lines)
                    self.assertEqual(result.stderr.splitlines(), [
                        'Gtk-WARNING: snapshot symbolic icon using mask',
                        'Traceback: synthetic failure',
                    ])
