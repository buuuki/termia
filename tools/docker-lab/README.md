# Reproduce the Termia Docker laboratory

[Español](README.es.md) · [Català](README.ca.md)

Run the visual desktop, synthetic SSH/SFTP/SCP fixtures, memory diagnostics and
process-lifecycle tests from a fresh checkout. The source stays read-only inside
the client; the host desktop, SSH agent and personal Termia profile are not mounted.

## First start on another PC

Requirements: Linux, a local Docker Engine accessible to your user, Git,
Python 3, `ssh-keygen` (OpenSSH client), a browser, available port 6080 and
several GB of free disk/RAM. Zenity and `xdg-open` are optional for the manager.
The image runs Ubuntu 24.04. Builds download packages; runtime SSH networks are
internal. Windows/macOS and remote Docker daemons are not validated.

Until #377 is merged, use its publication branch. After merge, the active
release-development branch also contains the package.

```bash
git clone https://github.com/buuuki/termia.git
cd termia
git switch maintenance/377-docker-lab
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
