# Laboratori Ubuntu 26.04 GNOME: escriptori experimental

[English](README.md) · [Español](README.es.md)

La issue #430 disposa d'un prototip funcional de GNOME sobre Wayland amb RDP,
executat directament amb Docker. Termia i el panell encara no estan integrats.
Les personalitzacions, optimitzacions i mesures d'aïllament següents es
revisaran amb el sol·licitant. El laboratori continua incomplet.

## Reconstrucció en un altre PC i límits de portabilitat

Les receptes reconstrueixen el sistema sense exportar una imatge, importar un
disc ni instal·lar manualment Ubuntu en un volum. A data 2026-10-28, els canvis
continuen en desenvolupament a la branca `maintenance/430-docker-gnome`.
Cal utilitzar aquesta branca i registrar el commit escollit; `main` no conté
aquest desplegament. No s'ha validat encara la reconstrucció en un
segon PC ni una segona descàrrega sense memòria cau.

```bash
git clone --branch maintenance/430-docker-gnome --single-branch https://github.com/buuuki/termia.git
cd termia
git rev-parse HEAD
```

| Requisit de l'amfitrió | Estat o motiu |
| --- | --- |
| Linux x86-64 i Docker Engine local amb permisos suficients | Provat amb kernel 6.8, Engine 28.5.1, Compose 2.40.0, cgroups v2 i driver systemd |
| Cgroups privats amb escriptura | El systemd del contenidor depèn del kernel i dels permisos del runtime |
| FUSE al kernel i `/dev/fuse` | Necessaris per als muntatges de GNOME; no s'instal·la ni carrega cap mòdul de l'amfitrió |
| Política de seguretat compatible | `SYS_ADMIN`, AppArmor sense confinament per al contenidor i seccomp versionat; revisar les restriccions del nou amfitrió |
| Recursos disponibles | Límits de l'escriptori: 2 CPU, 4 GiB RAM i 256 MiB de memòria compartida; reservar marge per a l'amfitrió i les capes de construcció |
| Xarxa i port | Descàrregues de Docker Hub i de la instantània Ubuntu; port local 13389 lliure |
| Client gràfic | Remmina amb GFX provat; no es comparteixen GPU ni sessió gràfica de l'amfitrió |
| Windows, macOS, ARM, Docker Desktop, rootless o SELinux | Sense validar; no se'n garanteix la compatibilitat |

Comprovacions prèvies des de l'arrel del clon:

```bash
uname -m
uname -r
docker version
docker compose version
docker info --format 'architecture={{.Architecture}} cgroups={{.CgroupVersion}} driver={{.CgroupDriver}}'
test -c /dev/fuse && ls -l /dev/fuse
docker compose -f tools/docker-lab/gnome26/compose.yaml config --quiet
```

Systemd, GDM, D-Bus, GNOME Shell i GNOME Remote Desktop pertanyen a la imatge.
No es connecten al D-Bus ni a la sessió gràfica de l'amfitrió. Docker comparteix
el seu kernel Linux; no reprodueix el kernel ni l'arrencada d'una ISO d'Ubuntu.
Si falten requisits cal revisar l'amfitrió, sense substituir-lo per QEMU/KVM.

Amb les receptes disponibles al nou PC, construir i arrencar:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml build desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop cat /var/lib/termia-lab/password
```

| Dada de connexió | Valor |
| --- | --- |
| Protocol | RDP |
| IP des del mateix amfitrió Docker | `127.0.0.1` |
| Port | `13389` |
| Login | `lab` |
| Password | Generat; consultar l'ordre anterior a cada instal·lació |
| Domini | Buit |
| Resolució i gràfics | 1440 × 900, GFX (`colordepth=63` a Remmina) |

`127.0.0.1` correspon al PC on s'obre el client. El port només es publica a
loopback: posar la IP LAN del servidor des d'un altre equip no hi dona accés
amb aquest Compose. El certificat és propi de cada perfil; verificar-ne
l'empremta en connectar, especialment després d'eliminar volums.

Reconstruir de zero conserva la configuració declarativa però genera una altra
contrasenya, una clau TLS nova i un perfil buit. Conservar les dades requereix
copiar i restaurar **tots dos** volums (`profile` i `credentials`) amb el
contenidor aturat i preservant permisos i propietaris. Contenen dades i secrets:
no es desen a Git. La migració de volums a un altre amfitrió continua sense
validar i no és necessària per reconstruir el sistema. No utilitzar
`down --volumes` si es volen conservar les dades.

## Mapa de configuració i operació

| Fitxer | Responsabilitat |
| --- | --- |
| `Dockerfile`, `ubuntu.sources`, `.dockerignore` | Base, paquets fixats, etapes i context permès |
| `compose.yaml` | Recursos, aïllament, FUSE, port i volums |
| `init.sh`, `termia-lab.target` | Cgroups privats i arrencada de systemd |
| `termia-lab-rdp.service`, `configure-rdp.py` | Usuari sintètic, credencials i configuració TLS/RDP |
| `termia-lab-session.service`, `after-rdp.conf` | Sessió Wayland creada per GDM i ordre d'arrencada |
| `termia-lab-user-rdp.service` | Configuració del servidor RDP dins de la sessió |
| `rendering.conf` | Renderització per programari |
| `seccomp-desktop.json`, `LICENSE.seccomp` | Perfil seccomp, permís `pivot_root` i llicència d'origen |
| `laboratory.remmina` | Perfil humà sense contrasenya desada |
| `rdp-probe.sh` | Client opcional aïllat per validar RDP |

Consultar l'estat sense modificar-lo:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml ps
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop systemctl --failed --no-pager
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop journalctl -b --no-pager _COMM=gnome-shell -n 60
```

