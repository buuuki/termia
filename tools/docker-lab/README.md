# Reproduce the Termia Docker laboratory

[Español](README.es.md) · [Català](README.ca.md)

Run the visual desktop, synthetic SSH/SFTP/SCP fixtures, memory diagnostics and
process-lifecycle tests from a fresh checkout. The source stays read-only inside
the client; the host desktop, SSH agent and personal Termia profile are not mounted.

The separate [Ubuntu 26.04 GNOME base](gnome26/README.md) is being built in
issue #430. Its experimental GNOME Wayland/RDP desktop has functional checks;
Termia integration and full laboratory acceptance remain pending.

## First start on another PC

Requirements: Linux, a local Docker Engine accessible to your user, Git,
Python 3, `ssh-keygen` (OpenSSH client), a browser, available port 6080 and
several GB of free disk/RAM. Zenity and `xdg-open` are optional for the manager.
The image runs Ubuntu 24.04. Builds download packages; runtime SSH networks are
internal. Windows/macOS and remote Docker daemons are not validated.

Use the active release-development branch, which contains the published laboratory.

```bash
git clone https://github.com/buuuki/termia.git
cd termia
git switch release/0.6.0-beta.4-dev
docker info
bash tools/docker-lab/run.sh prepare
bash tools/docker-lab/run.sh check
bash tools/docker-lab/run.sh start
```

Open the URL printed by `start`, normally
`http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale`.
The bottom panel launches Termia with 16 local tabs and two synthetic saved SSH
connections (password/key). Use them for SSH, SFTP and file-transfer checks.
The generated password is seeded automatically; no password/key needs copying
from the original PC. The server contains synthetic files under `/home/lab/pruebas`.

Close Termia normally and press **Iniciar / nueva prueba** for a fresh profile.
Choose Wayland/X11, tab count (1–40), tracing and optional GDB in the panel.
Source changes are loaded by a new process. Run `prepare` after changing the
laboratory scripts/dependencies, then stop and remove the old desktop before
starting it again. To avoid a port conflict for a new desktop:

```bash
LAB_PORT=6081 bash tools/docker-lab/run.sh start
```

## Manage the desktop

```bash
bash tools/docker-lab/manage.sh
```

The optional Zenity manager uses shared English action labels; the desktop
panel retains its Spanish labels. Its commands are also available without a GUI:

| Command after `bash tools/docker-lab/run.sh` | Result |
| --- | --- |
| `start`, `url` | Start the desktop or print its browser address |
| `status-desktop`, `logs` | Inspect this checkout's resources and container log |
| `restart` | Restart the desktop container; interrupts its sessions |
| `restart-wayland` | Restart only Weston; interrupts Wayland applications |
| `stop-desktop` | Stop the desktop and its manual SSH fixture |
| `remove` | Remove a stopped desktop so the next start uses rebuilt images |
| `monitor`, `stop monitor` | Start/stop passive memory sampling of the visual app |
| `cleanup` | Remove owned containers/networks; retains images, credentials and results |

Close active sessions before restart/stop. Commands guard resource ownership;
they never use a broad Docker prune. Different checkout paths have different
resource names, so this package does not touch the earlier ignored laboratory.

## Run a diagnostic

Run one diagnostic at a time. The following starts a background job and then
waits for its final manifest; merely starting a job is not a passing result.

```bash
bash tools/docker-lab/run.sh run ssh-smoke
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh status
```

| Mode | Workload |
| --- | --- |
| `smoke-x11`, `smoke-wayland` | Map the app, open/select/close local terminals, check child cleanup |
| `ssh-smoke` | Password and key SSH authentication, SFTP upload/download comparison and cleanup |
| `lifecycle` | SSH panes/tabs/detached/app closure and active SCP/SFTP cleanup |
| `memory`, `memory-trace` | 20 mixed cycles, file hashes, RSS/private memory and weak references; optional tracemalloc |
| `close-live` | Native titlebar close with live SSH/SFTP and an active upload |
| `menus` | 300 openings of the same native overflow menu |
| `churn-disabled`, `churn-enabled` | 20 terminal cycles, optional tools off/on |
| `behavior-x11`, `behavior-wayland` | Repeated pointer drags and cancellations |
| `valgrind` | Native allocation diagnostics; much slower |

The existing `churn-disabled` and `churn-enabled` commands use X11. To run
both workloads as Wayland clients on isolated Weston:

```bash
bash tools/docker-lab/run.sh run churn-disabled-wayland
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh run churn-enabled-wayland
bash tools/docker-lab/run.sh wait
```

Check `runtime.display` is `GdkWaylandDisplay` in each probe's `result.json`,
`completed` is true, `retention_detected` is false and `cleanup.running_children`
is zero. Review the memory samples; completion alone does not prove no leaks.
Weston is nested on private Xvfb; these runs do not test GNOME/Mutter.
Compare memory within the same backend and workload.

For a short memory trial, or to cancel this checkout's current diagnostic:

```bash
LAB_MEMORY_CYCLES=1 bash tools/docker-lab/run.sh run memory
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh stop diagnostic
```

Diagnostics have separate client/server resources from manual SSH sessions.
Results are under `.runtime/evidence/` beside this guide: manifests identify
source hashes, timestamps, completion/cancellation and logs. Look at the mode's
`result.json` and samples as well as the manifest. Completion is not proof of
zero leaks: check retained objects, workers and connections, and distinguish
allocator warm-up and tracing overhead from actual retention. GC/allocator
experiments in probes are diagnostics, not production fixes.

