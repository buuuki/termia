"""Safety boundaries for the persistent Ubuntu 24 GNOME laboratory."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

LAB = Path(__file__).resolve().parents[1] / 'tools/docker-lab/gnome24'
spec = importlib.util.spec_from_file_location('gnome24_lab', LAB / 'lab.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
credential_spec = importlib.util.spec_from_file_location('gnome24_credentials', LAB / 'configure.py')
credentials = importlib.util.module_from_spec(credential_spec)
credential_spec.loader.exec_module(credentials)

class Gnome24LabTests(unittest.TestCase):

    def test_snapshot_preserves_local_bytes_and_excludes_private_or_untracked_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'repo'
            (repo / 'src/termia').mkdir(parents=True)
            (repo / 'run_termia.py').write_text('# local source\n')
            (repo / 'src/termia/app.py').write_text('# changed source\n')
            (repo / 'src/termia/private.key').write_text('synthetic excluded sentinel')
            (repo / 'src/termia/untracked.py').write_text('synthetic excluded sentinel')
            (repo / 'scripts').mkdir()
            script = repo / 'scripts/compile_translations.py'
            script.write_text('#!/usr/bin/python3\n')
            script.chmod(493)
            files = 'run_termia.py\x00src/termia/app.py\x00src/termia/private.key\x00scripts/compile_translations.py\x00'
            responses = [SimpleNamespace(stdout=files), SimpleNamespace(stdout='a' * 40)]
            target = root / 'source'
            with patch.object(lab, 'run', side_effect=responses):
                metadata = lab.snapshot(repo, target)
            self.assertEqual((target / 'src/termia/app.py').read_text(), '# changed source\n')
            self.assertEqual((target / 'scripts/compile_translations.py').stat().st_mode & 511, 493)
            self.assertFalse((target / 'src/termia/private.key').exists())
            self.assertFalse((target / 'src/termia/untracked.py').exists())
            self.assertEqual(metadata['base_commit'], 'a' * 40)
            self.assertEqual(len(metadata['source_sha256']), 64)

    def test_source_path_traversal_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'outside.py').write_text('# synthetic\n')
            repo = root / 'repo'
            repo.mkdir()
            (repo / 'link.py').symlink_to(root / 'outside.py')
            for path in ('../outside.py', '/outside.py', 'link.py'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    lab.copy_regular(repo, path, root / 'output')

    def test_remote_daemon_is_rejected_before_any_compose_action(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'ssh://synthetic-host', 'DOCKER_CONTEXT': ''}), self.assertRaises(RuntimeError):
            lab.require_local_engine()

    def test_selected_remote_context_overrides_a_local_docker_host(self):
        environment = {'DOCKER_HOST': 'unix:///synthetic.sock', 'DOCKER_CONTEXT': 'synthetic-remote'}
        result = SimpleNamespace(stdout='ssh://synthetic-host\n')
        with patch.dict(os.environ, environment), patch.object(lab, 'run', return_value=result) as run:
            with self.assertRaises(RuntimeError):
                lab.require_local_engine()
            self.assertEqual(run.call_args.args[0][-1], 'synthetic-remote')

    def test_foreign_persistent_resources_are_not_reused(self):
        value = SimpleNamespace(returncode=0, stdout=json.dumps([{'Config': {'Labels': {}}}]))
        with patch.object(lab.subprocess, 'run', return_value=value), self.assertRaises(RuntimeError):
            lab.verify_ownership()

    def test_daemon_errors_are_not_treated_as_missing_resources(self):
        value = SimpleNamespace(returncode=1, stderr='permission denied')
        with patch.object(lab.subprocess, 'run', return_value=value), self.assertRaises(RuntimeError):
            lab.verify_ownership()

    def test_failed_preparation_does_not_build_or_recreate_the_desktop(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(lab, 'RUNTIME', Path(temporary)), patch.object(lab, 'context', side_effect=ValueError('synthetic rejection')), patch.object(lab, 'compose') as compose:
            with self.assertRaises(ValueError):
                lab.start()
            compose.assert_not_called()

    def test_failed_build_does_not_recreate_the_desktop(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(lab, 'RUNTIME', Path(temporary)), patch.object(lab, 'context', return_value={}), patch.object(lab.subprocess, 'run', return_value=SimpleNamespace(returncode=1)), patch.object(lab, 'compose', side_effect=RuntimeError('synthetic build failure')) as compose:
            with self.assertRaises(RuntimeError):
                lab.start()
            self.assertEqual(compose.call_count, 1)
            self.assertEqual(compose.call_args.args[:2], ('build', 'desktop'))

    def test_credentials_persist_and_reject_links_and_invalid_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            password = root / 'password'
            first = credentials.load_password(password)
            self.assertEqual(first, credentials.load_password(password))
            self.assertEqual(password.stat().st_mode & 511, 384)
            (root / 'link').symlink_to(password)
            with self.assertRaises(OSError):
                credentials.load_password(root / 'link')
            password.write_text('invalid:synthetic')
            with self.assertRaises(ValueError):
                credentials.load_password(password)

    def test_configuration_failure_does_not_expose_credential_arguments(self):
        with patch.object(credentials.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(RuntimeError) as error:
                credentials.command(['synthetic-command', 'synthetic-secret'])
            self.assertNotIn('synthetic-secret', str(error.exception))