Si el bloqueig per inactivitat deixa la imatge negra, la recuperació provada
interromp la sessió però conserva els volums i les credencials:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml restart desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
```

Això no resol el bloqueig. Els apartats següents distingeixen el que s'ha
validat, els errors observats i els requisits pendents abans del commit final
i de considerar acceptat el laboratori.

## Arrencar i connectar

Des de l'arrel del repositori:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml build desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop cat /var/lib/termia-lab/password
install -Dm600 tools/docker-lab/gnome26/laboratory.remmina tools/docker-lab/.runtime/gnome26.remmina
remmina -c tools/docker-lab/.runtime/gnome26.remmina
```

RDP a `127.0.0.1:13389`, usuari `lab`, resolució 1440 × 900. Introdueix la
contrasenya sintètica que mostra l'ordre explícita anterior; no la publiquis ni
la desis en fitxers versionats. La plantilla Remmina desactiva el porta-retalls
i l'emmagatzematge de contrasenyes. Compara l'empremta abans d'acceptar el
certificat autosignat:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop \
  openssl x509 -in /home/lab/.local/share/gnome-remote-desktop/tls.crt \
  -noout -sha256 -fingerprint
```

El perfil fixa `colordepth=63` per habilitar GFX, que GNOME exigeix. El mode
simple de 32 bits es va rebutjar. Després de corregir-lo, un client Remmina
aïllat va autenticar amb la contrasenya generada i va mostrar GNOME. La
validació inicial amb FreeRDP no va detectar l'error del perfil Remmina.
Tanca la pestanya antiga abans d'obrir el perfil corregit. La negociació del
porta-retalls avortava el servidor per manca de `/dev/fuse`; Compose ja declara
aquest dispositiu i un client Remmina amb porta-retalls no provoca el tancament.

Es manté el bloqueig normal per inactivitat. Durant el diagnòstic, una sessió
bloquejada va retornar una imatge RDP negra. Reiniciar el contenidor conservant
els volums va recuperar l'escriptori; reiniciar només els serveis de sessió
no el va recuperar de manera fiable per una cursa durant el tancament.
La recuperació després del bloqueig i l'estabilitat global continuen sense
validar. No es desactiva el bloqueig ni es canvia l'autenticació sense revisar-ho.

L'assistent de benvinguda d'Ubuntu continua habilitat i pot obrir una petició
nativa d'autenticació per a les opcions de privadesa. No s'han acceptat opcions
automàticament. Per comprovar l'entrada es va aturar el seu servei de primer
inici només en aquella sessió, sense deshabilitar-lo ni canviar preferències.

## Configuració i limitacions actuals

Systemd és PID 1. Compose utilitza cgroups privats, `SYS_ADMIN` i
`apparmor=unconfined`; manté seccomp i no utilitza `privileged`.
El perfil versionat `seccomp-desktop.json` prové de Moby `seccomp/v0.1.0`
(commit `a33e0005c5fd43eba98562c826376cac2517e437`, Apache-2.0;
consulta `LICENSE.seccomp`). Només afegeix permís per a `pivot_root`, necessari
per a l'aïllament dels carregadors Glycin amb bubblewrap. Sense aquest permís
no carreguen les icones ni el fons. Es manté l'aïllament de Glycin.
Permet una altra operació de muntatge dins del model de capacitats existent;
cal revisar el perfil en actualitzar Docker, perquè queda fixat a Git.
La validació visual per RDP va confirmar el fons, les icones del dock i la
icona de la carpeta personal després del canvi.
L'entrada
remunta amb escriptura els cgroups del contenidor. No hi ha muntatges de
carpetes de l'amfitrió, sockets del seu escriptori o Docker, GPU ni `/dev/kvm`.
L'amfitrió ha d'oferir FUSE al kernel i `/dev/fuse`, compartit amb lectura i
escriptura per al porta-retalls de GNOME. És una configuració experimental amb permisos amplis, no una
configuració mínima ni un desplegament endurit.

GDM crea la sessió individual de `lab` amb l'eina estàndard `gdm-new-session`,
executada per un servei root segons la política existent. La sessió gràfica i
GNOME Remote Desktop headless funcionen com a `lab`. El helper root continua
actiu per gestionar el tancament de sessió. RDP demana autenticació abans de
donar accés; no hi ha una segona pantalla d'accés GDM. PAM i polkit no es
modifiquen, i les accions administratives continuen demanant la contrasenya
sintètica. La pantalla amb l'usuari dinàmic de GDM va fallar en la prova
inicial i no es presenta com a operativa.

Renderització: `LIBGL_ALWAYS_SOFTWARE=1`, sense GPU compartida. Límits:
2 CPU, 4 GiB de RAM, 4.096 processos/fils i 256 MiB de memòria compartida.
El límit anterior de 1.024 donava només 337 tasques a la porció de l'usuari,
que GNOME esgotava en arrencar. S'ha provat Linux amd64 amb cgroups v2,
Docker Engine 28.5.1 i Compose 2.40.0. L'amfitrió ha de permetre els permisos
i el remuntatge assajats; no s'hi instal·len serveis ni mòduls de kernel.
Docker rootless, Docker Desktop, amfitrions SELinux i altres arquitectures
continuen sense validar.

Els volums desen només el perfil `lab` —inclosa la clau TLS— i la contrasenya
generada. `/run`, `/run/lock` i `/tmp` són temporals. El sistema i els serveis
s'instal·len a la imatge. Reiniciar conserva les credencials; eliminar els
volums les regenera.

Hi ha errors observats a Netplan/udev, colord, TPM i RealtimeKit, un avís BPF
a logind i un error en una extensió de cerca web d'Ubuntu. No s'han ocultat.
Declarar `/dev/fuse` va resoldre el tancament observat en negociar el
porta-retalls. La transferència sostinguda del porta-retalls, fitxers compartits,
portals de documents, àudio i acceptació de
l'autenticació administrativa continuen sense validar. No s'afegiran dispositius
ni s'ampliaran permisos sense revisar-ne l'impacte.

## Comprovació i destrucció

El client opcional executa FreeRDP sobre un Xvfb propi. Aquesta pantalla de
client no canvia el backend Wayland del servidor ni utilitza el teu escriptori:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation build rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation up -d rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop loginctl list-sessions
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation logs --tail 30 rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation stop rdp-probe
```

