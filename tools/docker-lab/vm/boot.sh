#!/bin/bash
set -euo pipefail
websockify --web=/usr/share/novnc 6080 127.0.0.1:5901 > /vm/websockify.log 2>&1 &
exec qemu-system-x86_64 \
 -name termia-observable-validation \
 -machine q35 -accel kvm -cpu host -m 2048 -smp 2 \
 -drive file=/vm/system.qcow2,if=virtio,format=qcow2,cache=writeback \
 -drive file=/vm/seed.iso,media=cdrom,readonly=on \
 -drive file=/vm/fixtures.iso,media=cdrom,readonly=on \
 -device qemu-xhci -device usb-tablet -vga std \
 -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
 -chardev socket,path=/vm/guest-agent.sock,server=on,wait=off,id=qga0 \
 -device virtio-serial-pci -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \
 -qmp unix:/vm/qmp.sock,server=on,wait=off \
 -serial file:/vm/serial.log -monitor none -display none -vnc 127.0.0.1:1
