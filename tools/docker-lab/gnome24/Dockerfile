# Base-image preparation only. Desktop/session deployment is a separate step.
FROM ubuntu:24.04@sha256:69cecf4bbf72d2d44a9eef1b71fb98c7fb973d78af11399deccef19beb008ad9 AS certificate-bootstrap

# The official minimal base has no CA bundle. Extract the snapshot's pinned
# public certificates without executing a downloaded maintainer script.
ADD --checksum=sha256:f7025ab9b24cd73215510931037b02d6960d89584d0d00afba81851abdbe6ef1 \
    https://snapshot.ubuntu.com/ubuntu/20261027T000000Z/pool/main/c/ca-certificates/ca-certificates_20260223_all.deb \
    /tmp/ca-certificates.deb
RUN dpkg-deb --extract /tmp/ca-certificates.deb /tmp/certificates \
    && cat /tmp/certificates/usr/share/ca-certificates/mozilla/*.crt > /bootstrap-ca.crt

FROM ubuntu:24.04@sha256:69cecf4bbf72d2d44a9eef1b71fb98c7fb973d78af11399deccef19beb008ad9 AS base

LABEL org.opencontainers.image.title="Termia Ubuntu 24.04 desktop laboratory base" \
    org.opencontainers.image.description="Package-only base; GNOME Wayland, remote access and Termia integration remain unvalidated." \
    local.termia.issue="459" \
    local.termia.lab.stage="base-image" \
    local.termia.apt.snapshot="20261027T000000Z"

COPY --from=certificate-bootstrap /bootstrap-ca.crt /tmp/bootstrap-ca.crt
RUN printf '%s\n' \
    'Acquire::https::Pipeline-Depth "0";' \
    'Acquire::Retries "3";' > /etc/apt/apt.conf.d/80-termia-snapshot
RUN printf '%s\n' \
    'Types: deb' \
    'URIs: https://snapshot.ubuntu.com/ubuntu/20261027T000000Z/' \
    'Suites: noble noble-updates noble-security' \
    'Components: main universe restricted multiverse' \
    'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
    'Check-Valid-Until: no' > /etc/apt/sources.list.d/ubuntu.sources

ARG FIREFOX_VERSION=159.0~build1

# Mozilla repository key, verified against the published signing fingerprint.
ADD --checksum=sha256:3ecc63922b7795eb23fdc449ff9396f9114cb3cf186d6f5b53ad4cc3ebfbb11f \
    https://packages.mozilla.org/apt/repo-signing-key.gpg \
    /tmp/packages.mozilla.org.asc

RUN apt-get -o Acquire::https::CaInfo=/tmp/bootstrap-ca.crt \
        -o APT::Update::Error-Mode=any update

# Use APT's signed package plan and existing downloader. Bounded parallel
# downloads avoid serial snapshot latency; each archive requires SHA-256.
RUN export DEBIAN_FRONTEND=noninteractive \
    && packages=' \
        ubuntu-desktop gnome-remote-desktop systemd-sysv dbus ca-certificates \
        python3-gi python3-gi-cairo python3-cryptography python3-yaml \
        python3-paramiko python3-venv gir1.2-gtk-4.0 gir1.2-vte-3.91 \
        gir1.2-gtksource-5 git openssh-client sshpass gnome-terminal \
        xvfb xauth dbus-x11 xdotool gdb valgrind curl iproute2 \
        language-pack-en language-pack-gnome-en \
        language-pack-es language-pack-gnome-es \
        language-pack-ca language-pack-gnome-ca' \
    && apt-get --print-uris -o Acquire::ForceHash=sha256 \
        install -y --install-recommends $packages > /tmp/termia-package-plan \
    && awk '$1 ~ /^.https:/ { \
        if ($4 !~ /^SHA256:[0-9a-f]+$/ || length($4) != 71) exit 1; \
        print substr($1, 2, length($1)-2), $2, $4; \
        }' /tmp/termia-package-plan > /tmp/termia-package-downloads \
    && test -s /tmp/termia-package-downloads \
    && xargs -r -n 3 -P 8 sh -ec ' \
        archive="https://archive.ubuntu.com/ubuntu/pool/${1#*/pool/}"; \
        /usr/lib/apt/apt-helper -o Acquire::https::CaInfo=/tmp/bootstrap-ca.crt \
            -o Acquire::Retries=1 download-file \
            "$archive" "/var/cache/apt/archives/$2" "$3" \
        || /usr/lib/apt/apt-helper -o Acquire::https::CaInfo=/tmp/bootstrap-ca.crt \
            -o Acquire::Retries=3 download-file \
            "$1" "/var/cache/apt/archives/$2" "$3"' sh \
        < /tmp/termia-package-downloads \
    && apt-get --no-download install -y --install-recommends $packages \
    && locale-gen en_US.UTF-8 es_ES.UTF-8 ca_ES.UTF-8 \
    && install -d -m 0755 /etc/apt/keyrings \
    && install -m 0644 /tmp/packages.mozilla.org.asc \
        /etc/apt/keyrings/packages.mozilla.org.asc \
    && printf '%s\n' \
        'Types: deb' \
        'URIs: https://packages.mozilla.org/apt' \
        'Suites: mozilla' \
        'Components: main' \
        'Signed-By: /etc/apt/keyrings/packages.mozilla.org.asc' \
        > /etc/apt/sources.list.d/mozilla.sources \
    && printf '%s\n' \
        'Package: firefox firefox-l10n-*' \
        'Pin: origin packages.mozilla.org' \
        'Pin-Priority: 1000' \
        '' \
        'Package: firefox' \
        'Pin: release o=Ubuntu' \
        'Pin-Priority: -1' \
        > /etc/apt/preferences.d/mozilla \
    && apt-get -o APT::Update::Error-Mode=any update \
    && apt-get install -y --no-install-recommends --no-remove \
        --allow-downgrades \
        "firefox=${FIREFOX_VERSION}" \
        "firefox-l10n-es-es=${FIREFOX_VERSION}" \
        "firefox-l10n-ca=${FIREFOX_VERSION}" \
    && mkdir -p /usr/local/share/termia-lab \
    && dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n' \
        | LC_ALL=C sort > /usr/local/share/termia-lab/packages.tsv \
    && printf '%s\n' '20261027T000000Z' > /usr/local/share/termia-lab/apt-snapshot \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/bootstrap-ca.crt \
        /tmp/packages.mozilla.org.asc /tmp/termia-package-plan \
        /tmp/termia-package-downloads

