# Draft updater preview — issue #428

This is an **unvalidated interactive preview**, published at the requester's
explicit request before end-to-end validation. It is not release evidence.
Requires local Linux Docker, Python 3, Internet for preparation/APT and port 6084.
Do not use a remote Docker daemon or expose the viewer beyond loopback.

From this branch, prepare and start:

```bash
python3 tools/docker-lab/upgrade-preview/prepare.py
docker build -t termia-updater-428:preview tools/docker-lab/.runtime/upgrade-preview/context
docker run -d --init --name termia-updater-428 --memory 3g --cpus 3 --pids-limit 512 --shm-size 256m -p 127.0.0.1:6084:6080 termia-updater-428:preview
```

Open <http://127.0.0.1:6084/vnc.html?autoconnect=1&resize=scale>.
The container has no host home, desktop session, SSH agent, Docker socket or
writable host mount. Only packages inside the disposable container change.
The build starts from Ubuntu 24.04 and the checksum-verified official beta.3
package, without GtkSourceView 5. Preparation exports tracked application files
only; its build context stays under ignored `.runtime/`. No local credentials
are exported. Preparation refuses to overwrite an existing context. Fixture downloads use
Termia's HTTPS-only official-host redirect policy and retain the pinned SHA-256
checks. Preview tools use absolute executable paths; this does not rebuild or
change an already-running laboratory.

Each trial keeps its logs in a uniquely allocated directory beneath
`/tmp/upgrade-evidence`, with private `0700` permissions even when the process
has a permissive umask. The panel reports its directory name, and earlier trial
logs remain available for inspection.

Original mode makes its status text selectable and uses 16-pixel content insets
for manual copying and layout review. These presentation adjustments do not
change the historical updater, requirement handling or installation behavior.

The panel displays a generated **synthetic** password for `lab`. The terminal
polkit agent requests that password for assisted APT; another terminal is
available for manual commands. Container polkit/session integration still needs
validation. If authorization does not work, retain the logs and use the manual
option; do not treat it as a validated assisted-installation test.

1. Choose **Git beta.3 original**. In Termia, open the main menu, About, Check
   for updates and install beta.4. This should reproduce the original behavior:
   Git advances without installing GtkSourceView. Close Termia and choose
   **Reiniciar desde código actualizado**; inspect its failure log.
2. Close Termia and choose **Restaurar beta.3 y quitar GtkSourceView**. Enter
   the panel password and wait for reset to complete.
3. Choose **Git beta.3 + actualizador propuesto**. Repeat the update check.
   The new dialog should identify Git, show GtkSourceView as new/missing, warn
   that startup will fail without it, and offer assisted/manual installation.
4. For manual mode, copy its commands and run them in **Abrir terminal para
   comandos manuales**. Before installing, Check and continue must keep the
   update pending. After installation, it should permit the update.
5. Reset between tests. Check assisted acceptance/cancellation and the **Paquete
   .deb + actualizador propuesto** mode. For .deb, APT resolves dependencies
   with the package transaction; check the final version and dependencies.

Modes 2/3 load only the proposed updater boundary over beta.3. They do **not**
claim that an unchanged beta.3 client contains the new behavior. Transport uses
local fixtures with official beta.4 package bytes and Git tags; no release is
published or fetched through the UI. The Git fetch runner redirects the fixed
upstream URL to the local bundle, while retaining actual updater logic.
Each launch has a separate synthetic profile. The target is beta.4 for this
regression test, not publication of the future maintenance release.

Inspect logs or stop the container:

```bash
docker logs termia-updater-428
docker exec termia-updater-428 find /tmp/upgrade-evidence -name console.log
docker stop termia-updater-428
```

Existing beta.4 clients still require the documented manual transition to the
future maintenance release. This preview does not repair already-installed clients.
