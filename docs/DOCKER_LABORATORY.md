# Docker laboratory: operation and investigation record

The local laboratory combines visual GTK/VTE trials, process lifecycle checks
and memory diagnostics without using a personal Termia profile. This document
records the environment and the findings promoted into beta.4, including the
sidebar and menu work in [#380](https://github.com/buuuki/termia/issues/380).

## What is available

The portable package is published under `tools/docker-lab/` through
[#377](https://github.com/buuuki/termia/issues/377). Start with its
[English](../tools/docker-lab/README.md),
[Spanish](../tools/docker-lab/README.es.md) or
[Catalan](../tools/docker-lab/README.ca.md) guide to reproduce it on another PC.
Credentials and results are generated locally and ignored; they are not part
of the published package.

The sections below preserve the investigation record of the earlier local
package. Its `.local` paths, fixed container names and archive provenance are
historical, not the installation instructions for the new portable package.
The portable version reads the checkout source and uses names derived from its
path, fresh build contexts and runtime-generated credentials.

| Component | Purpose |
| --- | --- |
| Ubuntu 24.04 image | Python, GTK 4, VTE, GtkSourceView, Paramiko and diagnostic tools |
| Xvfb and Openbox | Private X11 desktop and window management |
| Weston | Nested Wayland desktop; does not replace the host compositor |
| x11vnc, noVNC and websockify | Interactive browser view through loopback port 6080 |
| Desktop launch panel | Choose X11/Wayland, tracing, GDB and initial tab count |
| Zenity manager | Start, stop, inspect and restart laboratory components |
| GDB, Valgrind, tracemalloc and process sampling | Crash stacks, native allocation and Python lifetime investigations |
| OpenSSH fixtures | Synthetic password/key connections and file-transfer trials |

The image uses software rendering. Desktop tests can exercise X11 or Wayland;
the main visual session uses nested Wayland. Yaru supplies the icon theme.
Private desktop settings provide window minimize/maximize controls. Missing
icons and window buttons were corrected in the environment: application icon
overrides introduced during troubleshooting were reverted.

## Quick path in an existing local package

From the repository root, first confirm that the package exists:

```bash
test -f .local/termia-tabs-20261021/run.sh
bash .local/termia-tabs-20261021/run.sh status
bash .local/termia-tabs-20261021/run.sh tools check
```

Start the desktop, or open the graphical manager:

```bash
bash .local/termia-tabs-20261021/run.sh start
bash .local/termia-tabs-20261021/manage.sh
```

Open `http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale` and use
**Iniciar / nueva prueba** in the bottom panel. If Termia is already running,
close it normally before starting another trial. Source mounts are live, but
an existing Python process does not reload changed modules.

The manager supports restarting the whole container or only Weston, stopping
the container, viewing logs, monitoring memory and starting diagnostic modes.
Restarting Weston or stopping/restarting the desktop interrupts its sessions;
close them normally first. Cancelling a diagnostic uses its own resource
ownership checks and does not stop the manual SSH fixture.

## Isolation and source provenance

The visual container is `termia-tabs-checkpoint`. Its source is mounted from
the package's `source/src/termia` at `/opt/termia/src/termia`. This is a separate
copy from the checkout's `src/termia`: editing one does not update the other.
Diagnostic containers also need their source mount checked before interpreting
results. A passing test against a stale copy does not validate a PR.

Use the run's source fingerprint and actual mount paths, rather than an old
archive README or embedded base-commit marker, to identify what was executed.
The original package started from commit `2dd0e1d`; its later live source also
contains validated fixes promoted through #374 and #375. Historical statements
in the package describe the state when written, not necessarily its current
mounted source. Original archive checksums likewise do not certify later edits.

The manual SSH service (`termia-checkpoint-manual-ssh`) and diagnostic SSH
service (`termia-checkpoint-ssh`) use separate internal Docker networks.
Automated trials use their own client and generated configuration, so a user
can remain connected in the visual desktop. Only synthetic accounts, keys,
hosts and files belong in these fixtures. Seeded profiles support password and
key authentication and browsing/transferring test files with the image's
OpenSSH server. The password-profile connection problem was corrected in the
local fixture configuration and then confirmed interactively.

The desktop publishes noVNC on loopback. Diagnostic clients use read-only
mounts, temporary runtime directories and resource limits; networking is
disabled unless a mode needs its private SSH fixture. GDB tracing needs the
desktop's explicitly granted ptrace capability. These are laboratory choices,
not production application requirements.

## Diagnostic commands

All commands below require the local package and Docker. Run one diagnostic at
a time. `tools status` reports the job, manifest and result location; starting
a job is not proof it finished successfully.

```bash
bash .local/termia-tabs-20261021/run.sh tools status
bash .local/termia-tabs-20261021/run.sh tools monitor
bash .local/termia-tabs-20261021/run.sh tools stop monitor
bash .local/termia-tabs-20261021/run.sh tools run memory
bash .local/termia-tabs-20261021/run.sh tools stop diagnostic
```

Replace `memory` with a mode from this table:

| Mode | Checks |
| --- | --- |
| `lifecycle` | Managed local/SSH processes, terminal/split lifecycle, SFTP/SCP and shutdown scenarios |
| `memory` | Repeated session/file-transfer cycles and settled memory/object counts |
| `memory-trace` | Memory cycles with Python allocation tracing |
| `close-live` | Closing with live connections and transfer activity |
| `valgrind` | Native memory diagnostics; substantially slower |
| `menus` | Native menu object reuse and retained UI ownership |
| `churn-disabled`, `churn-enabled` | Repeated terminal creation/closure with optional tools off/on |
| `behavior-x11`, `behavior-wayland` | Pointer interaction and tab drag behavior on each backend |

`tools check` checks dependencies/imports only. `tools monitor` observes the
visual process; the diagnostic modes create separate trials. Results remain
under the package's `evidence/` directory, including manifests, source hashes,
structured observations and console output. Do not publish raw logs, profiles,
private keys, dumps or screenshots without reviewing their contents.

## Findings and changes retained

### Terminal tabs and unnecessary menu refreshes

The GTK Notebook trial and the custom laboratory tab strip were compared.
The requester retained the laboratory design: custom tab strip, native overlay
scrollbar that hides automatically, close buttons, private drag reordering and
the down-arrow overflow selector. A local source archive preserves the Notebook
alternative; it is not a runtime dependency or a public download.

Overflow-menu rebuilding during intermediate drag positions caused needless
work. The retained implementation reuses a native overflow menu and refreshes
it when opened. The selected design and ownership corrections were promoted in
[#374](https://github.com/buuuki/termia/issues/374) and
[PR #378](https://github.com/buuuki/termia/pull/378). Object-lifetime checks
cover retired signal handlers, pages, tab labels and VTE widgets while preserving
process-exit accounting. This is not a claim that every callback is redundant;
deferred cleanup candidates remain separate work.

### Memory and lifecycle laboratories

The earlier process lifecycle and memory probes were integrated into the local
Docker controller. Diagnosis distinguished allocator warm-up from genuinely
retained objects; stable RSS alone is insufficient evidence of correct cleanup.
Native weak references and Python references were inspected alongside managed
child identities, active workers, transfer results and settled memory.

SFTP investigation found two retention paths: UI/dialog signal ownership and
Paramiko's optional Invoke import exception retaining its traceback. The fixes
release windows after workers stop, disconnect native signals without calling
the SFTP action named `disconnect`, and clear only the known optional-import
traceback. They were promoted in
[#375](https://github.com/buuuki/termia/issues/375) and
[PR #379](https://github.com/buuuki/termia/pull/379).

That validation included 20 mixed cycles with 16 MiB file hash comparisons,
first-cycle SFTP collection, lifecycle scenarios and closing during an active
transfer. Zero surviving explorers after settled cycles is stronger evidence
than expecting RSS to return to an identical value. These observations validate
those synthetic scenarios, not every SSH server or a full release matrix.

### Sidebar and context menus

Connection groups and section headers now behave like Notes category headers:
clicking the content toggles expansion without making the header the selected
object. Keyboard selection skips headers. The existing compact, rounded
icon/text selection remains; scoped CSS removes the theme's pressed inset shadow.

Tab, server and group menus use GTK's native pointing arrow. GTK can reposition
it to fit the available space; it is not permanently fixed to the upper edge.
The main, tab, server, group and terminal menus clear the initial `SELECTED`
highlight once after opening, retaining subsequent keyboard navigation.

Leaving terminal Split/Tab submenus previously hid and reopened the root menu.
That looked like rebuilding even when the model was unchanged. The root now
owns outside-click dismissal, nested menus avoid separate autohide grabs, and
focus returns to their parent entry without restarting the root popover.

Real pointer/keyboard checks in the visible Wayland session exposed a focus
problem that programmatic menu activation had missed: Termia opened the menu,
then VTE's remaining click handling focused the terminal again. Disabling the
initial-highlight change did not remove that failure. Restoring menu focus on
idle, before clearing initial selection, corrected navigation in isolated full
windows and split panes; the requester then confirmed it interactively.

## Verification and limits

To validate a source checkout independently of the local Docker package:

```bash
python3 scripts/run_sandbox_tests.py
python3 -m py_compile run_termia.py scripts/compile_translations.py scripts/run_sandbox_tests.py src/termia/*.py tests/*.py
bash -n scripts/termia-setup.sh
scripts/compile_translations.py --check
scripts/run_test_instance.sh --fresh
```

Review [the regression checklist](REGRESSION_CHECKS.md) and
[the GTK inventory](GTK_CONTROLS.md). In the isolated app, right-click a tab,
server, group, terminal and split, release the button, navigate with Up/Down,
activate a harmless command with Enter and close with Escape. Enter/leave
Split and Tab using Right/Left; repeat outside-click dismissal after leaving a
submenu. Check the main menu with both its button and F10. Test real opening
gestures: calling `popup()` or activating a `GAction` alone does not reproduce
VTE's click/focus ordering.

No application version, storage schema, production SSH configuration or host
desktop settings are changed by the promoted UI fixes. They belong to the
planned beta.4 release; its full platform/install/upgrade validation remains a
separate release task. For upgrade-specific Docker work, see
[Docker upgrade validation](DOCKER_UPGRADE_VALIDATION.md).
