FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openssh-server python3 procps iproute2 ca-certificates && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash lab && echo 'lab:termia-synthetic-only' | chpasswd \
    && mkdir -p /run/sshd /home/lab/.ssh && chmod 700 /home/lab/.ssh
COPY synthetic.pub /home/lab/.ssh/authorized_keys
COPY remote_job.py /opt/remote_job.py
RUN chown -R lab:lab /home/lab/.ssh && chmod 600 /home/lab/.ssh/authorized_keys \
    && printf '\nPasswordAuthentication yes\nPermitRootLogin no\nUsePAM no\nPrintMotd no\nLogLevel VERBOSE\n' >> /etc/ssh/sshd_config
CMD ["/bin/sh", "-c", "ssh-keygen -A && exec /usr/sbin/sshd -D -e"]