El client llegeix la contrasenya amb un volum de només lectura, retira totes
les capacitats, activa no-new-privileges, no publica ports i desactiva el
porta-retalls. Només en aquesta prova aïllada accepta el certificat amb
`/cert:ignore`; la plantilla humana de Remmina demana confirmació.

Es va observar GNOME Shell com a servidor Wayland amb renderitzador sense
GPU; logind va confirmar una sessió remota Wayland activa i GTK va retornar
`GdkWaylandDisplay`. Es va inspeccionar la imatge rebuda per RDP i es va
escriure `TERMIA_RDP_INPUT_OK_430` a l'editor estàndard amb teclat i ratolí
RDP. Ctrl+S va desar un fitxer amb aquest contingut exacte. Desconnectar i
reconnectar va conservar sessió i fitxer. Això no valida encara Termia ni
tots els serveis de l'escriptori.

El segon cicle va retirar contenidors, xarxa i tots els volums del projecte,
va reconstruir amb la memòria cau de Docker i va repetir correctament les
proves Wayland/GTK i d'entrada/fitxer per RDP. Es van generar credencials noves
i no existia el marcador del perfil anterior. Això comprova la reconstrucció
sense dades privades prèvies; no s'ha repetit una descàrrega completa de paquets
sense memòria cau. El healthcheck només comprova el socket de sessió i el port
RDP, no tots els serveis Ubuntu.

