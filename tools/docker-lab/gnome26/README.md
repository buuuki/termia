# Ubuntu 26.04 GNOME laboratory: experimental desktop

[Español](README.es.md) · [Català](README.ca.md)

Issue #430 provides a headless GNOME Wayland/RDP desktop built directly with
Docker, plus an optional Termia trial image and GTK control panel. On 2026-10-29
the requester accepted this environment as a sufficient baseline for testing
Termia. Functional application and updater validation belong to #428 or their
own issues. This infrastructure acceptance does not certify a Termia release
or remove the runtime and portability limitations documented below.

## Reopen the existing desktop

If the container already exists on this computer, reuse it instead of rebuilding.
Start from a clean checkout; save local changes before switching branches.

```bash
git switch maintenance/430-docker-gnome
git pull --ff-only
docker start termia-430-gnome26-desktop-1
docker inspect --format '{{.State.Health.Status}}' termia-430-gnome26-desktop-1
docker exec termia-430-gnome26-desktop-1 cat /var/lib/termia-lab/password
remmina -c tools/docker-lab/gnome26/laboratory.remmina
```

Wait for `healthy` before connecting. If it says `starting`, wait a few seconds
and repeat the inspection command; inspect the container logs if it is unhealthy.
Use RDP at **127.0.0.1:13389**, user **lab**, no domain, and the generated password.
The **Laboratorio de pruebas de Termia** dock icon opens the compact GTK panel.
The profile and credential volumes preserve the dock, password and user data.
If first-login password prompts recur, use the temporary workaround documented
below. Do not remove volumes when resuming an existing session.

## If Docker Compose is unavailable

An existing container can be resumed with `docker start` without Compose.
For a fresh build, install the official standalone Compose binary in the ignored
local tools directory and verify its fixed SHA-256:

```bash
mkdir -p tools/docker-lab/.runtime/bin
curl --fail --location --proto '=https' --proto-redir '=https' \
  https://github.com/docker/compose/releases/download/v2.40.0/docker-compose-linux-x86_64 \
  -o tools/docker-lab/.runtime/bin/docker-compose
printf '%s\n' 'bd5835ccbbf06a42dcb5294c65e34a4634b34447afb9ed6fc7adf18a000e0f99  tools/docker-lab/.runtime/bin/docker-compose' | sha256sum -c -
chmod 700 tools/docker-lab/.runtime/bin/docker-compose
```

In the build commands below, replace `docker compose` with
`tools/docker-lab/.runtime/bin/docker-compose` when using this standalone binary.

## Reconstruction on another PC and portability limits

The recipes rebuild the system without exporting an image, importing a disk or
manually installing Ubuntu in a volume. As of 2026-10-28 these changes remain
under development on branch `maintenance/430-docker-gnome`. Use that branch
and record the selected commit; `main` does not contain this deployment.
Reconstruction on a second PC and a second uncached download have not yet
been validated.

```bash
git clone --branch maintenance/430-docker-gnome --single-branch https://github.com/buuuki/termia.git
cd termia
git rev-parse HEAD
```

| Host requirement | Status or reason |
| --- | --- |
| Linux x86-64 with a local Docker Engine and sufficient permissions | Tested with kernel 6.8, Engine 28.5.1, Compose 2.40.0, cgroup v2 and systemd driver |
| Private writable cgroups | Container systemd relies on the host kernel and runtime permissions |
| FUSE kernel interface and `/dev/fuse` | Required for GNOME mounts; recipes do not install or load a host module |
| Compatible security policy | `SYS_ADMIN`, per-container AppArmor unconfined and versioned seccomp; review restrictions on the new host |
| Available resources | Desktop limits: 2 CPUs, 4 GiB RAM and 256 MiB shared memory; allow additional host and build-layer resources |
| Network and port | Docker Hub and Ubuntu snapshot downloads; local port 13389 available |
| Graphical client | Remmina with GFX tested; no shared host GPU or desktop session |
| Windows, macOS, ARM, Docker Desktop, rootless or SELinux | Unvalidated; compatibility is not guaranteed |

