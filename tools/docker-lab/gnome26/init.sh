#!/bin/bash
set -euo pipefail

if [[ "$(cat /proc/self/cgroup)" != '0::/' ]]; then
    echo 'A private cgroup v2 namespace is required.' >&2
    exit 1
fi

# Docker's existing cgroup mount is scoped to this private namespace. Never
# replace it with a bind mount of the host's complete cgroup tree.
mount -o remount,rw /sys/fs/cgroup
exec /sbin/init --unit=termia-lab.target
