"""Safety boundaries for the optional observable VM laboratory."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

LAB = Path(__file__).resolve().parents[1] / 'tools/docker-lab'
spec = importlib.util.spec_from_file_location('termia_visible_lab', LAB / 'vm.py')
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)


class VisibleLabTests(unittest.TestCase):
    def test_setup_failure_is_neither_successful_installation_nor_cancellation(self):
        with tempfile.TemporaryDirectory() as temporary:
            spec = importlib.util.spec_from_file_location('termia_vm_worker', LAB / 'vm/worker.py')
            worker = importlib.util.module_from_spec(spec)
            with patch.object(Path, 'home', return_value=Path(temporary)):
                spec.loader.exec_module(worker)
            for stage in ('source-cancel', 'source-accept'):
                with self.subTest(stage=stage), \
                        patch.object(worker, 'version', return_value=worker.OLD), \
                        patch.object(worker, 'profile_hashes', return_value={}), \
                        patch.object(worker, 'write_state'), patch('builtins.print'), \
                        patch.object(worker.subprocess, 'run', side_effect=[
                            SimpleNamespace(returncode=0),  # sudo invalidation
                            SimpleNamespace(returncode=1),  # setup failure
                            SimpleNamespace(returncode=1 if stage == 'source-cancel' else 0),
                        ]):
                    with self.assertRaises(AssertionError):
                        worker.run(stage)

    def test_foreign_container_rejected_before_guest_command(self):
        with patch.object(vm, 'docker', return_value='[{"Config":{"Labels":{}}}]') as docker:
            with self.assertRaisesRegex(RuntimeError, 'foreign'):
                vm.guest('/bin/true')
        self.assertEqual(docker.call_count, 1)
        self.assertEqual(docker.call_args.args[0], 'inspect')

    def test_source_export_excludes_untracked_data_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'repo'
            (source / 'src/termia').mkdir(parents=True)
            (source / 'src/termia/app.py').write_text('# synthetic source')
            (source / 'src/termia/private.key').write_text('excluded synthetic sentinel')
            (source / 'src/termia/untracked.py').write_text('excluded synthetic sentinel')
            names = 'src/termia/app.py\0src/termia/private.key\0'
            with patch.object(vm, 'SOURCE', source), patch.object(vm, 'run', return_value=names):
                vm.export_source(root / 'export')
                self.assertEqual([str(p.relative_to(root / 'export')) for p in
                                  (root / 'export').rglob('*') if p.is_file()], ['src/termia/app.py'])
                (source / 'src/termia/app.py').unlink()
                (source / 'src/termia/app.py').symlink_to(source / 'src/termia/private.key')
                with self.assertRaisesRegex(RuntimeError, 'symlink'):
                    vm.export_source(root / 'rejected')

    def test_failed_checksum_does_not_replace_verified_download(self):
        import io
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'image'
            target.write_bytes(b'previous verified synthetic image')
            with patch.object(vm.urllib.request, 'urlopen', return_value=io.BytesIO(b'corrupt')):
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    vm.download('https://example.invalid/image', target, '0' * 64)
            self.assertEqual(target.read_bytes(), b'previous verified synthetic image')

    def test_start_exposes_only_loopback_and_kvm_without_host_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'manifest.json').write_text('{}')
            with patch.object(vm, 'RUNTIME', root), patch.object(vm.Path, 'stat') as stat, \
                    patch.object(vm, 'docker') as docker, patch('builtins.print'):
                stat.return_value.st_gid = 109
                vm.start(6082)
            args = docker.call_args.args
            self.assertEqual(args[args.index('-p') + 1], '127.0.0.1:6082:6080')
            self.assertIn('--read-only', args)
            self.assertIn('no-new-privileges', args)
            self.assertEqual(args[args.index('--device') + 1], '/dev/kvm')
            self.assertFalse(any('docker.sock' in str(x) or 'SSH_AUTH_SOCK' in str(x) for x in args))
            self.assertEqual(sum(x == '--mount' for x in args), 1)

    def test_prepare_refuses_existing_manifest_before_any_docker_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'manifest.json').write_text(json.dumps({'state': 'prepared'}))
            with patch.object(vm, 'RUNTIME', root), patch.object(vm, 'docker') as docker:
                with self.assertRaisesRegex(RuntimeError, 'already prepared'):
                    vm.prepare()
            docker.assert_not_called()


if __name__ == '__main__':
    unittest.main()