Preflight checks from the checkout root:

```bash
uname -m
uname -r
docker version
docker compose version
docker info --format 'architecture={{.Architecture}} cgroups={{.CgroupVersion}} driver={{.CgroupDriver}}'
test -c /dev/fuse && ls -l /dev/fuse
docker compose -f tools/docker-lab/gnome26/compose.yaml config --quiet
```

Systemd, GDM, D-Bus, GNOME Shell and GNOME Remote Desktop belong to the image.
They do not connect to the host's D-Bus or desktop session. Docker shares its
Linux kernel; it does not reproduce an Ubuntu ISO's kernel or boot process.
Review missing host requirements rather than substituting QEMU/KVM.

Once the recipes are available on the new PC, build and start:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml build desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop cat /var/lib/termia-lab/password
```

| Connection field | Value |
| --- | --- |
| Protocol | RDP |
| IP from the Docker host itself | `127.0.0.1` |
| Port | `13389` |
| Login | `lab` |
| Password | Generated; retrieve using the command above on each installation |
| Domain | Empty |
| Resolution and graphics | 1440 × 900, GFX (`colordepth=63` in Remmina) |

`127.0.0.1` refers to the PC running the client. This Compose publishes only
on loopback; entering the server's LAN IP from another computer does not grant
access. The certificate belongs to each profile; verify its fingerprint when
connecting, especially after removing volumes.

A fresh reconstruction preserves declarative configuration but generates a new
password, TLS key and empty profile. Preserving session data requires backing
up and restoring **both** volumes (`profile` and `credentials`) with the desktop
stopped and ownership/permissions retained. These contain data and secrets;
keep them out of Git. Cross-host volume migration remains unvalidated and is
not needed to rebuild the system. Avoid `down --volumes` when retaining data.

## Languages and Firefox

The image includes English, Spanish and Catalan language packs for Ubuntu and
GNOME, with `en_US.UTF-8`, `es_ES.UTF-8` and `ca_ES.UTF-8` locales.
Select the session language through Language Support; apply the requested
session restart to check the result.

Firefox is installed as a native DEB from Mozilla's signed APT repository,
with Spanish and Catalan translations and English included in the browser.
The initial version is fixed by `FIREFOX_VERSION` in the Dockerfile.
Mozilla's repository is separate from the fixed Ubuntu snapshot; rebuilding
requires that the selected Firefox version remains available.

Open Firefox from the application grid and check an HTTPS page and text input.
Language packs and Firefox are part of the image. User preferences persist in
the `profile` volume across container restarts and recreation.

## Ubuntu session defaults

The desktop starts with `en_US.UTF-8`; Language Support can select Spanish or
Catalan through Ubuntu's existing user settings. Existing profile preferences
are retained. GDM starts the Ubuntu session, which supplies the Yaru theme,
Ubuntu fonts, window buttons and keyboard defaults.

Open applications from the GNOME application grid or the panel's dock launcher.
For a manual panel launch from the host, close its previous instance and run:

```bash
docker exec termia-430-gnome26-desktop-1 runuser -u lab -- env \
  XDG_RUNTIME_DIR=/run/user/1100 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus \
  systemd-run --user --collect --quiet \
  /usr/bin/python3 /opt/upgrade-lab/panel.py
