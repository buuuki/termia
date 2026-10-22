#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$HOME" "$XDG_RUNTIME_DIR"
export GSETTINGS_BACKEND=keyfile
python3 - <<'PY'
from gi.repository import Gio

Gio.Settings.new("org.gnome.desktop.wm.preferences").set_string(
    "button-layout", "menu:minimize,maximize,close"
)
Gio.Settings.new("org.gnome.desktop.interface").set_string("icon-theme", "Yaru")
Gio.Settings.sync()
PY
dpkg-query -W libgtk-4-1 gir1.2-gtk-4.0 libvte-2.91-gtk4-0 weston python3 \
    > /evidence/packages.txt
exec dbus-run-session -- bash -c '
set -euo pipefail
Xvfb :99 -screen 0 1800x1100x24 -nolisten tcp > /evidence/xvfb.log 2>&1 &
for i in {1..100}; do xdpyinfo >/dev/null 2>&1 && break; sleep .1; done
xdpyinfo >/dev/null
openbox > /evidence/openbox.log 2>&1 &
weston --backend=x11-backend.so --renderer=pixman --socket=wayland-lab \
    --width=1600 --height=900 --idle-time=0 --no-config \
    --log=/evidence/weston.log &
for i in {1..100}; do test -S "$XDG_RUNTIME_DIR/wayland-lab" && break; sleep .1; done
test -S "$XDG_RUNTIME_DIR/wayland-lab"
x11vnc -display :99 -rfbport 5900 -localhost -nopw -forever -shared \
    -o /evidence/vnc.log &
websockify --web=/usr/share/novnc 6080 localhost:5900 > /evidence/websockify.log 2>&1 &
exec python3 /opt/lab/desktop.py
'
