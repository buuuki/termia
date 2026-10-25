"""Populate a fresh laboratory profile with synthetic OpenSSH connections."""
import os
from pathlib import Path

from termia.constants import (DATA_FILE, SETTINGS_FILE, STATISTICS_FILE,
                              INSTANCE_LOCK_FILE, HISTORY_FILE)
from termia.stores import ConnectionStore


def main():
    host = os.environ['LAB_SSH_HOST']
    key = Path('/opt/manual-synthetic')
    if DATA_FILE.exists():
        raise RuntimeError('El perfil ya existe; no se sobrescribirá.')
    if not key.is_file():
        raise RuntimeError('Falta la clave sintética del laboratorio.')
    trust = Path.home() / '.ssh'
    trust.mkdir(mode=0o700, exist_ok=True)
    known_hosts = trust / 'known_hosts'
    record = Path('/opt/manual-known-hosts').read_text()
    existing = known_hosts.read_text() if known_hosts.exists() else ''
    # Replace only this synthetic host; retain other entries in this private HOME.
    rows = [line for line in existing.splitlines()
            if line.split() and line.split()[0] != host]
    known_hosts.write_text('\n'.join(rows + [record.strip()]) + '\n')
    known_hosts.chmod(0o600)
    store = ConnectionStore(DATA_FILE, SETTINGS_FILE, STATISTICS_FILE,
                            INSTANCE_LOCK_FILE, HISTORY_FILE)
    try:
        group = store.add_group('Pruebas SSH locales')
        store.add_server('SSH — contraseña de pruebas', host, 'lab', 22, group.id,
                         password=Path('/opt/lab-password').read_text().strip())
        store.add_server('SSH — clave de pruebas', host, 'lab', 22, group.id,
                         public_key=str(key))
        store.update_optional_tools(statistics_enabled=True, sftp_enabled=True)
    finally:
        store.close()
    print('Perfil sintético preparado: dos conexiones SSH, SFTP y estadísticas.')


if __name__ == '__main__':
    main()
