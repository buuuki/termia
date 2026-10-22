"""Allowlisted, fresh Docker contexts; never send the checkout as build input."""
from pathlib import Path
import shutil
import subprocess

LAB_FILES = (
    'lab/boot.sh', 'lab/desktop.py', 'lab/launcher.py', 'lab/sample_process.py',
    'lab/seed_profile.py', 'lab/lifecycle/entry.py', 'lab/lifecycle/probe.py',
    'lab/lifecycle/memory_probe.py', 'probes/probe.py', 'probes/results.py',
)
SERVER_FILES = ('Dockerfile.server', 'observe.py', 'remote_job.py', 'server_entry.py')


def copy_regular(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f'Build input must be a regular file: {source.name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o644)


def prepare_context(repo: Path, lab: Path, target: Path, *, server=False) -> None:
    """Require a new destination; stale files can never enter a later build."""
    target.mkdir(mode=0o700)
    if server:
        for name in SERVER_FILES:
            copy_regular(lab / 'lab/lifecycle' / name, target / name)
        return
    copy_regular(lab / 'Dockerfile', target / 'Dockerfile')
    copy_regular(lab / '.dockerignore', target / '.dockerignore')
    for name in LAB_FILES:
        copy_regular(lab / name, target / name)
    files = subprocess.check_output(
        ['git', '-C', str(repo), 'ls-files', '-z', '--', 'run_termia.py', 'LICENSE', 'src/termia'],
    ).decode().split('\0')
    allowed = {'.py', '.mo', '.svg', '.png', '.xml'}
    for name in filter(None, files):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Invalid tracked source path')
        if name not in {'run_termia.py', 'LICENSE'} and relative.suffix not in allowed:
            continue
        # Reject symlinked directories as well as symlinked leaf inputs.
        if (repo / relative).resolve() != repo.resolve() / relative:
            raise RuntimeError('Build input traverses a symlink')
        copy_regular(repo / relative, target / 'source' / relative)
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    (target / 'source/BASE_COMMIT').write_text(commit + '\n')
    (target / 'source/BASE_COMMIT').chmod(0o644)
    # Context root stays private on the host; copied image paths must be
    # readable by the numeric, unprivileged runtime UID on any other PC.
    for path in target.rglob('*'):
        if path.is_dir():
            path.chmod(0o755)
