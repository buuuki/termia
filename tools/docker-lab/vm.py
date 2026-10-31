"""Checkout-owned KVM desktop. No host profile, SSH, or Docker socket in guests."""
import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[1]
RUNTIME = ROOT / '.runtime/visible-vm'
FILES = ROOT / 'vm'
PREFIX = 'termia-lab-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
NAME = PREFIX + '-visible-vm'
IMAGE = PREFIX + '-vm:local'
LABEL = 'local.termia.tools'
STAGES = ('source-cancel', 'source-accept', 'debian-prepare',
          'debian-cancel', 'debian-accept', 'verify')
BASE_URL = 'https://cloud-images.ubuntu.com/noble/current/'
BASE_FILE = 'noble-server-cloudimg-amd64.img'
OLD_URL = ('https://github.com/buuuki/termia/releases/download/v0.6.0-beta.3/'
           'termia_0.6.0.beta.3-1_all.deb')
OLD_HASH = 'b0b1382abb505ab09f004a6b555f39b8b142c95a7d4dbe01052784f1151b0691'


def run(*args, capture=False):
    try:
        return subprocess.run(list(map(str, args)), check=True, text=True,
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.PIPE if capture else None).stdout
    except subprocess.CalledProcessError as error:
        raise RuntimeError(error.stderr or str(error)) from error


def docker(*args, capture=False):
    return run('docker', *args, capture=capture)


def inspect_owned():
    data = json.loads(docker('inspect', NAME, capture=True))[0]
    if data.get('Config', {}).get('Labels', {}).get(LABEL) != str(ROOT):
        raise RuntimeError('Refusing to operate on a foreign container')
    return data


def download(url, target, expected):
    temporary = target.with_suffix('.partial')
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
        while block := response.read(1024 * 1024):
            output.write(block)
            digest.update(block)
    if digest.hexdigest() != expected:
        raise RuntimeError('Download checksum mismatch: ' + target.name)
    temporary.replace(target)


def export_source(destination):
    """Export named tracked regular files only, including uncommitted proposals."""
    names = run('git', '-C', SOURCE, 'ls-files', '-z', '--', 'run_termia.py',
                'LICENSE', 'README.md', 'scripts/termia-setup.sh', 'src/termia',
                'debian', 'pyproject.toml', capture=True).split('\0')
    allowed = {'.py', '.mo', '.svg', '.png', '.xml'}
    for name in filter(None, names):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Invalid source path')
        if name.startswith('src/termia/') and relative.suffix not in allowed:
            continue
        original = SOURCE / relative
        if original.is_symlink() or original.resolve() != SOURCE.resolve() / relative:
            raise RuntimeError('Source input traverses a symlink')
        if not original.is_file():
            raise RuntimeError('Source input is not a regular file')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        target.chmod(0o755 if name in {'debian/rules', 'scripts/termia-setup.sh'} else 0o644)


def helper(*args):
    inspect_owned()
    return docker('exec', NAME, 'python3', '/vm/control.py', *args, capture=True)


def guest(*args):
    return helper('guest', *args)


def user_command(code):
    return guest('/usr/sbin/runuser', '-u', 'lab', '--', 'python3', '-c', code)


