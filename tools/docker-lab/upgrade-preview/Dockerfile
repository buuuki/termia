FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-gi python3-tk python3-gi-cairo git sudo polkitd pkexec \
    gir1.2-polkit-1.0 dbus-x11 xvfb xauth x11-utils x11vnc novnc websockify \
    openbox xterm xdotool ca-certificates fonts-dejavu-core librsvg2-common \
    yaru-theme-icon desktop-file-utils
RUN useradd --create-home --shell /bin/bash --groups sudo lab
COPY fixtures/ /opt/fixtures/
RUN echo 'b0b1382abb505ab09f004a6b555f39b8b142c95a7d4dbe01052784f1151b0691  /opt/fixtures/beta3.deb' | sha256sum -c - \
    && echo 'a8f1582fd70eb12510b29522fe164b23e38c0f69850e63a0908de6844fa995b3  /opt/fixtures/termia_0.6.0.beta.4-1_all.deb' | sha256sum -c - \
    && apt-get install -y --no-remove /opt/fixtures/beta3.deb
COPY review/ /opt/review/
COPY boot.sh desktop.sh panel.py launch.py reset.py /opt/upgrade-lab/
RUN printf 'polkit.addAdminRule(function(action, subject) { return ["unix-user:lab"]; });\npolkit.addRule(function(action, subject) { if (action.id == "org.freedesktop.policykit.exec" && subject.user == "lab") return polkit.Result.AUTH_ADMIN; });\n' > /etc/polkit-1/rules.d/49-termia-lab.rules \
    && chown -R lab:lab /home/lab
ENV HOME=/home/lab XDG_RUNTIME_DIR=/tmp/runtime-lab DISPLAY=:99 GDK_BACKEND=x11 \
    PYTHONPATH= GTK_A11Y=none NO_AT_BRIDGE=1 LIBGL_ALWAYS_SOFTWARE=1 GSK_RENDERER=cairo
WORKDIR /home/lab
ENTRYPOINT ["bash", "/opt/upgrade-lab/boot.sh"]
