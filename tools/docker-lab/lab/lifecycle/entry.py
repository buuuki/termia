"""Run synthetic lifecycle workloads on the visual laboratory source."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def fingerprint():
    root = Path('/opt/termia')
    digest = hashlib.sha256()
    files = [root / 'run_termia.py', *sorted(
        p for p in (root / 'src/termia').rglob('*')
        if p.is_file() and p.suffix in ('.py', '.mo')
    )]
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('lifecycle', 'memory', 'memory-trace', 'close-live', 'valgrind', 'ssh-smoke'))
    args = parser.parse_args()
    initial = fingerprint()
    root = Path(__file__).resolve().parent
    if args.mode in ('memory', 'memory-trace', 'close-live'):
        cycles = os.environ.get('LAB_MEMORY_CYCLES', '20')
        if not cycles.isdigit() or not 1 <= int(cycles) <= 1000:
            raise ValueError('LAB_MEMORY_CYCLES must be between 1 and 1000')
        command = [sys.executable, str(root / 'memory_probe.py'), '--runs', '1', '--cycles', cycles]
        if args.mode != 'memory-trace':
            command.append('--no-tracemalloc')
        if args.mode == 'close-live':
            command.append('--close-live')
    else:
        command = [sys.executable, str(root / 'probe.py')]
        if args.mode == 'ssh-smoke':
            command.append('DockerLifecycleTests.test_authentication_smoke')
        if args.mode == 'valgrind':
            command = ['valgrind', '--tool=memcheck', '--num-callers=30',
                       '--leak-check=full', '--show-leak-kinds=definite',
                       '--log-file=/evidence/valgrind-%p.log', *command]
    output = Path('/evidence/result.json')
    result = {'mode': args.mode, 'source_sha256': initial, 'completed': False}
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='', flush=True)
            if line.startswith('MEMORY_RESULT '):
                result['memory'] = json.loads(line.removeprefix('MEMORY_RESULT '))
        result['exit_code'] = process.wait()
        result['source_unchanged'] = fingerprint() == initial
        result['completed'] = result['exit_code'] == 0 and result['source_unchanged']
        result['memory_leak_free'] = None
        return 0 if result['completed'] else 1
    finally:
        output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
