FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    qemu-system-x86 qemu-utils cloud-image-utils genisoimage novnc websockify \
    build-essential debhelper dh-python python3-all python3-setuptools \
    pybuild-plugin-pyproject ca-certificates python3-gi python3-cryptography \
    python3-paramiko python3-yaml gir1.2-gtk-4.0 gir1.2-gtksource-5 gir1.2-vte-3.91 \
    && rm -rf /var/lib/apt/lists/*