# No desktop startup, user accounts, listening ports, volumes or host integration
# are configured at this package-installation stage.
CMD ["/bin/bash"]

FROM base AS desktop

RUN useradd --create-home --uid 1100 --shell /bin/bash --groups sudo lab \
    && update-locale LANG=en_US.UTF-8 \
    && rm -f /etc/machine-id /var/lib/dbus/machine-id \
    && touch /etc/machine-id \
    && ln -s /etc/machine-id /var/lib/dbus/machine-id
COPY infra/init.sh /usr/local/sbin/termia-lab-init
COPY infra/rendering.conf /usr/lib/environment.d/90-termia-lab-rendering.conf
COPY configure.py panel.py /opt/termia-lab/
COPY termia-lab-prepare.service /etc/systemd/system/
COPY org.termia.Lab24.desktop /usr/share/applications/
COPY org.termia.Lab24.desktop /etc/xdg/autostart/
RUN chmod 0755 /usr/local/sbin/termia-lab-init \
    && sed -i 's/--unit=termia-lab.target/--unit=graphical.target/' /usr/local/sbin/termia-lab-init \
    && mkdir -p /etc/systemd/system/gnome-remote-desktop.service.d \
    && printf '%s\n' '[Unit]' 'Requires=termia-lab-prepare.service' \
       'After=termia-lab-prepare.service' \
       > /etc/systemd/system/gnome-remote-desktop.service.d/termia.conf \
    && mkdir -p /etc/systemd/system/gdm.service.d \
    && cp /etc/systemd/system/gnome-remote-desktop.service.d/termia.conf \
       /etc/systemd/system/gdm.service.d/termia.conf \
    && sed -i 's/RequiredComponents=/RequiredComponents=org.gnome.RemoteDesktop.Handover;/' \
       /usr/share/gnome-session/sessions/gnome-login.session \
    && systemctl --global enable gnome-remote-desktop-handover.service \
    && systemctl --global mask org.gnome.SettingsDaemon.Sharing.service \
    && mkdir -p /etc/systemd/system/colord.service.d \
    && printf '%s\n' '[Service]' 'PrivateUsers=false' \
       > /etc/systemd/system/colord.service.d/container.conf \
    && systemctl enable termia-lab-prepare.service gdm.service gnome-remote-desktop.service
COPY source/requirements-ci.txt source/requirements-coverage.txt /opt/lab-requirements/
RUN python3 -m venv --system-site-packages /opt/lab-tools \
    && /opt/lab-tools/bin/python -m pip install --no-cache-dir \
       -r /opt/lab-requirements/requirements-ci.txt \
       -r /opt/lab-requirements/requirements-coverage.txt
COPY --chown=lab:lab source/ /opt/termia/
ENV container=docker SYSTEMD_LOG_TARGET=console \
    PATH=/opt/lab-tools/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONDONTWRITEBYTECODE=1
STOPSIGNAL SIGRTMIN+3
ENTRYPOINT ["/usr/local/sbin/termia-lab-init"]
CMD []
