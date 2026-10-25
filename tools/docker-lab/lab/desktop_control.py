"""Host-side operations restricted to resources owned by this checkout."""
import json
import os
import subprocess
import time


def desktop(control, action):
    name = control.DESKTOP
    docker, capture, owned = control.docker, control.capture, control.owned
    if action == 'url':
        owned(name)
        address = capture('port', name, '6080/tcp')
        if not address.startswith('127.0.0.1:'):
            raise RuntimeError('Desktop must be published on loopback only')
        print(f'http://{address}/vnc.html?autoconnect=1&resize=scale')
    elif action == 'start':
        capture('image', 'inspect', control.IMAGE)
        control.manual_start()
        if control.exists(name):
            owned(name)
            docker('start', name)
        else:
            directory = control.EVIDENCE / 'desktop'
            directory.mkdir(parents=True, exist_ok=True)
            infra = control.EVIDENCE / 'infrastructure'
            port = int(os.environ.get('LAB_PORT', '6080'))
            if not 1024 <= port <= 65535:
                raise RuntimeError('LAB_PORT must be between 1024 and 65535')
            docker('run', '-d', '--init', '--name', name, '--label', f'{control.LABEL}={control.ROOT}',
                   '--network', 'bridge', '--user', f'{os.getuid()}:{os.getgid()}',
                   '--cap-drop', 'ALL', '--cap-add', 'SYS_PTRACE',
                   '--security-opt', 'no-new-privileges', '--read-only',
                   '--tmpfs', '/tmp:rw,nosuid,size=1g', '--shm-size', '512m',
                   '--pids-limit', '512', '--memory', '3g', '--cpus', '3',
                   '-p', f'127.0.0.1:{port}:6080', '--env', f'LAB_SSH_HOST={control.MANUAL_SERVER}',
                   '--mount', f'type=bind,src={control.SOURCE / "src/termia"},dst=/opt/termia/src/termia,readonly',
                   '--mount', f'type=bind,src={control.SOURCE / "run_termia.py"},dst=/opt/termia/run_termia.py,readonly',
                   '--mount', f'type=bind,src={infra / "synthetic"},dst=/opt/manual-synthetic,readonly',
                   '--mount', f'type=bind,src={infra / "password"},dst=/opt/lab-password,readonly',
                   '--mount', f'type=bind,src={infra / "manual-known-hosts"},dst=/opt/manual-known-hosts,readonly',
                   '--mount', f'type=bind,src={directory},dst=/evidence', control.IMAGE)
        # Docker does not publish ports for an internal-only endpoint.
        # Keep browser ingress on loopback and add the private SSH network.
        control.manual_start()
        for _ in range(80):
            ready = subprocess.run(['docker', 'exec', name, 'curl', '--fail', '--silent',
                                    '--max-time', '1', '--output', '/dev/null',
                                    'http://127.0.0.1:6080/vnc.html'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ready.returncode == 0:
                address = capture('port', name, '6080/tcp')
                if not address.startswith('127.0.0.1:'):
                    raise RuntimeError('Desktop must be published on loopback only')
                print(f'http://{address}/vnc.html?autoconnect=1&resize=scale')
                return
            time.sleep(.25)
        raise RuntimeError('Desktop is not ready; use the logs command')
    elif action == 'status-desktop':
        if control.exists(name):
            print(f'{name}: {owned(name)["State"]["Status"]}')
        else:
            print('Desktop not created; run prepare, then start.')
        control.status()
    else:
        info = owned(name)
        if action == 'stop-desktop':
            docker('stop', '-t', '15', name)
            control.manual_stop()
        elif action == 'remove':
            if info['State']['Running']:
                raise RuntimeError('Stop the desktop before removing it')
            docker('rm', name)
        elif action == 'restart':
            control.manual_start()
            docker('restart', name)
        elif action == 'logs':
            docker('logs', '--tail', '100', name)
        elif action == 'restart-wayland':
            docker('exec', name, 'pkill', '-TERM', '-x', 'weston')
            for _ in range(50):
                # Ignore zombies until the container init reaps them.
                live = capture('exec', name, 'python3', '-c',
                               'from pathlib import Path; '
                               'print(any((lambda s: s[1] == "(weston)" and s[2] != "Z")(p.read_text().split()) '
                               'for p in Path("/proc").glob("[0-9]*/stat") if p.exists()))')
                if live == 'False':
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Weston did not stop; refusing to create a duplicate')
            docker('exec', '-d', name, 'weston', '--backend=x11-backend.so',
                   '--renderer=pixman', '--socket=wayland-lab', '--width=1600', '--height=900',
                   '--idle-time=0', '--no-config', '--log=/evidence/weston-restart.log')
            print('Weston restarted. Use Iniciar / nueva prueba in the bottom panel.')
        else:
            raise RuntimeError('Unknown desktop operation')
