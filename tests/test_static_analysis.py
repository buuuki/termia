import asyncio
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_static_analysis as analysis


class StaticAnalysisTests(unittest.TestCase):
    def test_fingerprint_ignores_indentation_but_preserves_literal_contents(self):
        def key(code):
            return analysis.fingerprint("a.py", "F821", "undefined", "unrated", code)

        self.assertEqual(key("print(missing)"), key("    print(missing)"))
        self.assertNotEqual(key('print("a b")'), key('print("a  b")'))

    def test_comparison_preserves_duplicate_counts_and_file_identity(self):
        item = {"key": ("a.py", "F821"), "file": "a.py", "line": 1, "rule": "F821"}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(analysis.report_difference("ruff", [item], [item]), 0)
            self.assertEqual(analysis.report_difference("ruff", [item], [item, item]), 1)
            self.assertEqual(analysis.report_difference("ruff", [item], []), 0)
            renamed = {**item, "key": ("b.py", "F821"), "file": "b.py"}
            self.assertEqual(analysis.report_difference("ruff", [item], [renamed]), 1)

    def test_invalid_evidence_and_tool_failures_cannot_pass(self):
        for status, output in ((2, b"[]"), (0, b"invalid"), (1, b"[]"), (0, b"{}")):
            with self.subTest(status=status, output=output), self.assertRaises(analysis.AnalysisError):
                analysis.parse_report("ruff", status, output, Path.cwd())
        with self.assertRaises(analysis.AnalysisError):
            analysis.parse_report("bandit", 0, b'{"errors": ["failed"], "results": []}', Path.cwd())
        with patch.object(analysis.shutil, "which", return_value=None), self.assertRaises(analysis.AnalysisError):
            asyncio.run(analysis.command(["ruff"], Path.cwd()))

    def test_report_paths_and_syntax_errors_are_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.py").write_text("print(missing)\n")
            finding = {"filename": "a.py", "code": "F821", "message": "Undefined name",
                       "location": {"row": 1}, "end_location": {"row": 1}}
            parsed = analysis.parse_report("ruff", 1, json.dumps([finding]).encode(), root)
            self.assertEqual(parsed[0]["file"], "a.py")
            for changed in ({"filename": "../outside.py"}, {"code": "invalid-syntax"},
                            {"location": {"row": 99}}):
                with self.subTest(changed=changed), self.assertRaises(analysis.AnalysisError):
                    analysis.parse_report("ruff", 1, json.dumps([{**finding, **changed}]).encode(), root)

    @unittest.skipUnless(shutil.which("bandit"), "Bandit not installed")
    def test_bandit_dictionary_entries_ignore_siblings_but_detect_changes(self):
        original = (
            "MESSAGES = {\n"
            "    'password_label': (\n"
            "        'Synthetic prompt'\n"
            "    ),\n"
            "    'unrelated': 'Before',\n"
            "}\n"
        )
        cases = [
            ("unrelated value", original.replace("'Before'", "'After'"), 0),
            ("line shift", "\n\n" + original, 0),
            ("new sibling", original.replace(
                "}\n", "    'another': 'New entry',\n}\n"
            ), 0),
            ("changed key", original.replace(
                "'password_label'", "'password_caption'"
            ), 1),
            ("changed value", original.replace(
                "'Synthetic prompt'", "'Changed synthetic prompt'"
            ), 1),
            ("duplicate", original.replace(
                "}\n", "    'password_label': 'Synthetic prompt',\n}\n"
            ), 1),
        ]

        async def exercise(root):
            path = root / "messages.py"
            path.write_text(original, encoding="utf-8")
            baseline = await analysis.analyze("bandit", root)
            self.assertEqual(len(baseline), 1)
            for name, source, expected in cases:
                with self.subTest(case=name):
                    path.write_text(source, encoding="utf-8")
                    proposed = await analysis.analyze("bandit", root)
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(
                            analysis.report_difference(
                                "bandit", baseline, proposed
                            ),
                            expected,
                        )

            # AST columns count UTF-8 bytes, including preceding Unicode.
            path.write_text(
                "MESSAGES = {'é': 'Before', "
                "'password_label': 'Synthetic prompt'}\n",
                encoding="utf-8",
            )
            baseline = await analysis.analyze("bandit", root)
            self.assertEqual(len(baseline), 1)
            path.write_text(
                "MESSAGES = {'é': 'After', "
                "'password_label': 'Synthetic prompt'}\n",
                encoding="utf-8",
            )
            proposed = await analysis.analyze("bandit", root)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    analysis.report_difference("bandit", baseline, proposed), 0
                )

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(exercise(Path(temporary)))

    def test_snapshot_rejects_unsafe_destinations(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name in ("../escape.py", "/absolute.py"):
                with self.subTest(name=name), self.assertRaises(analysis.AnalysisError):
                    analysis.destination(Path(temporary), name)

    def test_missing_duplicate_or_unpinned_dependencies_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "requirements.txt"
            for content in ("", "ruff>=0.17.2\nbandit==1.9.4", "ruff==0.17.2\nruff==0.17.2",
                            "ruff==0.17.2\nbandit==1.9.4\nother==1.0.0"):
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(analysis.AnalysisError):
                    analysis.read_pins(path)
            path.write_text("ruff==0.17.2\nbandit==1.9.4\n")
            self.assertEqual(analysis.read_pins(path), {"ruff": "0.17.2", "bandit": "1.9.4"})
            with patch.object(analysis, "git", return_value=str(path.parent).encode()), \
                 patch.object(analysis, "command", return_value=(0, b"")), \
                 self.assertRaises(analysis.AnalysisError):
                asyncio.run(analysis.check("HEAD", "WORKTREE"))

    def test_ancestry_errors_cannot_select_a_quality_baseline(self):
        with patch.object(analysis, "command", return_value=(128, b"")), self.assertRaises(analysis.AnalysisError):
            asyncio.run(analysis.is_ancestor(Path("."), "a", "b"))

    @unittest.skipUnless(shutil.which("ruff") and shutil.which("bandit"), "Analyzers unavailable")
    def test_initial_adoption_requires_approved_history_and_blocks_reintroduced_debt(self):
        async def exercise(root):
            await analysis.git(root, "init", "-q")
            source = root / "a.py"

            async def commit(text):
                source.write_text(text)
                await analysis.git(root, "add", "a.py")
                await analysis.git(
                    root, "-c", "user.name=Synthetic", "-c", "user.email=ci@example.invalid",
                    "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                    "commit", "-qm", "synthetic quality history",
                )
                return (await analysis.git(root, "rev-parse", "HEAD")).decode().strip()

            base = await commit("print('before')\n")
            adoption = await commit("print(missing)\n")
            approved = await commit("print('approved')\n")
            head = await commit("print(missing)\n")
            with patch.object(analysis, "QUALITY_ADOPTION_COMMIT", adoption), \
                 patch.object(analysis, "APPROVED_RELEASE_BASELINE", approved), \
                 patch.object(analysis.Path, "cwd", return_value=root):
                self.assertEqual(await analysis.comparison_base(root, approved, head), approved)
                self.assertEqual(await analysis.comparison_base(root, base, base), base)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(await analysis.comparison_base(root, base, head), approved)
                self.assertIn(base, output.getvalue())
                self.assertIn(approved, output.getvalue())
                with self.assertRaises(analysis.AnalysisError):
                    await analysis.comparison_base(root, base, adoption)
                with patch.object(analysis, "QUALITY_ADOPTION_COMMIT", "0" * 40), self.assertRaises(analysis.AnalysisError):
                    await analysis.comparison_base(root, base, head)
                with contextlib.redirect_stdout(io.StringIO()):
                    # A warning fixed after adoption must not regain an old allowance.
                    self.assertEqual(await analysis.check(base, head), 1)
                    clean = await commit("print('clean')\n")
                    self.assertEqual(await analysis.check(base, clean), 0)
                await analysis.git(root, "checkout", "-q", "--detach", base)
                unrelated = await commit("print('other lineage')\n")
                with self.assertRaises(analysis.AnalysisError):
                    await analysis.comparison_base(root, unrelated, head)

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(exercise(Path(temporary)))

    def test_timed_out_child_is_stopped(self):
        with self.assertRaises(asyncio.TimeoutError):
            asyncio.run(analysis.command(
                [sys.executable, "-c", "import time; time.sleep(10)"], Path.cwd(), timeout=0.02,
            ))

    @unittest.skipUnless(shutil.which("ruff") and shutil.which("bandit"), "Pinned analyzers not installed")
    def test_real_scanners_and_git_snapshots_gate_changes_without_running_sources(self):
        async def exercise(root):
            await analysis.git(root, "init", "-q")
            source = root / "a.py"
            source.write_text("print(missing)\n")
            await analysis.git(root, "add", "a.py")
            await analysis.git(root, "-c", "user.name=Synthetic", "-c", "user.email=ci@example.invalid",
                               "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                               "commit", "-qm", "synthetic baseline")
            with patch.object(analysis.Path, "cwd", return_value=root):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(await analysis.check("HEAD", "HEAD"), 0)
                    self.assertEqual(await analysis.check("HEAD", "WORKTREE"), 0)
                    source.write_text("\n\nprint(missing)\n")
                    self.assertEqual(await analysis.check("HEAD", "WORKTREE"), 0)
                    source.write_text("print(missing)\nprint(missing)  # noqa\n")
                    (root / "ruff.toml").write_text('lint.ignore = ["F821"]\n')
                    self.assertEqual(await analysis.check("HEAD", "WORKTREE"), 1)
                    source.unlink()
                    self.assertEqual(await analysis.check("HEAD", "WORKTREE"), 0)
                    # New untracked source is scanned; no code is imported/executed.
                    (root / "unsafe.py").write_text("import pickle\npickle.loads(b'fixture')  # nosec\n")
                    self.assertEqual(await analysis.check("HEAD", "WORKTREE"), 1)
                    (root / "unsafe.py").unlink()
                    (root / "alias.py").symlink_to("a.py")
                    with self.assertRaises(analysis.AnalysisError):
                        await analysis.check("HEAD", "WORKTREE")
                with self.assertRaises(analysis.AnalysisError):
                    await analysis.check("0" * 40, "WORKTREE")

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(exercise(Path(temporary)))