Per aturar el projecte o destruir expressament les seves dades sintètiques:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation stop
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation down --volumes
```

Repeteix construcció i arrencada després de `down --volumes` per reconstruir-lo.
Les imatges i la memòria cau es conserven; `down --volumes --rmi all` també
retira les imatges dels serveis del projecte. No se seleccionen els laboratoris
privats anteriors. Abans de tancar #430 falten Termia, els límits d'execució
pendents i l'acceptació del desplegament final.

## Validació observada de la imatge base — 2026-10-28

Construcció Linux amd64 correcta amb Docker Engine 28.5.1. Mida:
3.228.534.874 bytes (3,007 GiB). Els 1.510 registres de paquets tenen estat
instal·lat; `dpkg --audit` no va mostrar problemes i `apt-get --simulate check`
va acabar correctament. L'inventari coincideix amb una consulta nova; SHA-256:
`afb1de6f3e7d5c45d85fa70f1b1e5a3315ffc2011bad0fa6095bdd2d9818d51d`.

Versions instal·lades: `ubuntu-desktop` 1.570.4, GNOME Shell 50.1-0ubuntu1.4,
GNOME Remote Desktop 50.2-0ubuntu0.1, Mutter 50.1-0ubuntu2.5, systemd
259.9-0ubuntu0.1 i PipeWire 1.6.2-1ubuntu1.2. El contenidor temporal
d'inspecció va utilitzar un sistema de fitxers de només lectura, sense xarxa,
muntatges ni capacitats addicionals, i es va eliminar automàticament. No es va
crear cap volum persistent ni escriptori actiu. No hi havia aplicacions Snap.
Van passar les 18 proves existents d'infraestructura del laboratori;
no validen l'execució gràfica d'aquesta imatge nova.

## Proves observades de systemd — 2026-10-28

Les proves temporals no van modificar la imatge ni estableixen encara un
desplegament suportat. Totes van utilitzar cgroups privats, sense xarxa ni
muntatges de l'amfitrió, mantenint seccomp. No es va utilitzar `--privileged`.

| Configuració | Resultat |
| --- | --- |
| Permisos i AppArmor predeterminats | systemd no pot crear `/init.scope`: cgroups de només lectura |
| Afegir `SYS_ADMIN`, mantenir AppArmor | Es rebutgen muntatge i remuntatge de cgroups |
| AppArmor sense confinament, sense afegir `SYS_ADMIN` | Es rebutja el remuntatge |
| Afegir `SYS_ADMIN`, AppArmor sense confinament | Funciona el remuntatge amb escriptura i crear/eliminar un cgroup fill |

Amb l'última configuració, systemd va arrencar com a PID 1 amb `basic.target`;
D-Bus i logind van quedar actius, i una unitat temporal amb `/usr/bin/true`
va acabar correctament. El sistema va quedar **degradat**:
`netplan-configure.service` va fallar perquè `udevadm` no va poder contactar
amb udev. logind també va registrar un error en connectar un filtre BPF de
sortida, tot i continuar actiu. No s'han ocultat ni corregit aquests problemes.

`SYS_ADMIN` és un permís ampli i treure el confinament AppArmor redueix
l'aïllament. S'ha demostrat un mecanisme que funciona, no els permisos mínims
ni la configuració definitiva. No es va muntar l'arbre de cgroups de l'amfitrió:
es va remuntar l'existent dins dels espais privats del contenidor. Tots els
contenidors de prova es van aturar/eliminar. No es va iniciar GNOME, RDP ni
Termia. Abans de desplegar cal revisar una política de seguretat més acotada,
els ajustos necessaris de serveis i l'arrencada de l'escriptori.

## Entrades de construcció

- Imatge oficial Docker Ubuntu 26.04 fixada al digest
  `sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78`.
- Instantània Ubuntu `20261027T000000Z`: `resolute`, `resolute-updates` i
  `resolute-security`, amb `main`, `universe`, `restricted` i `multiverse`.
  No s'hi afegeixen backports ni repositoris de tercers.
- Paquets explícits: `ubuntu-desktop`, `gnome-remote-desktop`, `systemd-sysv`,
  `dbus` i `ca-certificates`, amb dependències i recomanacions. S'instal·la el
  metapaquet d'escriptori complet i les aplicacions estàndard, sense substituir-lo
  per un escriptori lleuger ni aplicar exclusions personalitzades de paquets.
- La base no té certificats de confiança HTTPS. Una etapa separada descarrega
  `ca-certificates_20260223_all.deb` de la instantània, comprova SHA-256
  `f7025ab9b24cd73215510931037b02d6960d89584d0d00afba81851abdbe6ef1`
  i extreu els certificats públics sense executar scripts del paquet. APT els
  fa servir temporalment per verificar HTTPS durant la instal·lació normal,
  inclosa la versió de certificats que ofereix la instantània.
- Es mantenen les signatures d'Ubuntu i la comprovació de hashes d'APT.
  `Check-Valid-Until: no` permet reconstruir des de l'arxiu històric;
  no desactiva signatures ni la verificació TLS.
- `.dockerignore` permet el Dockerfile, fonts APT, scripts d'arrencada i RDP,
  unitats de serveis i configuració de renderització de la imatge. El perfil
  seccomp de Compose i la plantilla del client queden fora del context. Tampoc
  hi entren codi de Termia, fitxers privats ni configuració de l'amfitrió.

Es fixen les receptes i els paquets, sense prometre capes idèntiques byte a
byte: els scripts poden generar dates i estat de màquina. No s'instal·len les
aplicacions Snap: tenir un DEB transicional com Firefox no demostra que la seva
aplicació Snap estigui instal·lada. La botiga Snap queda fora de la instantània APT.

## Requisits i ordres

Executa des de l'arrel del repositori amb Docker Engine local sobre Linux i
BuildKit. Cal accés a Docker Hub i `snapshot.ubuntu.com`, i espai per a
l'escriptori complet i les capes de construcció. El destí de construcció és
`linux/amd64`; altres arquitectures, Docker rootless i Docker Desktop continuen
sense validar. No s'instal·len paquets APT a l'amfitrió ni s'utilitza el seu escriptori.

```bash
docker build --progress=plain --platform linux/amd64 --target base \
  --tag termia-lab-430-ubuntu26-base:local tools/docker-lab/gnome26
