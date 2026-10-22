# Reproduir el laboratori Docker de Termia

[English](README.md) · [Español](README.es.md)

Aquest paquet reconstrueix l'escriptori visual, els servidors sintètics
SSH/SFTP/SCP i les proves de memòria i cicles de vida des d'un clon nou. El client
munta el codi en només lectura, sense l'escriptori, l'agent SSH ni el perfil
personal de Termia de l'amfitrió.

## Primera arrencada en un altre PC

Cal Linux, Docker Engine local accessible per al teu usuari, Git, Python 3,
`ssh-keygen` (client OpenSSH), un navegador, el port 6080 lliure i diversos GB
de disc i RAM disponibles. Zenity i `xdg-open` són opcionals per al gestor.
La imatge utilitza Ubuntu 24.04. La construcció descarrega paquets; les xarxes
SSH d'execució són internes. No s'han validat Windows/macOS ni Docker remot.

Mentre #377 estigui pendent de fusió, utilitza la branca de publicació. Després
de fusionar-la, el paquet també serà a la branca activa de desenvolupament.

```bash
git clone https://github.com/buuuki/termia.git
cd termia
git switch maintenance/377-docker-lab
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
