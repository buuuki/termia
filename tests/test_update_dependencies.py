import json
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

from termia.update_controller import CheckResult, UpdateController
from termia.update_dependencies import (
    DependencyPlan,
    Requirement,
    dependency_plan,
    install_dependencies,
    parse_requirements,
    runtime_missing,
    source_requirements,
)
from termia.update_installers import DebianInstaller, GitInstaller, Installation
from termia.update_service import Release, UpdateError, Version


class DependencyPlanTests(unittest.TestCase):
    def test_source_uses_runtime_paragraph_and_version_constraints(self):
        text = '''Source: termia
Build-Depends: unrelated-build-tool

Package: termia
Depends: ${misc:Depends}, ${python3:Depends},
 python3 (>= 3.10), gir1.2-gtksource-5
'''
        self.assertEqual(source_requirements(text),
                         ((Requirement("python3", ">=", "3.10"),),
                          (Requirement("gir1.2-gtksource-5"),)))

    def test_invalid_or_ambiguous_requirements_fail_closed(self):
        for value in ("", "--remove", "bad-", "pkg;whoami", "pkg $(id)",
                      "pkg (= /tmp/file)", "pkg [amd64]", "${unknown:Depends}",
                      "pkg," , ",".join(["pkg"] * 129)):
            with self.subTest(value=value), self.assertRaises(UpdateError):
                parse_requirements(value)
        with self.assertRaises(UpdateError):
            source_requirements("Package: other\nDepends: python3")
        with self.assertRaises(UpdateError):
            source_requirements("Package: termia\nDepends: pkg\n\nPackage: termia\nDepends: pkg")

    @patch("termia.update_dependencies.Path.is_file", return_value=True)
    def test_new_already_installed_and_missing_requirements_are_distinct(self, _exists):
        before = parse_requirements("python3 (>= 3.10)")
        after = parse_requirements("python3 (>= 3.10), gir1.2-gtksource-5")
        def run(args, cancel, **kwargs):
            if args[0].endswith("dpkg-query"):
                if args[-1] == "gir1.2-gtksource-5":
                    raise UpdateError("update_install_failed")
                return "installed\t3.12"
            if args[0].endswith("dpkg"):
                return ""
            return json.dumps(["gir1.2-gtksource-5"])
        plan = dependency_plan(after, before, run, Event())
        self.assertEqual(plan.added, ("gir1.2-gtksource-5",))
        self.assertEqual(plan.packages, ("gir1.2-gtksource-5",))
        self.assertEqual(plan.manual_commands,
                         "sudo apt update\nsudo apt install --no-remove gir1.2-gtksource-5")
        ready = dependency_plan(after, before, lambda args, *a: "installed\t5.0" if
                                args[0].endswith("dpkg-query") else "[]", Event())
        self.assertEqual(ready.added, plan.added)
        self.assertFalse(ready.missing)
        self.assertFalse(ready.manual_commands)

    @patch("termia.update_dependencies.Path.is_file", return_value=True)
    def test_alternative_installed_satisfies_group(self, _exists):
        required = parse_requirements("first | second")
        def run(args, *_):
            if args[-1] == "first":
                raise UpdateError("update_install_failed")
            return "installed\t1.0"
        self.assertFalse(dependency_plan(required, (), run, Event()).missing)

    def test_runtime_probe_is_fresh_isolated_and_does_not_import_target(self):
        run = Mock(return_value='["gir1.2-gtksource-5"]')
        failed = runtime_missing(("gir1.2-gtksource-5",), run, Event())
        self.assertEqual(failed, ("gir1.2-gtksource-5",))
        self.assertEqual(run.call_args.args[0][1:3], ["-I", "-c"])
        run.return_value = '["unexpected-package"]'
        with self.assertRaisesRegex(UpdateError, "update_dependency_check_failed"):
            runtime_missing(("gir1.2-gtksource-5",), run, Event())

    def test_assisted_only_uses_native_apt_with_no_removals(self):
        plan = DependencyPlan((), (), ("pkg",), ("pkg",), "", True)
        run = Mock()
        install_dependencies(plan, run)
        calls = [c.args[0] for c in run.call_args_list]
        self.assertEqual(calls[0], ["/usr/bin/pkexec", "--disable-internal-agent", "/usr/bin/apt-get", "update"])
        self.assertIn("--no-remove", calls[1])
        self.assertEqual(calls[1][-2:], ["install", "pkg"])
        run.side_effect = UpdateError("update_install_failed")
        with self.assertRaisesRegex(UpdateError, "update_dependencies_install_failed"):
            install_dependencies(plan, run)

    def test_missing_platform_and_cancel_never_report_ready(self):
        with patch("termia.update_dependencies.Path.is_file", return_value=False), self.assertRaisesRegex(
                UpdateError, "update_dependency_platform"):
            dependency_plan(parse_requirements("pkg"), (), Mock(), Event())
        cancel = Event()
        cancel.set()
        with patch("termia.update_dependencies.Path.is_file", return_value=True), self.assertRaisesRegex(
                UpdateError, "update_cancelled"):
            dependency_plan(parse_requirements("pkg"), (), Mock(), cancel)


