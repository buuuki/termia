# Persistent Ubuntu 24.04 GNOME laboratory

[Español](README.es.md) · [Català](README.ca.md)

Infrastructure for #459. Image construction, GNOME/Wayland login and RDP
image/input have been validated locally. This is separate from the X11/Weston
laboratory and XFCE VM. Existing Ubuntu 26 and older laboratories are retained.

## Requirements and resources

Linux amd64, local Docker Engine and Compose, cgroups v2, `/dev/fuse`, host
Python 3 and Git. No host tools are installed. Reserve space for the complete
desktop and image layers. The container uses 2 CPUs, 4 GiB RAM and 256 MiB
shared memory; localhost port 12389 must be free. Docker Desktop, rootless,
ARM and reproduction on a second host are unvalidated.

The image pins the Ubuntu 24.04 digest and APT snapshot, installing full
`ubuntu-desktop` with recommendations, GNOME Remote Desktop, EN/ES/CA language
support, native Firefox, Termia dependencies, Git, Xvfb, GDB and Valgrind.
Ruff, Bandit and Coverage use the repository's pinned requirements in an
in-image virtual environment. Building can download packages. Importing tools
or opening the desktop does not run tests or Termia upgrades.

APT selects versions from the signed snapshot indexes. It downloads up to eight
archives concurrently from Ubuntu's official archive, falling back to Snapshot,
and requires each file's SHA-256 from those indexes. Changing the download
server does not change the selected versions or accepted package bytes.

## Build and connect

From the repository root, with implementation files added to Git so the
snapshot includes them:

```bash
python3 tools/docker-lab/gnome24/lab.py start
remmina -c tools/docker-lab/gnome24/laboratory.remmina
```

`start` snapshots allowlisted tracked files, including local edits, builds with
cache and creates or updates the same `termia-459-gnome24` project. It rejects
remote Docker and resources owned by another checkout. Rebuilding can interrupt
RDP. Preparation/build failure leaves the existing desktop untouched. The
previous image is retained under a rollback tag; volumes are not deleted.

Connect to `127.0.0.1:12389`, user `lab`, empty domain. Retrieve the synthetic
password only when needed:

```bash
python3 tools/docker-lab/gnome24/lab.py password
```

The proposed GNOME 46 native remote-login flow authenticates RDP first and then
user `lab` in GDM using the same synthetic password. The client needs RDP
redirection; actual behavior must be verified during integration. Listener
health does not prove a working graphical session. Verify the local TLS
certificate fingerprint before accepting it:

```bash
docker exec termia-459-gnome24-desktop-1 openssl x509 -in /var/lib/gnome-remote-desktop/termia-tls/tls.crt -noout -sha256 -fingerprint
```

## Routine use and persistence

```bash
python3 tools/docker-lab/gnome24/lab.py status
python3 tools/docker-lab/gnome24/lab.py logs
python3 tools/docker-lab/gnome24/lab.py stop
python3 tools/docker-lab/gnome24/lab.py resume
```

`stop` retains the container and data; `resume` opens its existing image without
refreshing source. `start` prepares and verifies a new snapshot. The panel
shows its identity. There is no automatic removal or mandatory host-boot
restart. Preserve credentials, TLS and profiles before manual retirement or
recreation; never use a global cleanup.

Open **Termia testing laboratory** from applications. **Open Termia** reuses a
persistent laboratory profile; **New isolated trial** creates another profile
and retains logs. The panel also opens a terminal and runs the suite using a
private display/bus. Data lives under `~/termia-lab-evidence` in the `profile`
volume. Test temporaries use its executable directory rather than Docker's
`noexec` `/tmp`. Never enter real credentials.

The separate `profile`, `credentials` and `remote-state` volumes belong to this
project. No host desktop, home, SSH agent or Docker socket is mounted. Images
contain code snapshots/tools, not profiles/passwords. Language selection and
session restart should preserve preferences; verify this interactively.

## Privileges and pending validation

As in Ubuntu 26, this proposal uses `SYS_ADMIN`, per-container unconfined
AppArmor, private cgroups and the existing versioned `gnome26` seccomp profile.
It shares `/dev/fuse`, not a GPU, KVM or the host's complete cgroup tree. These
are broad permissions, not a minimal-isolation guarantee. PAM and polkit rules
are unchanged.

GNOME 46's configuration utility requires synthetic credentials in argv, briefly
visible to authorized container processes. The helper never logs the arguments,
credential-bearing exceptions or raw command output. Real passwords and generated
runtime data must never be published.

Ubuntu's Xorg entries remain installed because GDM 46 needs them to initialize
without a physical display. The validated remote session uses Wayland. Native
handover starts with the greeter and the user session. Only this laboratory
masks `org.gnome.SettingsDaemon.Sharing.service`: its Docker external connection
is not a primary connection for that manager, which otherwise stops RDP.
Automatic GNOME sharing management is disabled; native RDP remains active.

Locally validated: interactive RDP login, remote Wayland session, GTK panel,
Termia with a VTE terminal, and 819 automated tests. Interactive checks of every
language and Firefox are outside this validation. This does not certify a
Termia release.

The colord service retains its hardening except `PrivateUsers`, disabled to
avoid Docker startup failure 217/USER and GNOME RDP initialization delays.
No additional container capabilities are granted.

Observed GNOME 46 limitation: the first connection after recreation or startup
can time out during handover and show black. Let that connection finish, then
reconnect using the same RDP profile. The second connection allows login and
desktop use. `healthy` checks services and the listener, not this limitation.
