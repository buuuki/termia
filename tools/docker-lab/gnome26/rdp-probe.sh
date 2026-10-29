#!/bin/bash
set -euo pipefail
umask 077
mkdir -p "$HOME"
Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp -ac > "$HOME/xvfb.log" 2>&1 &
display_pid=$!
trap 'kill "$display_pid" 2>/dev/null || true' EXIT
for attempt in {1..100}; do
    if xdotool getdisplaygeometry >/dev/null 2>&1; then
        break
    fi
    sleep .1
done
xfreerdp3 /v:desktop:3389 /u:lab /from-stdin:force /cert:ignore -clipboard \
    /size:1440x900 /log-level:WARN < /credentials/password 2>&1 | tee "$HOME/rdp.log"