```

The user manager supplies the session environment to the panel and its children.
Dock initialization uses the same mechanism after the Ubuntu session is active.
Direct `docker exec` launches do not inherit that environment automatically.

## Configuration map and operation

| File | Responsibility |
| --- | --- |
| `Dockerfile`, `ubuntu.sources`, `.dockerignore` | Base, pinned packages, stages and permitted build context |
| `compose.yaml` | Resources, isolation, FUSE, port and volumes |
| `init.sh`, `termia-lab.target` | Private cgroups and systemd startup |
| `termia-lab-rdp.service`, `configure-rdp.py` | Synthetic user, credentials and TLS/RDP configuration |
| `termia-lab-session.service`, `after-rdp.conf` | GDM-created Wayland session and startup ordering |
| `termia-lab-user-rdp.service` | RDP server configuration inside the session |
| `rendering.conf` | Software rendering |
| `seccomp-desktop.json`, `LICENSE.seccomp` | Seccomp profile, `pivot_root` permission and upstream license |
| `laboratory.remmina` | Human client profile without stored password |
| `rdp-probe.sh` | Optional isolated RDP validation client |
| `Dockerfile.updater`, `compose.updater.yaml`, `prepare-updater.sh` | Optional updater image and allowlisted fixture preparation |
| `panel.py`, `updater-init.sh`, `termia-lab-updater.service` | Recovered GTK controls and synthetic trial initialization |
| `org.termia.TestingLab.desktop`, `configure-desktop.py` | Panel launcher and additive dock setup |

Read-only status commands:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml ps
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop systemctl --failed --no-pager
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop journalctl -b --no-pager _COMM=gnome-shell -n 60
```

When idle locking leaves a black image, the tested recovery interrupts the
session while preserving volumes and credentials:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml restart desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
```

This does not fix idle-lock recovery. The sections below distinguish validated
behavior, observed failures and remaining acceptance requirements before the
final commit and completion of the laboratory.

## Start and connect

From the repository root:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml build desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop cat /var/lib/termia-lab/password
install -Dm600 tools/docker-lab/gnome26/laboratory.remmina tools/docker-lab/.runtime/gnome26.remmina
remmina -c tools/docker-lab/.runtime/gnome26.remmina
```

RDP listens on `127.0.0.1:13389`, username `lab`, at 1440 × 900. Enter the
generated synthetic password printed by the explicit command above; do not
publish it or save it into tracked files. The Remmina template disables
clipboard sharing and password storage. Verify the self-signed TLS certificate
fingerprint before accepting it:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop \
  openssl x509 -in /home/lab/.local/share/gnome-remote-desktop/tls.crt \
  -noout -sha256 -fingerprint
```

The profile explicitly sets `colordepth=63` to enable the RDP graphics pipeline
required by GNOME; plain 32-bit mode was rejected by the server. A private
Remmina client authenticated with the generated password and displayed GNOME
after this correction. The initial validation had used FreeRDP and did not
catch the incorrect Remmina profile. Close any old connection tab before
reopening the corrected profile. Clipboard negotiation previously aborted the
server because `/dev/fuse` was missing; Compose now declares that device, and
a clipboard-enabled Remmina client no longer aborts the server.

The standard idle screen lock remains enabled. A locked session returned a
black RDP image during troubleshooting; a full container restart preserving
the data volumes restored the usable desktop. Restarting only the session
services raced session teardown and did not recover it reliably. Neither idle
lock recovery nor global service stability is considered validated. Do not
disable locking or change authorization policy without requester review.

The initial Ubuntu welcome assistant remains enabled and can open a native
privacy authorization dialog. No initial-setup choices are pre-accepted.
For the input validation only, its first-login user service was stopped in
that session without disabling it or changing privacy preferences.

### Repeated password prompts on first use

The welcome assistant repeatedly requested privacy authorization in another
first-use trial. Logs identified `gnome-initial-setup` requesting
`com.ubuntu.whoopsiepreferences.change`; GNOME's authentication agent also
logged an error. This occurred before Termia was installed.

For a temporary workaround, run this on the Docker host from the repository root:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop \
  runuser -u lab -- env XDG_RUNTIME_DIR=/run/user/1100 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus \
  systemctl --user stop gnome-initial-setup-first-login.service
```

