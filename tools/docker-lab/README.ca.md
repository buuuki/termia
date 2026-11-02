# Reproduir el laboratori Docker de Termia

[English](README.md) · [Español](README.es.md)

Aquest paquet reconstrueix l'escriptori visual, els servidors sintètics
SSH/SFTP/SCP i les proves de memòria i cicles de vida des d'un clon nou. El client
munta el codi en només lectura, sense l'escriptori, l'agent SSH ni el perfil
personal de Termia de l'amfitrió.

La [base independent Ubuntu 26.04 GNOME](gnome26/README.ca.md) s'està
construint a #430. L'escriptori experimental GNOME Wayland/RDP té comprovacions
funcionals; falten Termia i l'acceptació completa del laboratori.

## Primera arrencada en un altre PC

Cal Linux, Docker Engine local accessible per al teu usuari, Git, Python 3,
`ssh-keygen` (client OpenSSH), un navegador, el port 6080 lliure i diversos GB
de disc i RAM disponibles. Zenity i `xdg-open` són opcionals per al gestor.
La imatge utilitza Ubuntu 24.04. La construcció descarrega paquets; les xarxes
SSH d'execució són internes. No s'han validat Windows/macOS ni Docker remot.

Utilitza la branca activa de desenvolupament, que conté el laboratori publicat.

```bash
git clone https://github.com/buuuki/termia.git
cd termia
git switch release/0.6.0-beta.4-dev
docker info
bash tools/docker-lab/run.sh prepare
bash tools/docker-lab/run.sh check
bash tools/docker-lab/run.sh start
```

Obre l'adreça que imprimeix `start`, normalment
`http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale`.
El panell inferior inicia Termia amb 16 pestanyes locals i dues connexions SSH
sintètiques desades: contrasenya i clau. Permeten provar SSH, SFTP i enviament
de fitxers. La contrasenya generada es carrega automàticament; no cal copiar
contrasenyes ni claus del PC anterior. El servidor conté fitxers sintètics
a `/home/lab/pruebas`.

Tanca Termia normalment i prem **Iniciar / nueva prueba** per obtenir un perfil
nou. El panell permet triar Wayland/X11, pestanyes (1–40), traces i GDB opcional.
Els canvis de codi es carreguen en crear un procés nou. Si canvies scripts o
dependències del laboratori, executa `prepare`, atura i elimina el contenidor de
l'escriptori i torna'l a iniciar. Per usar un altre port en un escriptori nou:

```bash
LAB_PORT=6081 bash tools/docker-lab/run.sh start
```

## Gestionar l'escriptori

```bash
bash tools/docker-lab/manage.sh
```

El gestor Zenity opcional fa servir etiquetes comunes en anglès; el panell de
l'escriptori conserva les etiquetes en castellà. També pots utilitzar la consola:

| Ordre després de `bash tools/docker-lab/run.sh` | Resultat |
| --- | --- |
| `start`, `url` | Iniciar l'escriptori o mostrar-ne l'adreça |
| `status-desktop`, `logs` | Consultar els recursos del clon i el registre del contenidor |
| `restart` | Reiniciar el contenidor; interromp les seves sessions |
| `restart-wayland` | Reiniciar només Weston; interromp les aplicacions Wayland |
| `stop-desktop` | Aturar l'escriptori i el servidor SSH manual |
| `remove` | Eliminar l'escriptori aturat per utilitzar imatges reconstruïdes |
| `monitor`, `stop monitor` | Iniciar/aturar l'observació passiva de memòria |
| `cleanup` | Eliminar contenidors/xarxes propis; conservar imatges, credencials i resultats |

Tanca les sessions abans de reiniciar o aturar. Les operacions comproven la
propietat dels recursos i no fan una neteja general de Docker. Cada ruta de clon
té noms diferents; aquest paquet no toca el laboratori antic del directori ignorat.

## Executar un assaig

Executa un únic diagnòstic alhora. Aquest exemple inicia la feina en segon pla i
espera el resultat final; iniciar-la no demostra que hagi passat.

```bash
bash tools/docker-lab/run.sh run ssh-smoke
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh status
```