## Privacy, rebuilding and limits

`prepare` creates fresh allowlisted build contexts. Only tracked application
source/assets and named laboratory scripts enter the client context. The server
image contains scripts, not credentials. New synthetic credentials and host
keys are generated locally at prepare/start; runtime mounts provide them to
the isolated fixtures. `.runtime/` is ignored. No image, key, profile, dump,
log, screenshot or historical archive needs committing or copying to another PC.

Raw results can contain local paths and anything typed into the laboratory;
keep them private and use only synthetic data. The noVNC port is loopback-only,
without authentication: keep it on the local PC and do not expose it publicly.
The client runs as your numeric UID with a read-only root, temporary home,
software rendering and bounded resources. The visual client grants ptrace for
optional GDB; it does not run privileged or receive the Docker socket.
The visual desktop uses Docker's ordinary bridge for its loopback browser port
and an additional internal SSH network. Diagnostic clients use only their
internal SSH network, or no network for visual-only trials.

Ubuntu package repositories are not pinned snapshots: a rebuild can have newer
GTK/VTE packages. The desktop records package versions and source fingerprints.
This is a reproducible setup, not a bit-identical image or release certification.
Long diagnostic modes and all supported OS upgrades still require their own
validation. See [the investigation record](../../docs/DOCKER_LABORATORY.md) and
[regression checks](../../docs/REGRESSION_CHECKS.md).

If startup fails, inspect `status-desktop`, `logs` and `.runtime/evidence/desktop`.
If Docker permissions fail, fix access to the local daemon before retrying;
avoid alternating root/user runs against the same runtime directory.

## Observable Ubuntu VM: real sudo and polkit

The Docker desktop above remains the lightweight X11/Wayland diagnostic lab.
For interactive OS authorization and installation/upgrade validation, use the
optional Ubuntu 24.04 VM with XFCE/X11 and its observable test panel.

Requirements: local Linux x86-64, usable `/dev/kvm`, local Docker Engine, Python 3,
a browser, port 6081, at least 4 GB available RAM and 15 GB available disk.
Prepare downloads the official Ubuntu cloud image (verified against its HTTPS
SHA256SUMS), the pinned official beta.3 Debian package, and APT dependencies.
The guest also needs Internet access for its initial desktop installation.
Only the VM receives package changes; no host APT or desktop session is used.

From the repository root:

```bash
python3 tools/docker-lab/vm.py prepare
python3 tools/docker-lab/vm.py start
python3 tools/docker-lab/vm.py status
```

Open the URL printed by `start`, normally
`http://127.0.0.1:6081/vnc.html?autoconnect=1&resize=scale`.
Guest initialization can take several minutes; `status` reports its bootstrap
log until `DESKTOP_READY`. The XFCE panel displays a generated synthetic VM
password. Trials stay paused until the observer sees that panel and runs:

```bash
python3 tools/docker-lab/vm.py ready
```

Use the panel buttons in numbered order. For stages 1 and 2, wait for the actual
sudo password prompt; cancel stage 1 with Ctrl+C, and enter the displayed VM
password for stage 2. Stage 3 checks the local candidate using beta.3's actual
updater. Cancel the graphical authorization in stage 4; authorize it with the VM
password in stage 5. Stage 6 verifies preserved synthetic groups, servers,
snippets and notes plus the legacy Notes backup. Do not edit the synthetic
profile or start another trial while a trial is running.

Equivalent commands queue a trial in the logged-in desktop (they do not bypass
authorization):

```bash
python3 tools/docker-lab/vm.py trial source-cancel
# Complete the visible prompt and inspect status before each following command.
python3 tools/docker-lab/vm.py trial source-accept
python3 tools/docker-lab/vm.py trial debian-prepare
python3 tools/docker-lab/vm.py trial debian-cancel
python3 tools/docker-lab/vm.py trial debian-accept
python3 tools/docker-lab/vm.py trial verify
python3 tools/docker-lab/vm.py show
python3 tools/docker-lab/vm.py evidence
```

Per-stage JSON results and console logs are in the guest's
`/home/lab/termia-lab-evidence`. `evidence` exports an archive and desktop PNG
under `.runtime/visible-vm/results`. A started command or `running: true` is
not a passing test: require `running: false` and `passed: true` for each stage.
`guest /bin/cat /home/lab/termia-lab-evidence/state.json` reads the current
result; `guest` runs commands locally through QEMU's guest agent, never SSH.
A guest command times out after 45 seconds and may continue in the VM; inspect
its processes before retrying a long command.

```bash
python3 tools/docker-lab/vm.py stop
python3 tools/docker-lab/vm.py remove
```

Stop before removing the owned container. Disks and evidence are retained.
After stop/remove, archive or move `.runtime/visible-vm` out of that path before
preparing a fresh VM. A prepared runtime is not silently overwritten. No broad
Docker cleanup is used. `start --port 6082` selects another loopback port.

This is a beta.3 → local beta.4 rehearsal. Only a temporary source copy receives
candidate version metadata; no Git tags or releases are created. Candidate
transport is a local fixture; this does not certify a public GitHub download,
the final release artifact, Ubuntu 26.04 or Wayland. Source snapshots use named
tracked regular files, including current edits; VM disks, passwords, profiles,
logs and screenshots remain ignored. Keep all data synthetic. The browser port
has no authentication and must remain local. The container receives only the
runtime mount and `/dev/kvm`, with bounded RAM/CPU, no capabilities and no Docker
socket or personal profile. Images and APT repositories are not pinned snapshots.