This stops the assistant only for the current session. No authentication policy
is changed and no privacy choice is accepted. After stopping it, no new requests
were logged during a 20-second observation; the requester confirmed the desktop
was usable. This does not validate the next login or resolve the underlying fault.
A healthy container and a working Wayland/RDP connection alone do not establish
that first-use interactions or administrative authorization work.

## Optional updater laboratory — #428

Termia and its controls require this optional image; the base desktop does not
include them. Build the base desktop first, then run from the repository root:

```bash
git fetch origin fix/428-update-dependencies
git fetch origin tag v0.6.0-beta.3 tag v0.6.0-beta.4
bash tools/docker-lab/gnome26/prepare-updater.sh bc3abd444efb8065cf00607ff1ccb743e7ece5bf
docker compose -f tools/docker-lab/gnome26/compose.yaml -f tools/docker-lab/gnome26/compose.updater.yaml build desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml -f tools/docker-lab/gnome26/compose.updater.yaml up -d --no-build --wait --wait-timeout 120 desktop
```

Recreation interrupts RDP but preserves the existing profile and credentials.
Open **Laboratorio de pruebas de Termia** from the dock or GNOME's application grid. It provides
original Git beta.3, beta.3 with the proposed updater, Debian and restart modes.
Close Termia and use the panel's baseline reset between trials. That reset
changes packages and replaces only the synthetic checkout at /home/lab/source.
Use the displayed synthetic password for administrative authorization.

The fixture launch/reset scripts are exported individually; the GTK panel comes
from this laboratory.
The recovered GTK 4 panel and Termia use Wayland and GNOME's native polkit agent.
No terminal authentication agent or PAM/polkit rule is installed. Exported
updater code comes from the recorded commit; package digests are checked and
release transport uses local fixtures. These are beta.3 → beta.4 regression
trials, not a published maintenance release or a validated upgrade.
Each launch has a separate synthetic profile and log under
/home/lab/termia-updater-evidence, preserved in the profile volume.
Do not store personal data in this lab.
If first-use prompts recur, use the temporary workaround above. Verify native
authorization cancellation/acceptance, Git and Debian updates and restart
before treating the integration as validated.

### Current validation status

The GNOME Wayland/RDP desktop and the recovered compact GTK panel have been
exercised locally. The optional updater image installs the panel launcher and
pins it without replacing existing GNOME favorites. Trial profiles use XDG
variables for older Termia versions as well as the newer TERMIA variables.
This is an intermediate laboratory checkpoint, not a validated updater release.

Git/.deb end-to-end acceptance remains pending in #428. The source trial reached
beta.4 without GtkSourceView 5 and then failed to start. The Debian trial reported
that `gir1.2-gtksource-5` was not installable with its current package metadata.
The requested installer-layout and dependency-message improvements are also
pending in #428. Do not interpret a working desktop as a successful upgrade.

## Deployment and current limitations

Compose starts systemd as PID 1 with private cgroups, `SYS_ADMIN`, and
`apparmor=unconfined`; seccomp remains enabled and `privileged` is false.
The versioned `seccomp-desktop.json` comes from Moby profiles `seccomp/v0.1.0`
(commit `a33e0005c5fd43eba98562c826376cac2517e437`, Apache-2.0;
see `LICENSE.seccomp`). Its only policy addition is allowing `pivot_root`,
required by bubblewrap for Glycin image-loader sandboxes. Without it, icons
and the wallpaper fail to load. Glycin sandboxing remains enabled.
This permits another mount operation within the existing capability model;
review this profile when upgrading Docker rather than silently inheriting
new daemon defaults. RDP visual validation confirmed the wallpaper, dock icons
and desktop Home icon after this change.
The startup script remounts the existing private cgroup mount read-write.
There are no host bind mounts, host desktop/session sockets, Docker socket,
GPU devices or `/dev/kvm`. The host must provide the FUSE kernel interface
and `/dev/fuse`, mapped read-write for GNOME clipboard mounts. This is an experimental permission
configuration, not a demonstrated minimum or a fully hardened deployment.