def prepare():
    if (RUNTIME / 'manifest.json').exists():
        raise RuntimeError('Runtime already prepared; retain it or archive it before a fresh preparation')
    if not Path('/dev/kvm').exists():
        raise RuntimeError('Linux /dev/kvm is required')
    for name in ('Dockerfile', 'boot.sh', 'bootstrap.sh', 'control.py', 'panel.py', 'worker.py', 'seed.py'):
        path = FILES / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('VM tool input must be a regular file')
    # The Docker context contains exactly its recipe; runtime and checkout stay out.
    context = RUNTIME / 'build-context'
    context.mkdir()
    shutil.copyfile(FILES / 'Dockerfile', context / 'Dockerfile')
    docker('build', '-t', IMAGE, context)
    checksums = urllib.request.urlopen(BASE_URL + 'SHA256SUMS', timeout=60).read().decode()
    match = re.search(r'^([0-9a-f]{64})\s+\*?' + re.escape(BASE_FILE) + r'$', checksums, re.MULTILINE)
    if match is None:
        raise RuntimeError('Official Ubuntu image checksum not found')
    download(BASE_URL + BASE_FILE, RUNTIME / 'ubuntu-base.img', match[1])
    fixtures = RUNTIME / 'fixtures'
    fixtures.mkdir(exist_ok=True)
    download(OLD_URL, fixtures / 'termia-beta3-official.deb', OLD_HASH)
    source = RUNTIME / 'build/source'
    source.mkdir(parents=True)
    export_source(source)
    version_file = source / 'src/termia/__init__.py'
    version_text = version_file.read_text()
    version_text, count = re.subn(r'(?m)^__version__\s*=.*$', '__version__ = "0.6.0-beta.4"', version_text)
    if count != 1:
        raise RuntimeError('Cannot identify candidate version')
    version_file.write_text(version_text)
    changelog = source / 'debian/changelog'
    changelog.write_text('termia (0.6.0~beta.4-1) unstable; urgency=medium\n\n'
                        '  * Synthetic local laboratory candidate; not a release.\n\n'
                        ' -- Laboratory <lab@example.invalid>  Thu, 22 Oct 2026 00:00:00 +0000\n\n'
                        + changelog.read_text())
    docker('run', '--rm', '--network', 'none', '--cap-drop', 'ALL',
           '--security-opt', 'no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
           '--mount', f'type=bind,src={RUNTIME / "build"},dst=/build', '-w', '/build/source',
           '-e', 'HOME=/tmp', '-e', 'DEB_BUILD_OPTIONS=nocheck', IMAGE,
           'dpkg-buildpackage', '-us', '-uc', '-b')
    package = RUNTIME / 'build/termia_0.6.0~beta.4-1_all.deb'
    candidate = fixtures / 'termia-beta4-candidate.deb'
    shutil.copyfile(package, candidate)
    metadata = {'tag': 'v0.6.0-beta.4', 'filename': package.name,
                'sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
                'size': candidate.stat().st_size}
    (fixtures / 'candidate.json').write_text(json.dumps(metadata))
    with tarfile.open(fixtures / 'candidate-source.tar.gz', 'w:gz') as archive:
        for path in sorted(source.rglob('*')):
            relative = path.relative_to(source)
            if path.is_file() and not path.is_symlink() and (
                str(relative) in {'run_termia.py', 'LICENSE', 'README.md', 'scripts/termia-setup.sh'}
                or relative.parts[0] == 'src' and path.suffix in {'.py', '.mo', '.svg', '.png', '.xml'}
            ) and '__pycache__' not in relative.parts:
                archive.add(path, arcname=str(relative), recursive=False)
    for name in ('panel.py', 'worker.py', 'seed.py'):
        shutil.copyfile(FILES / name, fixtures / name)
    (fixtures / 'password').write_text(secrets.token_urlsafe(18) + '\n')
    for path in fixtures.iterdir():
        path.chmod(0o644)
    shutil.copyfile(FILES / 'control.py', RUNTIME / 'control.py')
    shutil.copyfile(FILES / 'boot.sh', RUNTIME / 'boot.sh')
    config = {
        'hostname': 'termia-visible-lab', 'disable_root': True, 'ssh_pwauth': False,
        'users': [{'name': 'lab', 'gecos': 'Synthetic laboratory user', 'groups': ['sudo'],
                   'sudo': ['ALL=(ALL:ALL) ALL'], 'shell': '/bin/bash', 'lock_passwd': False}],
        'write_files': [
            {'path': '/usr/local/sbin/termia-lab-bootstrap', 'permissions': '0755',
             'content': (FILES / 'bootstrap.sh').read_text()},
            {'path': '/etc/lightdm/lightdm.conf.d/50-termia-lab.conf', 'permissions': '0644',
             'content': '[Seat:*]\nautologin-user=lab\nautologin-session=xfce\nuser-session=xfce\n'}],
        'runcmd': [['bash', '/usr/local/sbin/termia-lab-bootstrap']],
    }
    (RUNTIME / 'user-data').write_text('#cloud-config\n' + json.dumps(config))
    (RUNTIME / 'meta-data').write_text('instance-id: termia-visible-lab\n')
    docker('run', '--rm', '--user', f'{os.getuid()}:{os.getgid()}',
           '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
           '--mount', f'type=bind,src={RUNTIME},dst=/vm', IMAGE, 'bash', '-ec',
           'cd /vm; cloud-localds seed.iso user-data meta-data; '
           'genisoimage -quiet -o fixtures.iso -V TERMIA_FIXTURES -J -r fixtures; '
           'qemu-img create -f qcow2 -F qcow2 -b /vm/ubuntu-base.img system.qcow2 18G')
    manifest = {'state': 'prepared', 'initial_test_state': 'paused', 'ubuntu_sha256': match[1],
                'baseline_sha256': OLD_HASH, 'candidate': metadata,
                'source_commit': run('git', '-C', SOURCE, 'rev-parse', 'HEAD', capture=True).strip(),
                'source_sha256': hashlib.sha256((fixtures / 'candidate-source.tar.gz').read_bytes()).hexdigest()}
    (RUNTIME / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Prepared. No trials executed. Runtime: ' + str(RUNTIME))


def start(port):
    if not (RUNTIME / 'manifest.json').exists():
        raise RuntimeError('Run prepare first')
    if not 1 <= port <= 65535:
        raise ValueError('Port must be between 1 and 65535')
    docker('run', '-d', '--init', '--name', NAME, '--label', f'{LABEL}={ROOT}',
           '--user', f'{os.getuid()}:{os.getgid()}',
           '--group-add', str(Path('/dev/kvm').stat().st_gid), '--device', '/dev/kvm',
           '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--read-only',
           '--tmpfs', '/tmp:rw,nosuid,size=256m', '--memory', '3g', '--cpus', '2',
           '--pids-limit', '256', '-p', f'127.0.0.1:{port}:6080',
           '--mount', f'type=bind,src={RUNTIME},dst=/vm', IMAGE, 'bash', '/vm/boot.sh')
    print(f'http://127.0.0.1:{port}/vnc.html?autoconnect=1&resize=scale')
    print('Guest initialization downloads packages; inspect status until the desktop appears.')
    print('Trials remain paused. After opening the viewer, run ready.')


def status():
    info = inspect_owned()
    print(json.dumps({'container': NAME, 'running': info['State']['Running'],
                      'runtime': str(RUNTIME)}, indent=2))
    if info['State']['Running']:
        print(helper('qmp', 'query-kvm'))
        try:
            progress = guest('/bin/bash', '-c',
                             'if test -f /var/lib/termia-lab-ready; then echo DESKTOP_READY; '
                             'else tail -15 /var/log/termia-lab-bootstrap.log; fi')
        except RuntimeError:
            print('Guest agent not ready; latest serial output:')
            serial = RUNTIME / 'serial.log'
            if serial.exists():
                print('\n'.join(serial.read_text(errors='replace').splitlines()[-15:]))
            return
        print(progress)
        print(guest('/bin/bash', '-c', 'cat /home/lab/termia-lab-evidence/state.json 2>/dev/null || true'))


def evidence():
    guest('/usr/bin/tar', '-czf', '/tmp/visible-results.tar.gz', '-C', '/home/lab', 'termia-lab-evidence')
    encoded = guest('/usr/bin/base64', '-w0', '/tmp/visible-results.tar.gz').rsplit('Guest exit:', 1)[0].strip()
    output = RUNTIME / 'results'
    output.mkdir(exist_ok=True)
    (output / 'visible-results.tar.gz').write_bytes(base64.b64decode(encoded, validate=True))
    print(helper('qmp', 'screendump', json.dumps({'filename': '/vm/results/desktop.png', 'format': 'png'})))
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'start', 'status', 'ready', 'trial',
                                          'show', 'evidence', 'stop', 'remove', 'guest'))
    parser.add_argument('arguments', nargs='*')
    parser.add_argument('--port', type=int, default=6081)
    args = parser.parse_args()
    os.umask(0o077)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare': prepare()
        elif args.action == 'start': start(args.port)
        elif args.action == 'status': status()
        elif args.action == 'ready':
            print(user_command('from pathlib import Path; (Path.home()/"termia-lab-evidence/observer-ready").touch()'))
        elif args.action in ('trial', 'show'):
            action = args.arguments[0] if args.action == 'trial' and args.arguments else 'show'
            if args.action == 'trial' and action not in STAGES:
                parser.error('trial requires one of: ' + ', '.join(STAGES))
            print(user_command('from pathlib import Path; import json; '
                               '(Path.home()/"termia-lab-evidence/command.json").write_text('
                               + repr(json.dumps({'action': action})) + ')'))
        elif args.action == 'evidence': evidence()
        elif args.action == 'guest':
            if not args.arguments: parser.error('guest requires an executable and arguments')
            print(guest(*args.arguments))
        else:
            info = inspect_owned()
            if args.action == 'remove' and info['State']['Running']:
                raise RuntimeError('Stop the VM before removing its container')
            docker('stop', '--time', '30', NAME) if args.action == 'stop' else docker('rm', NAME)
            print('Runtime disks and evidence retained at ' + str(RUNTIME))


if __name__ == '__main__':
    main()
