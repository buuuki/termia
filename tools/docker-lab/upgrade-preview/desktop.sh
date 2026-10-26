#!/bin/bash
set -euo pipefail
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
Xvfb :99 -screen 0 1500x1000x24 -nolisten tcp > /tmp/upgrade-evidence/xvfb.log 2>&1 &
for i in {1..80}; do xdpyinfo >/dev/null 2>&1 && break; sleep .1; done
openbox > /tmp/upgrade-evidence/openbox.log 2>&1 &
x11vnc -display :99 -rfbport 5900 -localhost -nopw -forever -shared -o /tmp/upgrade-evidence/vnc.log &
websockify --web=/usr/share/novnc 6080 localhost:5900 > /tmp/upgrade-evidence/websockify.log 2>&1 &
python3 /opt/upgrade-lab/reset.py --source-only
exec python3 /opt/upgrade-lab/panel.py
