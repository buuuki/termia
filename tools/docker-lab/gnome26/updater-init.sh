#!/bin/bash
set -euo pipefail
install -d -m 755 -o lab -g lab /tmp/upgrade-evidence
install -m 600 -o lab -g lab /var/lib/termia-lab/password /home/lab/.lab-password
if [[ ! -e /home/lab/source ]]; then
  runuser -u lab -- python3 /opt/upgrade-lab/reset.py --source-only
fi
runuser -u lab -- env XDG_RUNTIME_DIR=/run/user/1100 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus \
  python3 /opt/upgrade-lab/configure-desktop.py
