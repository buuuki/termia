#!/bin/bash
set -euo pipefail
install -d -m 755 -o lab -g lab /tmp/upgrade-evidence
install -m 600 -o lab -g lab /var/lib/termia-lab/password /home/lab/.lab-password
if [[ ! -e /home/lab/source ]]; then
  runuser -u lab -- python3 /opt/upgrade-lab/reset.py --source-only
fi
session=(runuser -u lab -- env XDG_RUNTIME_DIR=/run/user/1100
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus)
for attempt in {1..60}; do
  if "${session[@]}" systemctl --user is-active --quiet gnome-session@ubuntu.target; then
    break
  fi
  sleep .5
done
if ! "${session[@]}" systemctl --user is-active --quiet gnome-session@ubuntu.target; then
  printf '%s\n' 'Ubuntu user session did not become active; dock setup was not applied.' >&2
  exit 1
fi
# Inherit the desktop identity and locale from the actual user session manager.
"${session[@]}" systemd-run --user --wait --pipe --collect --quiet \
  /usr/bin/python3 /opt/upgrade-lab/configure-desktop.py
