"""Local controller for isolated diagnostics and passive process observations."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from context import prepare_context

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parents[1]
EVIDENCE = ROOT / '.runtime' / 'evidence'
PREFIX = 'termia-lab-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
DESKTOP = PREFIX + '-desktop'
CLIENT = PREFIX + '-diagnostic'
SERVER = PREFIX + '-ssh'
NETWORK = PREFIX + '-internal'
MANUAL_SERVER = PREFIX + '-manual-ssh'
MANUAL_NETWORK = PREFIX + '-manual-internal'
IMAGE = PREFIX + '-client:local'
SERVER_IMAGE = PREFIX + '-server:local'
LABEL = 'local.termia.tools'
MODES = ('lifecycle', 'memory', 'memory-trace', 'close-live', 'valgrind',
         'menus', 'churn-disabled', 'churn-enabled', 'behavior-x11', 'behavior-wayland',
         'smoke-x11', 'smoke-wayland', 'ssh-smoke',
         'churn-disabled-wayland', 'churn-enabled-wayland')
SSH_MODES = MODES[:5] + ('ssh-smoke',)


def docker(*args, **kwargs):
    return subprocess.run(['docker', *map(str, args)], check=True, text=True, **kwargs)


def capture(*args):
    return docker(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def fingerprint():
    root = SOURCE
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


def birth(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()
        return fields[19] if fields[0] != 'Z' else None
    except (OSError, IndexError):
        return None


def job(kind):
    path = EVIDENCE / (kind + '.json')
    if not path.exists():
        return None
    info = json.loads(path.read_text())
    info['active'] = birth(info['pid']) == info['birth'] and info['birth'] is not None
    return info


def owned(name, object_type='container'):
    info = json.loads(capture(object_type, 'inspect', name))[0]
    labels = info.get('Config', {}).get('Labels', {}) if object_type == 'container' else info.get('Labels', {})
    if labels.get(LABEL) != str(ROOT):
        raise RuntimeError(f'{name}: recurso ajeno a esta copia del laboratorio')
    return info


def exists(name, object_type='container'):
    return subprocess.run(['docker', object_type, 'inspect', name],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def prepare():
    active = job('diagnostic')
    if active and active['active']:
        raise RuntimeError('Espera a que termine el ensayo antes de reconstruir las herramientas.')
    infra = EVIDENCE / 'infrastructure'
    infra.mkdir(parents=True, exist_ok=True)
    key = infra / 'synthetic'
    if not key.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                        '-C', 'termia-laboratory-generated', '-f', str(key)], check=True)
    password = infra / 'password'
    if not password.exists():
        password.write_text(secrets.token_urlsafe(24) + '\n')
        password.chmod(0o600)
    build_images()
    print('Herramientas preparadas; no se ha ejecutado ningún ensayo.', flush=True)


def build_images():
    runtime = ROOT / '.runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    for server, image in ((False, IMAGE), (True, SERVER_IMAGE)):
        with tempfile.TemporaryDirectory(prefix='build-', dir=runtime) as temporary:
            context = Path(temporary) / 'context'
            prepare_context(SOURCE, ROOT, context, server=server)
            build_args = [] if server else ['--build-arg', f'LAB_UID={os.getuid()}']
            docker('build', *build_args, '-f', context / ('Dockerfile.server' if server else 'Dockerfile'),
                   '-t', image, context)


def fixture_mounts():
    infra = EVIDENCE / 'infrastructure'
    return ['--mount', f'type=bind,src={infra / "synthetic.pub"},dst=/opt/fixture/authorized_keys,readonly',
            '--mount', f'type=bind,src={infra / "password"},dst=/opt/fixture/password,readonly']


def start(kind, mode=None):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with (EVIDENCE / (kind + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = job(kind)
        if previous and previous['active']:
            raise RuntimeError(f'Ya hay una tarea activa: {previous["directory"]}')
        if kind == 'diagnostic':
            capture('image', 'inspect', IMAGE)
            if mode in SSH_MODES:
                capture('image', 'inspect', SERVER_IMAGE)
                if not (EVIDENCE / 'infrastructure/synthetic').exists():
                    raise RuntimeError('Primero prepara las herramientas.')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        directory = EVIDENCE / f'{stamp}-{mode or kind}'
        directory.mkdir()
        write_json(directory / 'manifest.json', dict(mode=mode or kind,
                   source_sha256=fingerprint(), source=str(SOURCE),
                   created_utc=stamp, state='starting'))
        with (directory / 'console.log').open('w') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                '_worker', kind, str(directory), mode or 'monitor'],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(EVIDENCE / (kind + '.json'), dict(pid=process.pid, birth=birth(process.pid),
                   mode=mode or kind, directory=str(directory)))
        print(f'Iniciado: {directory}')


def setup_server():
    if exists(NETWORK, 'network'):
        info = owned(NETWORK, 'network')
        if not info['Internal']:
            raise RuntimeError('La red de ensayos debe ser interna.')
    else:
        docker('network', 'create', '--internal', '--label', f'{LABEL}={ROOT}', NETWORK)
    if exists(SERVER):
        info = owned(SERVER)
        if info['State']['Running']:
            raise RuntimeError('El servidor sintético ya está ocupado.')
        docker('rm', SERVER)
    docker('run', '-d', '--init', '--name', SERVER, '--label', f'{LABEL}={ROOT}',
           '--network', NETWORK, '--pids-limit', '256', '--memory', '512m',
           *fixture_mounts(), SERVER_IMAGE)
    for _ in range(60):
        ready = subprocess.run(['docker', 'exec', SERVER, 'python3', '-c',
            'import socket; socket.create_connection(("127.0.0.1",22),.5).close()'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ready.returncode == 0:
            return
        time.sleep(.2)
    raise RuntimeError('El servidor SSH sintético no responde.')


def manual_start():
    capture('image', 'inspect', SERVER_IMAGE)
    key = EVIDENCE / 'infrastructure/synthetic'
    if not key.exists():
        raise RuntimeError('Primero prepara las herramientas del laboratorio.')
    if exists(MANUAL_NETWORK, 'network'):
        info = owned(MANUAL_NETWORK, 'network')
        if not info['Internal']:
            raise RuntimeError('La red manual debe ser interna.')
    else:
        docker('network', 'create', '--internal', '--label', f'{LABEL}={ROOT}', MANUAL_NETWORK)
    if exists(MANUAL_SERVER):
        info = owned(MANUAL_SERVER)
        if MANUAL_NETWORK not in info['NetworkSettings']['Networks']:
            raise RuntimeError('El servidor manual utiliza otra red.')
        if not info['State']['Running']:
            docker('start', MANUAL_SERVER)
    else:
        docker('run', '-d', '--init', '--name', MANUAL_SERVER,
               '--label', f'{LABEL}={ROOT}', '--network', MANUAL_NETWORK,
               '--pids-limit', '256', '--memory', '512m', *fixture_mounts(), SERVER_IMAGE)
    for _ in range(60):
        ready = subprocess.run(['docker', 'exec', MANUAL_SERVER, 'python3', '-c',
            'import socket; socket.create_connection(("127.0.0.1",22),.5).close()'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ready.returncode == 0:
            break
        time.sleep(.2)
    else:
        raise RuntimeError('El servidor SSH manual no responde.')
    docker('exec', MANUAL_SERVER, 'sh', '-c',
           'mkdir -p /home/lab/pruebas; '
           'if ! test -f /home/lab/pruebas/ejemplo.txt; then '
           'printf "Archivo sintetico para probar SSH y SFTP.\\n" > /home/lab/pruebas/ejemplo.txt; fi; '
           'if ! test -f /home/lab/pruebas/archivo-1MiB.bin; then '
           'truncate -s 1048576 /home/lab/pruebas/archivo-1MiB.bin; fi; '
           'chown -R lab:lab /home/lab/pruebas')
    public = capture('exec', MANUAL_SERVER, 'cat', '/etc/ssh/ssh_host_ed25519_key.pub').split()
    trust = EVIDENCE / 'infrastructure/manual-known-hosts'
    record = f'{MANUAL_SERVER} {public[0]} {public[1]}\n'
    if not trust.exists() or trust.read_text() != record:
        trust.write_text(record)
    if exists(DESKTOP):
        info = json.loads(capture('inspect', DESKTOP))[0]
        if info['Config']['Labels'].get(LABEL) != str(ROOT):
            raise RuntimeError('El contenedor visual no pertenece al laboratorio.')
        mounts = {m['Destination']: m['Source'] for m in info['Mounts']}
        if mounts.get('/opt/termia/src/termia') != str(SOURCE / 'src/termia'):
            raise RuntimeError('El contenedor visual utiliza otra copia del código.')
        if MANUAL_NETWORK not in info['NetworkSettings']['Networks']:
            docker('network', 'connect', MANUAL_NETWORK, DESKTOP)
    print(f'Servidor manual disponible: {MANUAL_SERVER}:22 (usuario sintético lab).')


def manual_stop():
    if exists(MANUAL_SERVER):
        info = owned(MANUAL_SERVER)
        if info['State']['Running']:
            docker('stop', '-t', '10', MANUAL_SERVER)


def observe_server(directory, stop):
    observations = directory / 'observations'
    while not stop.is_set():
        try:
            data = json.loads(capture('exec', SERVER, 'python3', '/opt/observe.py'))
            write_json(observations / 'status.json', data)
        except Exception as error:
            print(f'Monitor SSH: {error}', flush=True)
        stop.wait(.3)


def client_command(directory, mode):
    args = ['run', '--rm', '--init', '--name', CLIENT, '--label', f'{LABEL}={ROOT}',
            '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--read-only',
            '--tmpfs', '/tmp:rw,nosuid,size=1g', '--shm-size', '512m',
            '--pids-limit', '512', '--memory', '3g', '--cpus', '3',
            '--mount', f'type=bind,src={SOURCE / "src/termia"},dst=/opt/termia/src/termia,readonly',
            '--mount', f'type=bind,src={SOURCE / "run_termia.py"},dst=/opt/termia/run_termia.py,readonly',
            '--mount', f'type=bind,src={ROOT / "lab"},dst=/opt/lab,readonly',
            '--mount', f'type=bind,src={ROOT / "probes"},dst=/opt/probes,readonly',
            '--mount', f'type=bind,src={directory},dst=/evidence',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'TERMIA_PROBE_OUTPUT=/evidence']
    if mode in SSH_MODES:
        args += ['--network', NETWORK, '--env', f'TERMIA_LAB_HOST={SERVER}',
                 '--env', 'TERMIA_LAB_PORT=22', '--env', 'TERMIA_LAB_STATUS=/evidence/observations/status.json',
                 '--env', f'LAB_MEMORY_CYCLES={os.environ.get("LAB_MEMORY_CYCLES", "20")}',
                 '--env', 'TERMIA_LAB_KEY=/opt/synthetic',
                 '--mount', f'type=bind,src={EVIDENCE / "infrastructure/password"},dst=/opt/lab-password,readonly',
                 '--mount', f'type=bind,src={EVIDENCE / "infrastructure/synthetic"},dst=/opt/synthetic,readonly']
        command = ['python3', '-X', 'faulthandler', '/opt/lab/lifecycle/entry.py', mode]
    else:
        args += ['--network', 'none']
        probe_mode, separator, backend = mode.rpartition('-')
        if not separator or backend not in ('x11', 'wayland'):
            probe_mode, backend = mode, 'x11'
        command = ['python3', '-X', 'faulthandler', '/opt/probes/probe.py', probe_mode, backend]
    args += ['--entrypoint', 'bash', IMAGE, '-c',
             'mkdir -p "$HOME" "$XDG_RUNTIME_DIR"; chmod 700 "$HOME" "$XDG_RUNTIME_DIR"; '
             'unset SSH_AUTH_SOCK; export GDK_BACKEND=x11 GSETTINGS_BACKEND=memory; '
             'exec dbus-run-session -- xvfb-run -a -s "-screen 0 1800x1100x24 -nolisten tcp" "$@"',
             'termia-diagnostic', *command]
    return ['docker', *map(str, args)]


def worker(kind, directory, mode):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    manifest['state'] = 'running'
    write_json(directory / 'manifest.json', manifest)
    stop = threading.Event()
    observer = None
    server_owned = False
    client_owned = False
    try:
        if kind == 'monitor':
            info = json.loads(capture('inspect', DESKTOP))[0]
            if info['Config']['Labels'].get(LABEL) != str(ROOT):
                raise RuntimeError('Contenedor visual ajeno al laboratorio')
            mounts = {m['Destination']: m['Source'] for m in info['Mounts']}
            if mounts.get('/opt/termia/src/termia') != str(SOURCE / 'src/termia'):
                raise RuntimeError('El escritorio utiliza otra copia del código')
            with (directory / 'samples.jsonl').open('a') as output:
                while not (directory / 'stop.request').exists():
                    try:
                        value = json.loads(capture('exec', DESKTOP, 'python3', '/opt/lab/sample_process.py'))
                        output.write(json.dumps(value) + '\n')
                        output.flush()
                        write_json(directory / 'latest.json', value)
                    except Exception as error:
                        print(f'Esperando una instancia activa de Termia: {error}', flush=True)
                    time.sleep(1)
            manifest['state'] = 'stopped'
        else:
            if exists(CLIENT):
                owned(CLIENT)
                raise RuntimeError('Existe un cliente de diagnóstico; consulta su estado antes de continuar.')
            if mode in SSH_MODES:
                if exists(SERVER):
                    info = owned(SERVER)
                    if info['State']['Running']:
                        raise RuntimeError('El servidor sintético ya está ocupado.')
                server_owned = True
                setup_server()
                (directory / 'observations').mkdir()
                observer = threading.Thread(target=observe_server, args=(directory, stop), daemon=True)
                observer.start()
                for _ in range(50):
                    if (directory / 'observations/status.json').exists():
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError('El monitor del servidor no ha arrancado.')
            client_owned = True
            process = subprocess.Popen(client_command(directory, mode))
            started = time.monotonic()
            deadline = 7200 if mode == 'valgrind' else 3600
            while process.poll() is None:
                if (directory / 'stop.request').exists() or time.monotonic() - started > deadline:
                    if exists(CLIENT):
                        owned(CLIENT)
                        docker('stop', '-t', '10', CLIENT)
                    process.wait(timeout=30)
                    manifest['state'] = 'cancelled'
                    break
                time.sleep(.5)
            else:
                manifest['state'] = 'completed' if process.returncode == 0 else 'failed'
            manifest['exit_code'] = process.returncode
    except Exception as error:
        manifest.update(state='failed', error=str(error))
        print(f'ERROR: {error}', flush=True)
    finally:
        stop.set()
        if observer is not None:
            observer.join(timeout=15)
        for name, cleanup in ((CLIENT, client_owned), (SERVER, server_owned)):
            if cleanup and exists(name):
                try:
                    owned(name)
                    docker('stop', '-t', '10', name)
                except Exception as error:
                    manifest['cleanup_error'] = str(error)
                    manifest['state'] = 'failed'
        manifest['source_unchanged'] = fingerprint() == manifest['source_sha256']
        if not manifest['source_unchanged'] and manifest['state'] == 'completed':
            manifest['state'] = 'invalid-source-changed'
        manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(directory / 'manifest.json', manifest)
        print(json.dumps(manifest, indent=2), flush=True)


def status():
    if exists(MANUAL_SERVER):
        info = owned(MANUAL_SERVER)
        print(f'Servidor SSH manual: {info["State"]["Status"]}')
    for kind in ('monitor', 'diagnostic'):
        info = job(kind)
        print(f'\n{kind}:')
        if info is None:
            print('Sin ejecuciones.')
            continue
        directory = Path(info['directory'])
        print(json.dumps(info, indent=2))
        print((directory / 'manifest.json').read_text())
        if kind == 'monitor' and (directory / 'latest.json').exists():
            print((directory / 'latest.json').read_text())
        if kind == 'diagnostic' and (directory / 'console.log').exists():
            print('Últimos mensajes:')
            with (directory / 'console.log').open(errors='replace') as log:
                print(''.join(deque(log, maxlen=20)))


def cancel(kind):
    info = job(kind)
    if info is None or not info['active']:
        if kind == 'diagnostic':
            for name in (CLIENT, SERVER):
                if exists(name):
                    resource = owned(name)
                    if resource['State']['Running']:
                        docker('stop', '-t', '10', name)
            print('Recursos de diagnóstico detenidos; no había un trabajador activo.')
        else:
            print('No hay una tarea activa.')
        return
    (Path(info['directory']) / 'stop.request').touch()
    print('Parada solicitada. El trabajador cerrará sus recursos y guardará el resultado.')


def check_tools():
    command = [
        'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,nosuid,size=128m',
        '--user', f'{os.getuid()}:{os.getgid()}', '--env', 'PYTHONDONTWRITEBYTECODE=1',
        '--mount', f'type=bind,src={SOURCE / "src/termia"},dst=/opt/termia/src/termia,readonly',
        '--mount', f'type=bind,src={ROOT / "lab"},dst=/opt/lab,readonly',
        '--entrypoint', 'python3', IMAGE, '-c',
        'import sys, shutil; sys.path.insert(0,"/opt/lab/lifecycle"); '
        'import probe, memory_probe; from termia.app import TermiaWindow; '
        'print("Importaciones de ciclos de vida y memoria: correctas"); '
        'print("Menú actual:",hasattr(TermiaWindow,"refresh_tab_overflow_menu")); '
        'tools=("gdb","valgrind","ssh","sshpass","ssh-keyscan","Xvfb","xdotool","weston"); '
        'missing=[t for t in tools if not shutil.which(t)]; '
        'print("Herramientas ausentes:",missing); sys.exit(bool(missing))'
    ]
    docker(*command)
    print('Solo se han comprobado dependencias e importaciones; no se han ejecutado ensayos.')


def wait_for_diagnostic():
    info = job('diagnostic')
    if info is None:
        raise RuntimeError('No diagnostic has been started')
    path = Path(info['directory']) / 'manifest.json'
    while True:
        manifest = json.loads(path.read_text())
        if manifest['state'] not in ('starting', 'running'):
            break
        if birth(info['pid']) != info['birth']:
            raise RuntimeError('Diagnostic worker exited without a final manifest')
        time.sleep(.5)
    print(json.dumps(manifest, indent=2))
    if manifest['state'] != 'completed' or manifest.get('cleanup_error'):
        raise RuntimeError('Diagnostic did not complete successfully; inspect its results')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    sub.add_parser('check')
    sub.add_parser('status')
    sub.add_parser('monitor')
    sub.add_parser('manual-start')
    sub.add_parser('manual-stop')
    sub.add_parser('build')
    sub.add_parser('wait')
    desktop_actions = ('start', 'status-desktop', 'stop-desktop', 'remove', 'restart', 'restart-wayland', 'logs', 'url')
    for action in desktop_actions:
        sub.add_parser(action)
    sub.add_parser('cleanup')
    run = sub.add_parser('run')
    run.add_argument('mode', choices=MODES)
    stop = sub.add_parser('stop')
    stop.add_argument('kind', choices=('monitor', 'diagnostic'))
    internal = sub.add_parser('_worker')
    internal.add_argument('kind', choices=('monitor', 'diagnostic'))
    internal.add_argument('directory')
    internal.add_argument('mode')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'check':
        check_tools()
    elif args.action == 'status':
        status()
    elif args.action == 'monitor':
        start('monitor')
    elif args.action == 'manual-start':
        manual_start()
    elif args.action == 'manual-stop':
        manual_stop()
    elif args.action == 'build':
        build_images()
    elif args.action == 'wait':
        wait_for_diagnostic()
    elif args.action in desktop_actions:
        from desktop_control import desktop
        desktop(sys.modules[__name__], args.action)
    elif args.action == 'cleanup':
        for kind in ('monitor', 'diagnostic'):
            info = job(kind)
            if info and info['active']:
                raise RuntimeError('Stop active workers before cleanup')
        for name in (DESKTOP, MANUAL_SERVER, CLIENT, SERVER):
            if exists(name):
                info = owned(name)
                if info['State']['Running']:
                    docker('stop', '-t', '15', name)
                docker('rm', name)
        for name in (NETWORK, MANUAL_NETWORK):
            if exists(name, 'network'):
                owned(name, 'network')
                docker('network', 'rm', name)
        print('Owned containers/networks removed; images and local results retained.')
    elif args.action == 'run':
        start('diagnostic', args.mode)
    elif args.action == 'stop':
        cancel(args.kind)
    else:
        worker(args.kind, args.directory, args.mode)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