class UpdateTransactionTests(unittest.TestCase):
    def setUp(self):
        self.missing = DependencyPlan(((Requirement("pkg"),),), ("pkg",), ("pkg",),
                                      ("pkg",), "sudo apt install pkg", True)
        self.ready = DependencyPlan(self.missing.required, ("pkg",), (), (), "", True)
        self.adapter = Mock(kind="update_source")
        self.adapter.prepare.side_effect = lambda release, path, cancel: path
        self.adapter.dependencies.return_value = self.missing
        self.result = CheckResult(Release("v0.6.1-beta", Version.parse("0.6.1-beta"), None),
                                  Installation(self.adapter, ""))
        self.events = []
        self.controller = UpdateController("0.6.0-beta.4", lambda f: f(),
                                           lambda *args: self.events.append(args))
        self.addCleanup(self.controller.close)

    def finish(self):
        self.controller.thread.join(5)
        self.assertFalse(self.controller.thread.is_alive())

    def prepare(self):
        self.assertTrue(self.controller.prepare_update(self.result))
        self.finish()
        self.assertIsNotNone(self.controller.prepared)
        return self.controller.prepared

    def test_prepare_and_manual_missing_dependencies_never_apply(self):
        plan = self.prepare()
        self.adapter.apply.assert_not_called()
        self.controller.install(plan, assisted=False)
        self.finish()
        self.adapter.apply.assert_not_called()
        self.adapter.install_dependencies.assert_not_called()
        self.assertIsNotNone(self.controller.prepared)
        self.assertTrue(Path(plan.artifact).exists())
        self.adapter.dependencies.return_value = self.ready
        self.controller.install(self.controller.prepared, assisted=False)
        self.finish()
        self.adapter.apply.assert_called_once()
        self.assertFalse(Path(plan.artifact).exists())

    def test_assisted_install_rechecks_before_applying_source(self):
        plan = self.prepare()
        self.adapter.dependencies.side_effect = [self.missing, self.ready]
        self.controller.install(plan, assisted=True)
        self.finish()
        self.adapter.install_dependencies.assert_called_once_with(self.missing)
        self.adapter.apply.assert_called_once()

    def test_assisted_failure_leaves_source_unchanged(self):
        plan = self.prepare()
        self.adapter.install_dependencies.side_effect = UpdateError("update_dependencies_install_failed")
        self.controller.install(plan, assisted=True)
        self.finish()
        self.adapter.apply.assert_not_called()
        self.assertIn(("error", "update_dependencies_install_failed"), self.events)

    def test_post_install_missing_runtime_blocks_source_update(self):
        plan = self.prepare()
        self.controller.install(plan, assisted=True)
        self.finish()
        self.adapter.apply.assert_not_called()
        self.assertIn(("error", "update_dependencies_not_ready"), self.events)

    def test_plan_changes_require_new_confirmation(self):
        plan = self.prepare()
        self.adapter.dependencies.return_value = DependencyPlan(
            self.ready.required, (), ("other",), ("other",), "", True)
        self.controller.install(plan, assisted=True)
        self.finish()
        self.adapter.install_dependencies.assert_not_called()
        self.adapter.apply.assert_not_called()
        self.assertIn(("error", "update_plan_expired"), self.events)

    def test_close_during_manual_wait_cleans_staged_artifact(self):
        plan = self.prepare()
        self.controller.close()
        self.assertFalse(Path(plan.artifact).exists())
        self.adapter.apply.assert_not_called()

    def test_debian_uses_package_transaction_and_verifies_outcome(self):
        self.adapter.kind = "update_debian"
        plan = self.prepare()
        self.adapter.dependencies.side_effect = [self.missing, self.ready]
        self.controller.install(plan, assisted=True)
        self.finish()
        self.adapter.install_dependencies.assert_not_called()
        self.adapter.apply.assert_called_once()
        self.adapter.verify_installed.assert_called_once()

    def test_debian_verification_failure_does_not_report_success(self):
        self.adapter.kind = "update_debian"
        plan = self.prepare()
        self.adapter.verify_installed.side_effect = UpdateError("update_install_failed")
        self.controller.install(plan, assisted=True)
        self.finish()
        self.assertIn(("error", "update_verification_failed_after_apply"), self.events)

    def test_source_recovery_rechecks_dependencies_before_applying(self):
        self.result = CheckResult(self.result.release, self.result.installation, True)
        self.adapter.prepare_recovery.return_value = "synthetic-head"
        prepared = self.prepare()
        self.adapter.prepare.assert_not_called()
        self.adapter.prepare_recovery.assert_called_once()
        self.controller.install(prepared, assisted=False)
        self.finish()
        self.adapter.apply.assert_not_called()
        self.adapter.dependencies.side_effect = [self.missing, self.ready]
        self.controller.install(self.controller.prepared, assisted=True)
        self.finish()
        self.adapter.install_dependencies.assert_called_once()
        self.adapter.apply.assert_called_once_with("synthetic-head", self.result.release)


