"""Configure only synthetic credentials and native GNOME remote login."""
import os
import pwd
import secrets
import subprocess
import sys
import time
from pathlib import Path


def main():
    os.umask(0o077)
    state = Path('/var/lib/termia-lab')
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    state.chmod(0o700)
    password_file = state / 'password'
    if not password_file.exists():
        password_file.write_text(secrets.token_urlsafe(24) + '\n')
    password_file.chmod(0o600)
    password = password_file.read_text().strip()
    if not password or any(char in password for char in ':\r\n'):
        raise ValueError('Invalid synthetic laboratory password')
    if sys.argv[1:] == ['prepare']:
        subprocess.run(['/usr/sbin/chpasswd'], input=f'lab:{password}\n', text=True, check=True)
        print('Synthetic user lab is ready.', flush=True)
        return
    if sys.argv[1:] != ['session']:
        raise ValueError('Expected prepare or session phase')

    user = pwd.getpwnam('lab')
    runtime = Path('/run/user') / str(user.pw_uid)
    for attempt in range(300):
        if (runtime / 'bus').exists():
            break
        time.sleep(.1)
    else:
        raise RuntimeError('GNOME user session bus did not become available')

    def grd(*arguments, input=None):
        subprocess.run([
            '/usr/sbin/runuser', '-u', user.pw_name, '--', '/usr/bin/env',
            'XDG_RUNTIME_DIR=' + str(runtime),
            'DBUS_SESSION_BUS_ADDRESS=unix:path=' + str(runtime / 'bus'),
            '/usr/bin/grdctl', '--headless', 'rdp', *arguments,
        ], input=input, text=True, check=True, stdout=subprocess.DEVNULL)

    tls = Path(user.pw_dir) / '.local/share/gnome-remote-desktop'
    tls.mkdir(mode=0o700, parents=True, exist_ok=True)
    for directory in [Path(user.pw_dir) / '.local', tls.parent, tls]:
        os.chown(directory, user.pw_uid, user.pw_gid)
        directory.chmod(0o700)
    key, certificate = tls / 'tls.key', tls / 'tls.crt'
    if not key.exists() or not certificate.exists():
        subprocess.run([
            '/usr/sbin/runuser', '-u', user.pw_name, '--', '/usr/bin/openssl', 'req',
            '-new', '-newkey', 'rsa:3072', '-days', '365', '-nodes', '-x509',
            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
            '-keyout', str(key), '-out', str(certificate),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for arguments in [
        ['set-tls-key', str(key)], ['set-tls-cert', str(certificate)],
        ['set-port', '3389'], ['disable-port-negotiation'],
    ]:
        grd(*arguments)
    grd('set-credentials', 'lab', input=password + '\n')
    grd('enable')
    print('Native GNOME headless RDP configured for synthetic user lab.', flush=True)


if __name__ == '__main__':
    main()