| Mode | Prova |
| --- | --- |
| `smoke-x11`, `smoke-wayland` | Arrencada, creació/selecció/tancament de terminals i neteja de processos |
| `ssh-smoke` | SSH amb contrasenya i clau, comparació de pujada/baixada SFTP i neteja |
| `lifecycle` | Tancament de panells, pestanyes, finestres i aplicació; cancel·lació SCP/SFTP actius |
| `memory`, `memory-trace` | 20 cicles mixtos, hashes, RSS/memòria privada i referències febles; tracemalloc opcional |
| `close-live` | Tancament amb el botó natiu i SSH/SFTP amb una pujada activa |
| `menus` | 300 obertures del mateix menú natiu de pestanyes |
| `churn-disabled`, `churn-enabled` | 20 cicles de terminals amb eines opcionals desactivades/activades |
| `behavior-x11`, `behavior-wayland` | Arrossegaments i cancel·lacions amb esdeveniments del ratolí |
| `valgrind` | Diagnòstic d'assignacions natives; molt més lent |

Les ordres existents `churn-disabled` i `churn-enabled` utilitzen X11. Per
provar ambdós casos com a clients Wayland sobre Weston aïllat:

```bash
bash tools/docker-lab/run.sh run churn-disabled-wayland
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh run churn-enabled-wayland
bash tools/docker-lab/run.sh wait
```

Comprova al `result.json` de cada sonda que `runtime.display` sigui
`GdkWaylandDisplay`, `completed` sigui true, `retention_detected` sigui false i
`cleanup.running_children` sigui zero. Revisa les mostres de memòria; acabar
no demostra absència de fuites. Weston s'executa sobre Xvfb privat; aquestes
proves no cobreixen GNOME/Mutter. Compara memòria dins del mateix entorn i cas.

Per fer una prova curta de memòria, o cancel·lar el diagnòstic d'aquest clon:

```bash
LAB_MEMORY_CYCLES=1 bash tools/docker-lab/run.sh run memory
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh stop diagnostic
```

Els diagnòstics utilitzen client i servidor independents de les connexions SSH
manuals. Els resultats són a `.runtime/evidence/`, al costat d'aquesta guia:
els manifests indiquen empremtes del codi, dates, finalització/cancel·lació i
registres. Revisa també `result.json` i les mostres de cada mode. Acabar no
certifica l'absència de fuites: comprova objectes retinguts, treballadors i
connexions, i distingeix l'escalfament de l'assignador i el cost de les traces
de la retenció real. Els experiments de GC/assignador són diagnòstics, no correccions de producció.

## Privacitat, reconstrucció i límits

`prepare` crea contextos nous amb una llista de fitxers permesos. Només hi entren
el codi/recursos de l'aplicació seguits per Git i els scripts indicats del
laboratori. La imatge del servidor conté scripts, sense credencials. Les claus
i contrasenyes sintètiques es generen localment en preparar/iniciar i es munten
durant l'execució. `.runtime/` està ignorat. No cal publicar ni traslladar a
l'altre PC imatges, claus, perfils, bolcats, registres, captures ni arxius històrics.

Els resultats poden contenir rutes locals i allò que escriguis al laboratori;
mantén-los privats i utilitza dades sintètiques. noVNC escolta només a loopback
i no té autenticació: no publiquis el port. El client utilitza el teu UID numèric,
arrel de només lectura, directori personal temporal, renderització per programari
i límits de recursos. El client visual permet ptrace per a GDB, sense mode
privilegiat ni sòcol de Docker.
L'escriptori visual utilitza el pont normal de Docker per al port local del
navegador i una xarxa interna addicional per a SSH. Els clients de diagnòstic
utilitzen només la xarxa SSH interna, o cap xarxa a les proves exclusivament visuals.