class AdapterDependencyTests(unittest.TestCase):
    def test_git_metadata_is_read_from_prepared_commit_not_worktree(self):
        adapter = GitInstaller(Path("/synthetic"), "0.6.0-beta.4")
        adapter.original_head = "old"
        adapter.availability = Mock(return_value="")
        adapter.git = Mock(side_effect=["old", "Package: termia\nDepends: pkg", "Package: termia\nDepends: oldpkg"])
        with patch("termia.update_installers.dependency_plan", return_value="plan") as planner:
            self.assertEqual(adapter.dependencies("target", Event()), "plan")
        self.assertEqual(adapter.git.call_args_list[1].args, ("show", "target:debian/control"))
        self.assertEqual(planner.call_args.args[0], ((Requirement("pkg"),),))

    def test_debian_verifies_actual_installed_version(self):
        run = Mock(return_value="installed\t0.6.1~beta-1")
        adapter = DebianInstaller(Mock(), run)
        adapter.target_version = "0.6.1~beta-1"
        adapter.verify_installed()
        run.return_value = "installed\t0.6.0~beta.4-1"
        with self.assertRaisesRegex(UpdateError, "update_verification_failed_after_apply"):
            adapter.verify_installed()

    def test_debian_dependency_fields_include_predepends(self):
        run = Mock(side_effect=["basepkg", "newpkg (>= 2)", "basepkg", "oldpkg"])
        adapter = DebianInstaller(Mock(), run)
        with patch("termia.update_installers.dependency_plan", return_value="plan") as planner:
            self.assertEqual(adapter.dependencies("synthetic.deb", Event()), "plan")
        self.assertEqual(planner.call_args.args[0],
                         ((Requirement("basepkg"),), (Requirement("newpkg", ">=", "2"),)))

    def test_git_recovery_rejects_dirty_or_unrelated_checkout(self):
        release = Release("v0.6.1-beta", Version.parse("0.6.1-beta"), None)
        for branch, status, head, target, expected in (
            ("main", "", "target", "target", True),
            ("HEAD", "", "target", "target", True),
            ("feature", "", "target", "target", False),
            ("main", " M synthetic.py", "target", "target", False),
            ("main", "", "other", "target", False),
        ):
            with self.subTest(branch=branch, status=status, head=head):
                adapter = GitInstaller(Path("/synthetic"), "0.6.0-beta.4")
                adapter.git = Mock(side_effect=lambda *args, branch=branch, status=status,
                                          head=head, target=target, **kwargs: (
                    branch if args[:2] == ("rev-parse", "--abbrev-ref") else
                    status if args[0] == "status" else
                    head if args == ("rev-parse", "HEAD") else target))
                self.assertEqual(adapter.recovery_available(release, Event()), expected)

    def test_source_recovery_does_not_bypass_development_restriction(self):
        adapter = GitInstaller(Path("/synthetic"), "0.6.1-dev")
        adapter.git = Mock()
        release = Release("v0.6.1-beta", Version.parse("0.6.1-beta"), None)
        self.assertFalse(adapter.recovery_available(release, Event()))
        adapter.git.assert_not_called()
