"""Manage only the persistent Ubuntu 24 GNOME project for this checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent
REPO = LAB.parents[2]
RUNTIME = LAB.parent / '.runtime' / 'gnome24'
PROJECT = 'termia-459-gnome24'
LABEL = 'local.termia.checkout'
IDENTITY = hashlib.sha256(str(REPO).encode()).hexdigest()
SOURCE_ROOTS = ('src/termia', 'tests', 'scripts', 'tools/docker-lab',
                'docs', 'po', 'debian', '.github')
SOURCE_FILES = ('run_termia.py', 'LICENSE', 'requirements-ci.txt',
                'requirements-coverage.txt', '.coveragerc', 'README.md',
                'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md',
                'ROADMAP.md', 'pyproject.toml')
SUFFIXES = {'.py', '.mo', '.svg', '.png', '.xml', '.sh', '.md', '.txt',
            '.po', '.pot', '.json', '.yaml', '.yml', '.toml', '.conf',
            '.service', '.target', '.sources', '.desktop', '.remmina', '.seccomp'}
SPECIAL_NAMES = {'Dockerfile', 'Dockerfile.server', 'Dockerfile.client',
                 'Dockerfile.updater', '.dockerignore', '.gitignore',
                 'control', 'changelog', 'rules', 'format'}
RECIPE_FILES = ('Dockerfile', '.dockerignore', 'configure.py', 'panel.py',
                'termia-lab-prepare.service', 'org.termia.Lab24.desktop')


def run(arguments, **kwargs):
    executable = shutil.which(arguments[0])
    if executable is None:
        raise RuntimeError('Required laboratory executable unavailable')
    return subprocess.run([str(Path(executable).resolve()), *arguments[1:]],
                          check=True, text=True, **kwargs)


def docker_executable():
    return str(Path(shutil.which('docker') or '/usr/bin/docker').resolve())


def validate_relative(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Invalid snapshot path')
    return path


def copy_regular(source: Path, relative: str, target: Path) -> str:
    path = validate_relative(relative)
    original = source / path
    if original.is_symlink() or original.resolve() != source.resolve() / path:
        raise ValueError('Snapshot symlinks are not allowed')
    if not original.is_file():
        raise ValueError('Snapshot input must be a regular file')
    data = original.read_bytes()
    destination = target / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    destination.chmod(0o755 if original.stat().st_mode & 0o111 else 0o644)
    return hashlib.sha256(data).hexdigest()


def snapshot(repo: Path, target: Path) -> dict:
    target.mkdir()
    result = run(['git', '-C', str(repo), 'ls-files', '-z', '--',
                  *SOURCE_FILES, *SOURCE_ROOTS], capture_output=True)
    hashes = {}
    for name in filter(None, result.stdout.split('\0')):
        path = validate_relative(name)
        if name not in SOURCE_FILES and path.suffix not in SUFFIXES and path.name not in SPECIAL_NAMES:
            continue
        if not (repo / path).exists():
            # Tracked local deletions are part of the snapshot.
            continue
        hashes[name] = copy_regular(repo, name, target)
    if 'run_termia.py' not in hashes or 'src/termia/app.py' not in hashes:
        raise ValueError('Incomplete Termia source snapshot')
    commit = run(['git', '-C', str(repo), 'rev-parse', 'HEAD'],
                 capture_output=True).stdout.strip()
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    metadata = {'base_commit': commit, 'source_sha256': digest, 'files': hashes}
    (target / 'SNAPSHOT.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


def context(target: Path) -> dict:
    """Create a fresh allowlisted build context; never reuse stale files."""
    target.mkdir()
    for name in RECIPE_FILES:
        copy_regular(LAB, name, target)
    infra = target / 'infra'
    infra.mkdir()
    copy_regular(LAB.parent / 'gnome26', 'init.sh', infra)
    copy_regular(LAB.parent / 'gnome26', 'rendering.conf', infra)
    return snapshot(REPO, target / 'source')


def require_local_engine():
    # Docker gives DOCKER_CONTEXT precedence over DOCKER_HOST. Validate the
    # endpoint that subsequent commands will actually use.
    selected_context = os.environ.get('DOCKER_CONTEXT')
    endpoint = None if selected_context else os.environ.get('DOCKER_HOST')
    if selected_context or not endpoint:
        endpoint = run(['docker', 'context', 'inspect', '--format',
                        '{{.Endpoints.docker.Host}}',
                        *([selected_context] if selected_context else [])],
                       capture_output=True).stdout.strip()
    if not endpoint.startswith('unix://'):
        raise RuntimeError('This laboratory requires a local Unix Docker socket')


def verify_ownership():
    # Check both the expected resource names and retained project volumes.
    for kind, names in (
        ('container', (PROJECT + '-desktop-1',)),
        ('volume', tuple(PROJECT + '_' + name for name in
                         ('profile', 'credentials', 'remote-state'))),
    ):
        for name in names:
            result = subprocess.run([docker_executable(), kind, 'inspect', name],
                                    text=True, capture_output=True, check=False)
            if result.returncode:
                # Distinguish missing resources from daemon/permission errors.
                message = result.stderr.lower()
                if 'no such' in message or 'not found' in message:
                    continue
                raise RuntimeError('Docker resource inspection failed')
            info = json.loads(result.stdout)[0]
            labels = info.get('Config', {}).get('Labels', {}) if kind == 'container' else info.get('Labels', {})
            if labels.get(LABEL) != IDENTITY:
                raise RuntimeError('Refusing to reuse a resource owned by another checkout')


def compose(*arguments, build_context: Path | None = None):
    environment = os.environ.copy()
    environment['LAB_CHECKOUT_ID'] = IDENTITY
    environment['LAB_BUILD_CONTEXT'] = str(build_context or RUNTIME / 'unused-context')
    return run(['docker', 'compose', '--project-name', PROJECT, '-f',
                str(LAB / 'compose.yaml'), *arguments], env=environment)


def start():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='build-', dir=RUNTIME) as temporary:
        build_context = Path(temporary) / 'context'
        metadata = context(build_context)
        previous = subprocess.run([docker_executable(), 'image', 'inspect',
                                   'termia-lab-459-gnome24:local', '--format', '{{.Id}}'],
                                  text=True, capture_output=True, check=False)
        if previous.returncode == 0:
            image = previous.stdout.strip()
            run(['docker', 'image', 'tag', image,
                 'termia-lab-459-gnome24:before-' + image.removeprefix('sha256:')[:12]])
        compose('build', 'desktop', build_context=build_context)
        # Recheck immediately before a potentially disruptive recreation.
        verify_ownership()
        compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '120',
                'desktop', build_context=build_context)
    installed = run(['docker', 'exec', PROJECT + '-desktop-1', '/usr/bin/python3',
                     '-c', 'import json; print(json.load(open("/opt/termia/SNAPSHOT.json"))["source_sha256"])'],
                    capture_output=True).stdout.strip()
    if installed != metadata['source_sha256']:
        raise RuntimeError('Running laboratory source does not match the prepared snapshot')
    (RUNTIME / 'snapshot.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('RDP: 127.0.0.1:12389; user: lab')
    print('Listener readiness does not validate a GNOME login or desktop.')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'resume', 'stop', 'status', 'logs', 'password'))
    action = parser.parse_args().action
    require_local_engine()
    verify_ownership()
    if action == 'start':
        start()
    elif action == 'resume':
        compose('start', 'desktop')
    elif action == 'stop':
        compose('stop', 'desktop')
    elif action == 'status':
        compose('ps', '--all')
    elif action == 'logs':
        compose('logs', '--tail', '100', 'desktop')
    elif action == 'password':
        # Deliberate local credential disclosure, never part of normal status/logs.
        run(['docker', 'exec', PROJECT + '-desktop-1', '/bin/cat',
             '/var/lib/termia-lab/password'])


if __name__ == '__main__':
    main()
