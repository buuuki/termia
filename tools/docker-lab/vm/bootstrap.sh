#!/bin/bash
set -euxo pipefail
exec >> /var/log/termia-lab-bootstrap.log 2>&1
systemctl mask lightdm.service
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends xserver-xorg xserver-xorg-video-vesa \
    xserver-xorg-video-fbdev xfonts-base lightdm-gtk-greeter xfce4-session xfwm4 \
    xfce4-panel xfce4-settings xfdesktop4 lightdm policykit-1 policykit-1-gnome \
    dbus-x11 xterm python3-tk qemu-guest-agent xdotool sudo desktop-file-utils bsdutils
mkdir -p /mnt/termia-fixtures
mount -o ro /dev/disk/by-label/TERMIA_FIXTURES /mnt/termia-fixtures
apt-get install -y --no-remove /mnt/termia-fixtures/termia-beta3-official.deb
mkdir -p /opt/termia-lab /home/lab/candidate-source /home/lab/.config/autostart /home/lab/termia-lab-evidence
cp /mnt/termia-fixtures/{panel.py,worker.py,seed.py,password} /opt/termia-lab/
chmod 600 /opt/termia-lab/password
chown lab:lab /opt/termia-lab/password
tar -xzf /mnt/termia-fixtures/candidate-source.tar.gz -C /home/lab/candidate-source
cat > /home/lab/.config/autostart/termia-lab.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Termia laboratory control
Exec=python3 /opt/termia-lab/panel.py
Terminal=false
DESKTOP
# The distribution package supplies its own polkit agent autostart entry.
chown -R lab:lab /home/lab/candidate-source /home/lab/.config /home/lab/termia-lab-evidence
runuser -u lab -- env HOME=/home/lab python3 /opt/termia-lab/seed.py
python3 - <<'PY'
from pathlib import Path
import subprocess
password=Path('/opt/termia-lab/password').read_text().strip()
subprocess.run(['chpasswd'],input='lab:'+password+'\n',text=True,check=True)
PY
# Cloud images can grant passwordless sudo through a separate cloud-init rule.
rm -f /etc/sudoers.d/90-cloud-init-users
printf 'lab ALL=(ALL:ALL) ALL\n' > /etc/sudoers.d/91-termia-lab
chmod 440 /etc/sudoers.d/91-termia-lab
systemctl start qemu-guest-agent.service
systemctl unmask lightdm.service
systemctl set-default graphical.target
systemctl start lightdm.service
touch /var/lib/termia-lab-ready
