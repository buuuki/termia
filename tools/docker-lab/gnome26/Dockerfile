# Base-image preparation only. Desktop/session deployment is a separate step.
FROM ubuntu:26.04@sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78 AS certificate-bootstrap

# The official minimal base has no CA bundle. Extract the snapshot's pinned
# public certificates without executing a downloaded maintainer script.
ADD --checksum=sha256:f7025ab9b24cd73215510931037b02d6960d89584d0d00afba81851abdbe6ef1 \
    https://snapshot.ubuntu.com/ubuntu/20261027T000000Z/pool/main/c/ca-certificates/ca-certificates_20260223_all.deb \
    /tmp/ca-certificates.deb
RUN dpkg-deb --extract /tmp/ca-certificates.deb /tmp/certificates \
    && cat /tmp/certificates/usr/share/ca-certificates/mozilla/*.crt > /bootstrap-ca.crt

FROM ubuntu:26.04@sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78 AS base

LABEL org.opencontainers.image.title="Termia Ubuntu 26.04 desktop laboratory base" \
    org.opencontainers.image.description="Package-only base; GNOME Wayland, remote access and Termia integration remain unvalidated." \
    local.termia.issue="430" \
    local.termia.lab.stage="base-image" \
    local.termia.apt.snapshot="20261027T000000Z"

COPY --from=certificate-bootstrap /bootstrap-ca.crt /tmp/bootstrap-ca.crt
COPY ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -o Acquire::https::CaInfo=/tmp/bootstrap-ca.crt \
        -o APT::Update::Error-Mode=any update \
    && apt-get -o Acquire::https::CaInfo=/tmp/bootstrap-ca.crt \
        install -y --install-recommends \
        ubuntu-desktop gnome-remote-desktop systemd-sysv dbus ca-certificates \
    && mkdir -p /usr/local/share/termia-lab \
    && dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n' \
        | LC_ALL=C sort > /usr/local/share/termia-lab/packages.tsv \
    && printf '%s\n' '20261027T000000Z' > /usr/local/share/termia-lab/apt-snapshot \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/bootstrap-ca.crt

# No desktop startup, user accounts, listening ports, volumes or host integration
# are configured at this package-installation stage.
CMD ["/bin/bash"]

FROM base AS desktop

LABEL org.opencontainers.image.description="Experimental GNOME Wayland/RDP desktop; Termia integration remains pending." \
    local.termia.lab.stage="desktop-prototype"

RUN useradd --create-home --uid 1100 --shell /bin/bash --groups sudo lab \
    && rm -f /etc/machine-id /var/lib/dbus/machine-id \
    && touch /etc/machine-id \
    && ln -s /etc/machine-id /var/lib/dbus/machine-id \
    && install -d -m 0700 /var/lib/termia-lab

COPY init.sh /usr/local/sbin/termia-lab-init
COPY configure-rdp.py /usr/local/lib/termia-lab/configure-rdp.py
COPY termia-lab.target termia-lab-rdp.service /etc/systemd/system/
COPY termia-lab-session.service termia-lab-user-rdp.service /etc/systemd/system/
COPY after-rdp.conf /etc/systemd/system/gdm.service.d/termia-lab.conf
COPY rendering.conf /usr/lib/environment.d/90-termia-lab-rendering.conf
RUN chmod 0755 /usr/local/sbin/termia-lab-init

ENV container=docker SYSTEMD_LOG_TARGET=console
STOPSIGNAL SIGRTMIN+3
ENTRYPOINT ["/usr/local/sbin/termia-lab-init"]
CMD []

# Optional RDP verification client. Its X11 display is independent of the
# GNOME Wayland compositor in the desktop service.
FROM base AS rdp-probe
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -o APT::Update::Error-Mode=any update \
    && apt-get install -y --no-install-recommends freerdp3-x11 xvfb xauth xdotool \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY rdp-probe.sh /usr/local/bin/termia-rdp-probe
RUN chmod 0755 /usr/local/bin/termia-rdp-probe
ENTRYPOINT ["/usr/local/bin/termia-rdp-probe"]
CMD []
