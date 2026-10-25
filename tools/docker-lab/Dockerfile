FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-gi python3-gi-cairo python3-cryptography python3-yaml \
    python3-paramiko python3-tk gir1.2-gtk-4.0 gir1.2-vte-3.91 \
    gir1.2-gtksource-5 fonts-dejavu-core dbus-x11 xvfb xauth x11-utils \
    x11vnc novnc websockify openbox weston xterm xdotool gdb libc6-dbg \
    ca-certificates procps curl librsvg2-common yaru-theme-icon \
    valgrind openssh-client sshpass && rm -rf /var/lib/apt/lists/*
ARG LAB_UID=1000
RUN if ! getent passwd "$LAB_UID" >/dev/null; then \
      useradd --uid "$LAB_UID" --user-group --no-create-home --home-dir /tmp/home termia-lab; \
    fi
RUN apt-get update && apt-get install -y --no-install-recommends gsettings-desktop-schemas \
    && rm -rf /var/lib/apt/lists/*
COPY source/ /opt/termia/
COPY lab/ /opt/lab/
COPY probes/ /opt/probes/
WORKDIR /opt/termia
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/termia/src \
    HOME=/tmp/home XDG_RUNTIME_DIR=/tmp/runtime DISPLAY=:99 GTK_A11Y=none \
    NO_AT_BRIDGE=1 LIBGL_ALWAYS_SOFTWARE=1 GSK_RENDERER=cairo
ENTRYPOINT ["bash", "/opt/lab/boot.sh"]