```

Per inspeccionar els paquets sense iniciar serveis, xarxa, muntatges de
l'amfitrió ni capacitats addicionals:

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

L'inventari ordenat de paquets, versions, arquitectures i estats és a
`/usr/local/share/termia-lab/packages.tsv`; la data de l'arxiu, a
`/usr/local/share/termia-lab/apt-snapshot`. Es retiren índexs i paquets
descarregats després de la instal·lació. `DEBIAN_FRONTEND=noninteractive`
només s'aplica al pas de construcció.

El destí base té `/bin/bash` com a ordre. No declara ports, volums ni usuaris
de laboratori personalitzats ni arrencada automàtica de GNOME/systemd.
Construir i inspeccionar no inicia ni substitueix els laboratoris anteriors.
El destí `desktop` i el seu Compose separat executen el prototip descrit més amunt.

## Límits de la imatge base i desplegament pendent

Docker comparteix el kernel Linux de l'amfitrió; no arrenca un kernel Ubuntu.
No s'utilitza QEMU/KVM, cap disc preinstal·lat ni `/dev/kvm`. Construir aquesta
base no requereix GPU, cgroups de l'amfitrió, el seu bus de sessió, el seu
socket Wayland, un socket Docker dins del contenidor ni execució privilegiada.

Els permisos de systemd/cgroups, la renderització per programari i els límits
del prototip es documenten més amunt. Instal·lar paquets per a maquinari o
serveis no prova que funcionin tots en un contenidor. Es conserva
la política d'Ubuntu que impedeix iniciar serveis durant la instal·lació:
no equival a tenir un escriptori arrencat ni autenticació gràfica validada.

GNOME/Wayland, imatge/entrada RDP i reconstrucció amb volums nous han passat
les proves del prototip. Falten Termia, la reconstrucció posterior i la
configuració final acceptada de permisos i serveis. No es recorrerà a una VM,
un altre compositor ni a l'escriptori de l'amfitrió com a alternativa.

## Actualització i retirada

Per actualitzar, revisa conjuntament digest, data d'instantània, URL i hash
del paquet inicial de certificats. Reconstrueix, compara inventaris i repeteix
les comprovacions afectades. Una instantània fixa no rep actualitzacions de
seguretat automàticament. La reconstrucció depèn de la disponibilitat dels
proveïdors; Ubuntu expressa la intenció de conservar instantànies almenys dos
anys, no una garantia de conservació il·limitada.

Quan ja no necessitis la imatge, elimina només la seva etiqueta:

```bash
docker image rm termia-lab-430-ubuntu26-base:local
```

El destí base no crea volums persistents. No facis neteges generals de Docker
ni eliminis discos o fitxers dels laboratoris privats per reconstruir-la.

Referències: [imatge oficial Ubuntu](https://hub.docker.com/_/ubuntu),
[arxiu d'instantànies Ubuntu](https://snapshot.ubuntu.com/) i
[issue #430](https://github.com/buuuki/termia/issues/430).