GDM creates the individual `lab` headless session using its standard
`gdm-new-session` tool, called by a root service under GDM's existing policy.
The graphical session and GNOME Remote Desktop headless server run as `lab`.
The root helper stays alive to manage session shutdown. RDP authenticates
before granting desktop access; there is no separate GDM login screen. PAM
and polkit files are unchanged, and administrative actions still require the
synthetic user's password. GDM's dynamic-user greeter failed its account check
in the initial remote-login experiment; that path is not claimed as working.

Rendering uses `LIBGL_ALWAYS_SOFTWARE=1`. Limits are 2 CPUs, 4 GiB RAM,
4,096 processes/threads and 256 MiB shared memory. The earlier 1,024-process
limit gave the user slice only 337 tasks and exhausted it during GNOME startup.
The host must provide Linux cgroup v2 and permit the tested mount/capability
configuration; Linux amd64, Docker Engine 28.5.1 and Compose 2.40.0 were used.
No host service or kernel module is installed by these recipes. Rootless,
Docker Desktop, SELinux hosts and other architectures remain unvalidated.

Named volumes hold only the `lab` profile (including its runtime RDP TLS key)
and the generated password. `/run`, `/run/lock` and `/tmp` are temporary.
OS packages and service configuration live in the built image. Restarting a
container retains its generated credentials; removing the volumes resets them.

Observed limitations: Netplan/udev, colord, TPM and RealtimeKit have failed
units; logind logged an egress BPF attachment warning; an Ubuntu web-search
extension logged an error. They have not been suppressed. Declaring `/dev/fuse`
resolved the observed clipboard-negotiation abort; sustained clipboard data
transfer, file redirection, document portals, audio and native authorization acceptance remain
unvalidated. Do not add hardware or relax more permissions without review.

## Verification and teardown

The optional client runs FreeRDP on its own Xvfb display, which does not change
the server's Wayland backend or access the host desktop:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation build rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation up -d rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop loginctl list-sessions
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation logs --tail 30 rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation stop rdp-probe
```

The validation client reads the synthetic password volume read-only, drops all
capabilities, sets no-new-privileges, has no published ports and disables
clipboard. For this isolated test only, it accepts the self-signed certificate
with FreeRDP's `/cert:ignore`. The human Remmina template requires confirmation.

Observed: GNOME Shell logged that it was a Wayland display server using a
surfaceless renderer without GPU; logind reported a remote active Wayland user
session; a GTK probe returned `GdkWaylandDisplay`. RDP delivered an inspected
desktop image. Mouse/keyboard input typed `TERMIA_RDP_INPUT_OK_430` into the
standard Ubuntu text editor, saved via Ctrl+S, and the resulting file contained
exactly that marker. Client reconnection retained the session and the file.
These checks do not validate Termia or all desktop services.

The second runtime cycle removed this project's containers, network and all
data volumes, rebuilt using Docker's existing build cache and repeated the
Wayland/backend and RDP input/file checks successfully. New credentials were
generated and the old synthetic home-profile marker was absent. This verifies
reconstruction without private runtime data; a second uncached package download
has not been performed. The readiness healthcheck tests the session socket and
RDP listener only, not all Ubuntu services.

Stop this project or deliberately destroy its synthetic data with:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation stop
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation down --volumes
```

After `down --volumes`, repeat build/start to reconstruct from the recipes.
Images/build cache remain available; `down --volumes --rmi all` additionally
removes this Compose project's service images. No previous private lab is
targeted by these commands. Termia startup, remaining host/runtime limitations
and the final accepted deployment must be validated before closing #430.

## Observed base-image validation — 2026-10-28

