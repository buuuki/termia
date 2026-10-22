"""Generate server identity at runtime; accept only the mounted test fixture."""
import os
from pathlib import Path
import shutil
import subprocess

fixture = Path('/opt/fixture')
password = (fixture / 'password').read_text().strip()
if not password or '\n' in password or ':' in password:
    raise RuntimeError('Invalid generated laboratory password')
subprocess.run(['chpasswd'], input=f'lab:{password}\n', text=True, check=True)
shutil.copyfile(fixture / 'authorized_keys', '/home/lab/.ssh/authorized_keys')
os.chown('/home/lab/.ssh', 1001, 1001)
os.chown('/home/lab/.ssh/authorized_keys', 1001, 1001)
os.chmod('/home/lab/.ssh/authorized_keys', 0o600)
subprocess.run(['ssh-keygen', '-A'], check=True)
os.execv('/usr/sbin/sshd', ['/usr/sbin/sshd', '-D', '-e'])