Els repositoris Ubuntu no estan fixats a una instantània: reconstruir pot canviar
GTK/VTE. L'escriptori registra versions de paquets i empremtes del codi. Es
reprodueix el muntatge, no una imatge idèntica bit a bit ni una certificació de
release. Els assaigs llargs i les actualitzacions dels sistemes compatibles
necessiten validació independent. Consulta el [registre d'investigació](../../docs/DOCKER_LABORATORY.md)
i les [comprovacions de regressió](../../docs/REGRESSION_CHECKS.md).

Si falla l'arrencada, revisa `status-desktop`, `logs` i `.runtime/evidence/desktop`.
Si fallen els permisos de Docker, corregeix l'accés al dimoni local abans de
reintentar-ho; evita alternar execucions com a root i com a usuari al mateix directori de resultats.

## VM Ubuntu observable: sudo i polkit reals

Per observar la instal·lació i l'actualització amb autorització real del sistema,
utilitza la VM opcional Ubuntu 24.04 amb XFCE/X11. El laboratori Docker anterior
continua disponible per a les proves lleugeres X11 i Wayland.

Requisits: Linux x86-64, `/dev/kvm` utilitzable, Docker local, Python 3, navegador,
port 6081, 4 GB de RAM disponibles i 15 GB de disc. La preparació descarrega la
imatge oficial d'Ubuntu, verifica SHA256SUMS per HTTPS i descarrega el paquet
beta.3 amb hash fixat. L'escriptori inicial necessita Internet. No s'instal·len
paquets ni s'utilitza la sessió gràfica de l'amfitrió.

Des de l'arrel del repositori:

```bash
python3 tools/docker-lab/vm.py prepare
python3 tools/docker-lab/vm.py start
python3 tools/docker-lab/vm.py status
```

Obre l'URL que imprimeix `start`, normalment
`http://127.0.0.1:6081/vnc.html?autoconnect=1&resize=scale`.
Espera a veure el tauler XFCE; la preparació pot trigar uns minuts.
`status` mostra el progrés fins a `DESKTOP_READY`. El tauler mostra la contrasenya
sintètica generada per a la VM. Quan l'estiguis observant, habilita les proves:

```bash
python3 tools/docker-lab/vm.py ready
```

Prem els sis botons del tauler en ordre. Al primer espera la petició de
contrasenya sudo i cancel·la amb Ctrl+C. Al segon introdueix la contrasenya de
la VM. El tercer verifica el paquet candidat. Al quart cancel·la el diàleg
gràfic d'autorització; al cinquè autoritza'l amb la contrasenya de la VM.
El sisè comprova connexions, grups, snippets, notes i la còpia de seguretat.
No canviïs les dades sintètiques ni iniciïs una altra prova mentre n'hi hagi una
activa. També pots enviar cada fase des de la terminal, esperant-ne el resultat
abans de continuar:

```bash
python3 tools/docker-lab/vm.py trial source-cancel
python3 tools/docker-lab/vm.py trial source-accept
python3 tools/docker-lab/vm.py trial debian-prepare
python3 tools/docker-lab/vm.py trial debian-cancel
python3 tools/docker-lab/vm.py trial debian-accept
python3 tools/docker-lab/vm.py trial verify
python3 tools/docker-lab/vm.py show
python3 tools/docker-lab/vm.py evidence
```

Exigeix `running: false` i `passed: true` al JSON de cada fase; iniciar una prova
no significa superar-la. Els resultats es guarden a la VM sota
`/home/lab/termia-lab-evidence`; `evidence` exporta un arxiu i una captura a
`.runtime/visible-vm/results`. `guest /bin/cat /home/lab/termia-lab-evidence/state.json`
consulta l'estat. `guest` utilitza l'agent local de QEMU, sense SSH; una ordre que
superi 45 segons pot continuar executant-se i cal inspeccionar-la abans de repetir-la.

```bash
python3 tools/docker-lab/vm.py stop
python3 tools/docker-lab/vm.py remove
```

Els discos i les evidències es conserven. Després d'aturar i treure el contenidor,
mou `.runtime/visible-vm` a una altra destinació abans de preparar una VM nova.
No se sobreescriu un laboratori preparat ni es netegen recursos aliens.
Utilitza `start --port 6082` si necessites un altre port local.

És un assaig beta.3 → beta.4 local: només canvia la versió en una còpia temporal,
sense publicar releases ni tags. La descàrrega candidata utilitza una fixture
local; resta validar l'artefacte final i la descàrrega pública. No certifica
Ubuntu 26.04 ni Wayland. Només es copien fitxers versionats permesos, incloent-hi
els canvis actuals. Discos, contrasenyes, dades i captures queden ignorats.
Utilitza només dades sintètiques i no exposis el visor, que no té autenticació.
El contenidor rep únicament el directori d'execució i `/dev/kvm`, amb recursos
limitats i sense capacitats, sòcol Docker ni perfil personal. Les imatges i els
repositoris APT no són instantànies fixades.