The Linux amd64 build succeeded with Docker Engine 28.5.1. Image size was
3,228,534,874 bytes (3.007 GiB). All 1,510 package records had installed status;
`dpkg --audit` was empty and `apt-get --simulate check` succeeded. The embedded
inventory exactly matched a fresh query, with SHA-256
`afb1de6f3e7d5c45d85fa70f1b1e5a3315ffc2011bad0fa6095bdd2d9818d51d`.

Installed versions included `ubuntu-desktop` 1.570.4, GNOME Shell
50.1-0ubuntu1.4, GNOME Remote Desktop 50.2-0ubuntu0.1, Mutter 50.1-0ubuntu2.5,
systemd 259.9-0ubuntu0.1 and PipeWire 1.6.2-1ubuntu1.2. The inspection container
had a read-only filesystem, no network, mounts or added capabilities and was
automatically removed. No persistent volume or running desktop was created.
Snap payloads were absent. Eighteen existing laboratory infrastructure tests
passed; they do not validate the new image's graphical runtime.

## Observed systemd runtime probes — 2026-10-28

These temporary probes did not change the image or establish a supported
deployment. All used private cgroup namespaces, no network, no host mounts and
Docker's default seccomp policy. No `--privileged` container was used.

| Runtime configuration | Observation |
| --- | --- |
| Default Docker capabilities and AppArmor | systemd exited with read-only `/init.scope` cgroup creation failure |
| Add `SYS_ADMIN`, retain default AppArmor | Mounting and remounting cgroups were rejected |
| AppArmor unconfined, no added `SYS_ADMIN` | Remounting cgroups was rejected |
| Add `SYS_ADMIN`, AppArmor unconfined | Remounting the container's existing cgroup mount read-write and creating/removing a child cgroup succeeded |

With the last configuration, systemd ran as PID 1 using `basic.target`; D-Bus
and logind started successfully, and `systemd-run --wait --collect` completed a
`/usr/bin/true` service. The system was **degraded**: `netplan-configure.service`
failed because `udevadm` could not contact udev. logind also logged an egress BPF
attachment failure while remaining active. These were not suppressed or fixed.

`SYS_ADMIN` is a broad capability and removing AppArmor confinement weakens
isolation. This proves one working mechanism, not that these are the minimum
or final deployment permissions. The probes used no host cgroup bind mount;
the read-write remount was in the container's own cgroup/mount namespaces.
All probe containers were stopped/removed. GNOME, RDP and Termia were not
started. A narrower security policy, required service adjustments and the
actual desktop deployment still need review before implementation.

## Build inputs

- Official Docker Ubuntu 26.04 base, pinned to
  `sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78`.
- Ubuntu archive snapshot: `20261027T000000Z`, with `resolute`,
  `resolute-updates` and `resolute-security`; components `main`, `universe`,
  `restricted` and `multiverse`. Backports and third-party repositories are absent.
- Explicit packages: `ubuntu-desktop`, `gnome-remote-desktop`, `systemd-sysv`,
  `dbus` and `ca-certificates`, installed with their dependencies and recommends.
  This includes the full desktop metapackage and standard applications; no
  hand-selected lightweight desktop or custom package exclusions are used.
- The base lacks a TLS trust bundle. A separate build stage downloads the
  snapshot's `ca-certificates_20260223_all.deb` over HTTPS, checks its SHA-256
  (`f7025ab9b24cd73215510931037b02d6960d89584d0d00afba81851abdbe6ef1`),
  and extracts its public CA certificates without running maintainer scripts.
  APT uses that temporary bundle to verify HTTPS while installing the normal
  snapshot packages, including the snapshot's current CA package.
- APT retains Ubuntu archive signature and package hash verification.
  `Check-Valid-Until: no` applies to this fixed historical snapshot so later
  rebuilds can use it; it does not disable signatures or TLS verification.
- `.dockerignore` allowlists the Dockerfile, APT sources, initialization and
  RDP scripts, service units and rendering configuration needed by the image.
  The Compose-side seccomp profile and client template stay outside the build
  context. Application source, private runtime files and host configuration
  do not enter it.

