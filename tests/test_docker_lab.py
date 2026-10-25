"""Publication boundaries: no private/generated inputs enter Docker contexts."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

LAB = Path(__file__).resolve().parents[1] / 'tools/docker-lab'
spec = importlib.util.spec_from_file_location('termia_lab_context', LAB / 'context.py')
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)
control_spec = importlib.util.spec_from_file_location('termia_lab_control', LAB / 'lab/tools.py')
control = importlib.util.module_from_spec(control_spec)
control_spec.loader.exec_module(control)
results_spec = importlib.util.spec_from_file_location('termia_lab_results', LAB / 'probes/results.py')
results = importlib.util.module_from_spec(results_spec)
results_spec.loader.exec_module(results)


class DockerLabContextTests(unittest.TestCase):
    def test_client_context_excludes_untracked_and_non_source_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, target = root / 'repo', root / 'context'
            (repo / 'src/termia').mkdir(parents=True)
            (repo / 'run_termia.py').write_text('# synthetic launcher\n')
            (repo / 'src/termia/app.py').write_text('# synthetic module\n')
            (repo / 'src/termia/private.key').write_text('synthetic excluded sentinel')
            (repo / 'src/termia/untracked.py').write_text('synthetic excluded sentinel')
            (repo / 'personal-profile.json').write_text('synthetic excluded sentinel')
            files = b'run_termia.py\0src/termia/app.py\0src/termia/private.key\0'
            with patch.object(context.subprocess, 'check_output', side_effect=[files, 'a' * 40]):
                context.prepare_context(repo, LAB, target)
            self.assertTrue((target / 'source/src/termia/app.py').is_file())
            self.assertEqual((target / 'source/src/termia').stat().st_mode & 0o777, 0o755)
            self.assertEqual((target / 'source/src/termia/app.py').stat().st_mode & 0o777, 0o644)
            self.assertEqual((target / 'source/BASE_COMMIT').read_text(), 'a' * 40 + '\n')
            self.assertFalse(list(target.rglob('*.key')))
            self.assertFalse(list(target.rglob('untracked.py')))
            self.assertFalse(list(target.rglob('personal-profile.json')))
            self.assertFalse(any('excluded sentinel' in p.read_text(errors='ignore')
                                 for p in target.rglob('*') if p.is_file()))

    def test_server_context_contains_only_scripts_never_generated_authentication(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'context'
            context.prepare_context(Path(temporary), LAB, target, server=True)
            self.assertEqual({p.name for p in target.iterdir()}, set(context.SERVER_FILES))
            dockerfile = (target / 'Dockerfile.server').read_text()
            self.assertNotIn('COPY synthetic', dockerfile)
            self.assertNotIn('chpasswd', dockerfile)

    def test_stale_destination_is_rejected_without_reusing_its_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'context'
            target.mkdir()
            sentinel = target / 'private-sentinel'
            sentinel.write_text('synthetic')
            with self.assertRaises(FileExistsError):
                context.prepare_context(Path(temporary), LAB, target, server=True)
            self.assertEqual(sentinel.read_text(), 'synthetic')

    def test_tracked_symlink_cannot_exfiltrate_an_external_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'repo'
            (repo / 'src/termia').mkdir(parents=True)
            outside = root / 'outside.py'
            outside.write_text('synthetic excluded sentinel')
            (repo / 'src/termia/app.py').symlink_to(outside)
            with patch.object(context.subprocess, 'check_output', return_value=b'src/termia/app.py\0'):
                with self.assertRaisesRegex(RuntimeError, 'symlink'):
                    context.prepare_context(repo, LAB, root / 'context')

    def test_checked_in_package_has_no_runtime_credentials_or_local_archive(self):
        paths = [p.relative_to(LAB) for p in LAB.rglob('*') if p.is_file()
                 and '.runtime' not in p.parts and '__pycache__' not in p.parts]
        self.assertFalse(any(p.suffix in {'.pem', '.pub', '.key', '.gz', '.log'} for p in paths))
        self.assertFalse(any(p.name in {'synthetic', 'password', 'connections.json', 'settings.json'}
                             for p in paths))

    def test_foreign_container_and_network_are_rejected_before_mutation(self):
        for kind in ('container', 'network'):
            with self.subTest(kind=kind), patch.object(control, 'capture', return_value='[{"Labels":{}}]'):
                with self.assertRaisesRegex(RuntimeError, 'recurso ajeno'):
                    control.owned('synthetic-foreign-resource', kind)

    def test_diagnostic_network_and_mounts_are_isolated(self):
        ordinary = control.client_command('/tmp/synthetic-evidence', 'smoke-x11')
        self.assertEqual(ordinary[ordinary.index('--network') + 1], 'none')
        ssh = control.client_command('/tmp/synthetic-evidence', 'ssh-smoke')
        self.assertEqual(ssh[ssh.index('--network') + 1], control.NETWORK)
        self.assertNotEqual(control.NETWORK, control.MANUAL_NETWORK)
        for command in (ordinary, ssh):
            self.assertIn('--read-only', command)
            self.assertIn('no-new-privileges', command)
            self.assertFalse(any('docker.sock' in item or 'SSH_AUTH_SOCK=' in item for item in command))


class DockerLabResultTests(unittest.TestCase):
    def test_worker_cleanup_outcome_is_persisted_and_controls_wait(self):
        for fails in (False, True):
            with self.subTest(cleanup_fails=fails), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                manifest_path = directory / 'manifest.json'
                manifest_path.write_text(json.dumps(dict(
                    state='starting', source_sha256='synthetic-source',
                )))
                process = Mock(returncode=0)
                process.poll.return_value = 0
                failure = RuntimeError('synthetic cleanup failure') if fails else None
                with (
                    patch.object(control, 'fingerprint', return_value='synthetic-source'),
                    patch.object(control, 'exists', side_effect=[False, True]),
                    patch.object(control, 'owned', return_value={}),
                    patch.object(control, 'client_command', return_value=['synthetic-command']),
                    patch.object(control.subprocess, 'Popen', return_value=process),
                    patch.object(control, 'docker', side_effect=failure) as docker,
                    redirect_stdout(io.StringIO()),
                ):
                    control.worker('diagnostic', directory, 'menus')
                docker.assert_called_once_with('stop', '-t', '10', control.CLIENT)
                manifest = json.loads(manifest_path.read_text())
                self.assertEqual(manifest['state'], 'failed' if fails else 'completed')
                self.assertEqual(manifest['exit_code'], 0)
                self.assertEqual(bool(manifest.get('cleanup_error')), fails)
                with patch.object(control, 'job', return_value=dict(directory=str(directory))), \
                        redirect_stdout(io.StringIO()):
                    if fails:
                        with self.assertRaisesRegex(RuntimeError, 'did not complete successfully'):
                            control.wait_for_diagnostic()
                    else:
                        control.wait_for_diagnostic()

    def test_wait_rejects_legacy_completed_manifest_with_cleanup_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'manifest.json').write_text(json.dumps(dict(
                state='completed', cleanup_error='synthetic cleanup failure',
            )))
            with patch.object(control, 'job', return_value=dict(directory=str(directory))), \
                    redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'did not complete successfully'):
                    control.wait_for_diagnostic()

    def test_visual_cleanup_fails_for_survivors_and_preserves_workload_failure(self):
        for completed in (False, True):
            for window_closed, children in ((True, 0), (True, 1), (False, 0)):
                with self.subTest(completed=completed, closed=window_closed, children=children):
                    result = dict(completed=completed)
                    results.record_cleanup(result, window_closed=window_closed,
                                           running_children=children)
                    self.assertEqual(result['completed'], completed and window_closed and children == 0)
                    self.assertEqual(result['cleanup'], dict(
                        window_closed=window_closed, running_children=children,
                    ))


if __name__ == '__main__':
    unittest.main()
