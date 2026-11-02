import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "termia-setup.sh"


class SetupScriptTests(unittest.TestCase):
    def run_setup_functions(self, body):
        return subprocess.run(
            ["bash", "-c", 'source "$1" --help >/dev/null\n' + body,
             "termia-setup-regression", str(SCRIPT)],
            capture_output=True, text=True, timeout=10,
        )

    def test_missing_required_dependency_propagates_failure_inside_condition(self):
        for missing, expected in (
            ("python", ["python", "blocked"]),
            ("ssh", ["python", "ssh", "blocked"]),
            ("sshpass", ["python", "ssh", "sshpass", "blocked"]),
        ):
            with self.subTest(missing=missing):
                result = self.run_setup_functions('''
missing="''' + missing + '''"
check_python_modules() { echo python; test "$missing" != python; }
check_command() { echo "$1"; test "$missing" != "$1"; }
check_terminal_font() { echo font; }
if run_checks; then echo unexpected-success; else echo blocked; fi
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), expected)

    def test_available_dependencies_do_not_invoke_installer(self):
        result = self.run_setup_functions('''
check_python_modules() { return 0; }
check_command() { return 0; }
check_terminal_font() { return 0; }
install_packages() { echo unexpected-install; return 17; }
ensure_dependencies
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dependencies are already available", result.stdout)
        self.assertNotIn("unexpected-install", result.stdout)

    def test_missing_dependency_triggers_installation_and_is_checked_again(self):
        result = self.run_setup_functions('''
checks=0
check_python_modules() { checks=$((checks + 1)); test "$checks" -gt 1; }
check_command() { return 0; }
check_terminal_font() { return 0; }
install_packages() { echo installed; }
ensure_dependencies
echo "checks:$checks"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Installing the required packages", result.stdout)
        self.assertIn("installed", result.stdout.splitlines())
        self.assertIn("checks:2", result.stdout.splitlines())
        self.assertNotIn("dependencies are already available", result.stdout)

    def test_package_manager_failure_prevents_launcher_and_success_message(self):
        result = self.run_setup_functions('''
confirm_install() { return 0; }
check_python_modules() { return 1; }
check_command() { return 0; }
check_terminal_font() { return 0; }
install_packages() { return 19; }
install_desktop_launcher() { echo unexpected-launcher; }
install
''')
        self.assertEqual(result.returncode, 19, result.stderr)
        self.assertNotIn("unexpected-launcher", result.stdout)
        self.assertNotIn("completed successfully", result.stdout)

    def test_failed_post_install_check_prevents_false_success(self):
        result = self.run_setup_functions('''
confirm_install() { return 0; }
check_python_modules() { return 1; }
check_command() { return 0; }
check_terminal_font() { return 0; }
install_packages() { echo installed; }
install_desktop_launcher() { echo unexpected-launcher; }
install
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("installed", result.stdout.splitlines())
        self.assertNotIn("unexpected-launcher", result.stdout)
        self.assertNotIn("completed successfully", result.stdout)