Build instructions and the package snapshot are fixed; this is not a promise of
byte-identical layers. Package scripts can generate timestamps and machine state.
The image does not install Snap application payloads: transitional DEB packages
such as Firefox do not prove that the actual Snap application is installed.
Snap store content is outside the pinned APT snapshot.

## Requirements and commands

Run from the repository root using a local Linux Docker Engine with BuildKit,
Internet access to Docker Hub and `snapshot.ubuntu.com`, and sufficient disk for
the full desktop packages and Docker build layers. The validated build target is
`linux/amd64`. Other architectures, rootless Docker and Docker Desktop have not
been validated. No host APT packages, desktop session or private profile are used.

```bash
docker build --progress=plain --platform linux/amd64 --target base \
  --tag termia-lab-430-ubuntu26-base:local tools/docker-lab/gnome26
```

Inspect the installed packages without starting desktop services, giving the
temporary container no network, host mounts or added capabilities:

```bash
docker run --rm --network none --read-only --cap-drop ALL \
  termia-lab-430-ubuntu26-base:local \
  dpkg-query -W ubuntu-desktop gnome-shell gnome-session-bin ubuntu-session \
  gnome-remote-desktop systemd systemd-sysv dbus pipewire wireplumber

docker run --rm --network none --read-only --cap-drop ALL \
  termia-lab-430-ubuntu26-base:local \
  cat /usr/local/share/termia-lab/packages.tsv

docker image inspect termia-lab-430-ubuntu26-base:local
```

The image stores the sorted package/version/architecture/status inventory at
`/usr/local/share/termia-lab/packages.tsv` and snapshot ID at
`/usr/local/share/termia-lab/apt-snapshot`. APT indexes and downloaded package
archives are removed after installation. `DEBIAN_FRONTEND=noninteractive` is
limited to the build step, not set for future interactive package operations.

The base target's default command is `/bin/bash`. It declares no listening ports,
volumes, custom laboratory users or automatic GNOME/systemd startup. Building
and inspecting it does not start or replace any previous laboratory container.
Use the separate `desktop` target and Compose configuration for the prototype.

## Base-image boundaries and remaining deployment work

Docker containers share the Docker host's Linux kernel; they do not boot an
Ubuntu kernel. No QEMU/KVM, preinstalled VM disk or `/dev/kvm` is used. The base
build does not request GPU devices, host cgroups, a host session bus, a Wayland
socket, a Docker socket inside the container, or privileged execution.

The desktop target's current systemd/cgroup permissions, software rendering and
host limitations are documented above. Installed hardware/service packages do
not imply that all their kernel-dependent functions work in Docker.
Ubuntu's container service-start policy is retained during package installation;
it must not be mistaken for a booted desktop or tested authorization agent.

GNOME/Wayland, RDP image/input and fresh-volume reconstruction passed the
prototype checks above. Termia integration, its subsequent reconstruction and
the final accepted permission/service configuration remain pending. No fallback
to a VM, another compositor or the host desktop is part of this design.

## Updating and removing the base

To update dependencies, review the Ubuntu digest, snapshot date, bootstrap URL
and checksum together, rebuild, compare the package inventories and repeat the
relevant validation. A frozen snapshot does not receive security updates by
itself. Reconstruction depends on continued upstream availability; Ubuntu
currently states a snapshot retention intention of at least two years, not an
unlimited archive guarantee.

After the image is no longer needed, remove only its tag with:

```bash
docker image rm termia-lab-430-ubuntu26-base:local
```

The base target creates no persistent volume. Do not use broad Docker prune commands
or delete the existing private laboratory artifacts to rebuild this image.

References: [official Ubuntu image](https://hub.docker.com/_/ubuntu),
[Ubuntu snapshot service](https://snapshot.ubuntu.com/), and
[issue #430](https://github.com/buuuki/termia/issues/430).
