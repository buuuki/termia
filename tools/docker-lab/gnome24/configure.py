"""Configure only synthetic local accounts and GNOME 46 native remote login."""
from __future__ import annotations

import os
import pwd
import secrets
import stat
import subprocess
from pathlib import Path


def command(arguments, *, input_text=None):
    # GNOME 46's credential setter requires argv. Never log that vector,
    # propagate CalledProcessError or include captured output in diagnostics.
    try:
        result = subprocess.run(arguments, input=input_text, text=True,
                                capture_output=True, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError('Laboratory configuration command did not complete') from None
    if result.returncode:
        raise RuntimeError('Laboratory configuration command failed')


def load_password(path: Path) -> str:
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, 'r+') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError('Credential storage must be a regular file')
        os.fchmod(handle.fileno(), 0o600)
        password = handle.read(129).strip()
        if not password:
            password = secrets.token_urlsafe(24)
            handle.write(password + '\n')
        if not 16 <= len(password) <= 128 or any(c not in
                'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in password):
            raise ValueError('Invalid synthetic credentials')
        return password


def main():
    os.umask(0o077)
    state = Path('/var/lib/termia-lab')
    state.mkdir(mode=0o700, exist_ok=True)
    state.chmod(0o700)
    password = load_password(state / 'password')
    command(['/usr/sbin/chpasswd'], input_text='lab:' + password + '\n')

    user = pwd.getpwnam('gnome-remote-desktop')
    home = Path(user.pw_dir)
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(home, user.pw_uid, user.pw_gid)
    tls = home / 'termia-tls'
    tls.mkdir(mode=0o700, exist_ok=True)
    os.chown(tls, user.pw_uid, user.pw_gid)
    key, cert = tls / 'tls.key', tls / 'tls.crt'
    if key.exists() != cert.exists():
        raise RuntimeError('Incomplete TLS identity; restore the laboratory backup')
    if not key.exists():
        command(['/usr/sbin/runuser', '-u', user.pw_name, '--', '/usr/bin/openssl',
                 'req', '-new', '-newkey', 'rsa:3072', '-days', '365', '-nodes',
                 '-x509', '-subj', '/CN=localhost', '-addext',
                 'subjectAltName=DNS:localhost,IP:127.0.0.1',
                 '-keyout', str(key), '-out', str(cert)])

    def grd(*arguments):
        # Running as GRD's system account selects system mode in version 46
        # without invoking pkexec or changing PAM/polkit authorization policy.
        command(['/usr/sbin/runuser', '-u', user.pw_name, '--', '/usr/bin/env',
                 'HOME=' + str(home), 'XDG_CONFIG_HOME=' + str(home / '.config'),
                 'XDG_DATA_HOME=' + str(home / '.local/share'),
                 '/usr/bin/grdctl', 'rdp', *arguments])

    for args in (('set-tls-key', str(key)), ('set-tls-cert', str(cert)),
                 ('set-port', '3389'), ('disable-port-negotiation',),
                 ('set-credentials', 'lab', password), ('enable',)):
        grd(*args)
    print('Ubuntu 24 laboratory native remote login is configured.', flush=True)


if __name__ == '__main__':
    main()
