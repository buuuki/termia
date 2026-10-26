#!/bin/bash
set -euo pipefail
mkdir -p /run/dbus /tmp/upgrade-evidence
chmod 755 /tmp/upgrade-evidence
chown lab:lab /tmp/upgrade-evidence
python3 - <<'PY'
from pathlib import Path
import secrets, subprocess
path=Path('/home/lab/.lab-password')
if not path.exists():
    password=secrets.token_urlsafe(8)
    subprocess.run(['chpasswd'],input='lab:'+password+'\n',text=True,check=True)
    path.write_text(password+'\n')
    path.chmod(0o600)
    import pwd, os
    user=pwd.getpwnam('lab')
    os.chown(path,user.pw_uid,user.pw_gid)
PY
dbus-daemon --system --fork
/usr/lib/polkit-1/polkitd --no-debug > /tmp/upgrade-evidence/polkit.log 2>&1 &
exec runuser -u lab -- env HOME=/home/lab XDG_RUNTIME_DIR=/tmp/runtime-lab \
    dbus-run-session -- bash /opt/upgrade-lab/desktop.sh
