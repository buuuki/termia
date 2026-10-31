"""Prepare an allowlisted, ignored build context for the draft updater preview."""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from threading import Event

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTEXT = HERE.parent / '.runtime/upgrade-preview/context'
ASSETS = [
    ('v0.6.0-beta.3', 'termia_0.6.0.beta.3-1_all.deb', 'beta3.deb',
     'b0b1382abb505ab09f004a6b555f39b8b142c95a7d4dbe01052784f1151b0691'),
    ('v0.6.0-beta.4', 'termia_0.6.0.beta.4-1_all.deb', 'termia_0.6.0.beta.4-1_all.deb',
     'a8f1582fd70eb12510b29522fe164b23e38c0f69850e63a0908de6844fa995b3'),
]

MAX_ASSET_BYTES = 10 * 1024 * 1024


def download_package(url, digest, client):
    data = client.read(url, Event(), MAX_ASSET_BYTES)
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('Official package checksum mismatch')
    return data


def main():
    # Use this checkout's HTTPS/redirect policy without importing GTK.
    sys.path.insert(0, str(ROOT / 'src'))
    from termia.update_service import ReleaseClient

    client = ReleaseClient()
    CONTEXT.mkdir(parents=True, exist_ok=False)
    fixtures = CONTEXT / 'fixtures'
    fixtures.mkdir()
    for tag, name, local, digest in ASSETS:
        url = f'https://github.com/buuuki/termia/releases/download/{tag}/{name}'
        (fixtures / local).write_bytes(download_package(url, digest, client))
    subprocess.run(['/usr/bin/git', '-C', str(ROOT), 'bundle', 'create', str(fixtures / 'releases.bundle'),
                    'refs/tags/v0.6.0-beta.3', 'refs/tags/v0.6.0-beta.4'], check=True)
    names = subprocess.check_output(['/usr/bin/git', '-C', str(ROOT), 'ls-files', '-z', '--', 'src/termia']).decode().split('\0')
    for name in filter(None, names):
        relative = Path(name)
        source = ROOT / relative
        if relative.is_absolute() or '..' in relative.parts or source.is_symlink():
            raise RuntimeError('Invalid source input')
        if not source.is_file() or source.suffix not in {'.py', '.mo', '.svg', '.png', '.xml'}:
            continue
        target = CONTEXT / 'review' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for name in ('Dockerfile', 'boot.sh', 'desktop.sh', 'panel.py', 'launch.py', 'reset.py'):
        shutil.copyfile(HERE / name, CONTEXT / name)
    print('Prepared:', CONTEXT)
    print('Build and run with the commands in tools/docker-lab/upgrade-preview/README.md')


if __name__ == '__main__':
    main()
