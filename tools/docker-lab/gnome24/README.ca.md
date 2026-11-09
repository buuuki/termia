# Laboratori persistent Ubuntu 24.04 amb GNOME

[English](README.md) · [Español](README.es.md)

Infraestructura de #459. La construcció, l’inici de sessió GNOME/Wayland
i la imatge/entrada RDP s’han validat localment. És independent
del laboratori X11/Weston i de la VM XFCE. Es conserven Ubuntu 26 i els anteriors.

## Requisits i recursos

Linux amd64, Docker Engine local i Compose, cgroups v2, `/dev/fuse`, Python 3
i Git a l’amfitrió. No s’hi instal·len eines. Cal espai per a l’escriptori complet
i les capes d’imatge. El contenidor té 2 CPU, 4 GiB de RAM i 256 MiB de memòria
compartida; el port local 12389 ha d’estar lliure. Docker Desktop, rootless,
ARM i la reproducció en un segon amfitrió no s’han validat.

La imatge fixa el digest d’Ubuntu 24.04 i la instantània APT, i instal·la
`ubuntu-desktop` complet amb recomanacions, GNOME Remote Desktop, idiomes
EN/ES/CA, Firefox nadiu, dependències de Termia, Git, Xvfb, GDB i Valgrind.
Ruff, Bandit i Coverage utilitzen els requisits fixats del repositori en un
entorn virtual dins la imatge. Construir pot descarregar paquets. Importar eines
o obrir l’escriptori no executa tests ni actualitzacions de Termia.

APT fixa les versions a partir dels índexs signats de la instantània. Descarrega
fins a vuit paquets en paral·lel de l’arxiu oficial d’Ubuntu, amb Snapshot com
a alternativa, i exigeix el SHA-256 d’aquests índexs per a cada fitxer. Canviar
el servidor de descàrrega no canvia les versions ni els bytes acceptats.

## Construir i connectar

Des de l’arrel, amb els fitxers d’implementació afegits a Git perquè entrin a
la instantània:

```bash
python3 tools/docker-lab/gnome24/lab.py start
remmina -c tools/docker-lab/gnome24/laboratory.remmina
```

`start` captura fitxers versionats permesos, inclosos canvis locals, construeix
amb memòria cau i crea o actualitza el mateix projecte `termia-459-gnome24`.
Rebutja Docker remot i recursos d’un altre checkout. Reconstruir pot interrompre
RDP. Si falla la preparació o construcció, no recrea l’escriptori existent.
Conserva una etiqueta de la imatge anterior i no elimina volums.

Connecta a `127.0.0.1:12389`, usuari `lab`, domini buit. Consulta la contrasenya
sintètica només quan calgui:

```bash
python3 tools/docker-lab/gnome24/lab.py password
```

Es proposa l’accés remot nadiu de GNOME 46: primer autentica RDP i després
l’usuari `lab` a GDM amb la mateixa contrasenya sintètica. El client ha d’admetre
redirecció RDP; el comportament real s’ha de comprovar durant la integració.
La salut del listener no demostra una sessió gràfica funcional. Verifica la
petjada TLS abans d’acceptar el certificat local:

```bash
docker exec termia-459-gnome24-desktop-1 openssl x509 -in /var/lib/gnome-remote-desktop/termia-tls/tls.crt -noout -sha256 -fingerprint
```

## Ús habitual i persistència

```bash
python3 tools/docker-lab/gnome24/lab.py status
python3 tools/docker-lab/gnome24/lab.py logs
python3 tools/docker-lab/gnome24/lab.py stop
python3 tools/docker-lab/gnome24/lab.py resume
```

`stop` conserva contenidor i dades; `resume` obre la imatge existent sense
actualitzar el codi. `start` prepara i verifica una instantània nova. El panell
n’indica la identitat. No hi ha eliminació automàtica ni reinici obligatori en
arrencar l’amfitrió. Conserva credencials, TLS i perfils abans de retirar o
recrear manualment; no utilitzis una neteja global.

Obre **Laboratori de proves de Termia** des de les aplicacions. **Obrir Termia**
reutilitza un perfil persistent; **Nova prova aïllada** en crea un altre i
conserva registres. El panell també obre un terminal i executa la bateria amb
pantalla/bus privats. Les dades queden a `~/termia-lab-evidence` del volum
`profile`. Els temporals utilitzen el seu directori executable, no `/tmp`,
que Docker munta amb `noexec`. No hi introdueixis credencials reals.

Els volums `profile`, `credentials` i `remote-state` són exclusius del projecte.
No es munten escriptori, llar, agent SSH ni socket Docker de l’amfitrió.
Les imatges contenen codi/eines, no perfils/contrasenyes. Seleccionar idioma i
reiniciar sessió ha de conservar preferències; cal verificar-ho interactivament.

## Permisos i validació

Com Ubuntu 26, el laboratori utilitza `SYS_ADMIN`, AppArmor sense confinament per
a aquest contenidor, cgroups privats i el perfil seccomp versionat de `gnome26`.
Comparteix `/dev/fuse`, però no GPU, KVM ni tots els cgroups de l’amfitrió.
Són permisos amplis, no una garantia d’aïllament mínim. No modifica PAM ni polkit.

L’eina de configuració de GNOME 46 requereix la contrasenya sintètica en argv,
breument visible per a processos autoritzats del contenidor. La utilitat no
registra arguments, excepcions amb credencials ni sortida crua. Mai no s’han
de publicar contrasenyes reals ni dades generades.

Les entrades Xorg es conserven perquè GDM 46 les necessita per inicialitzar-se
sense pantalla física. La sessió remota validada utilitza Wayland. El component
nadiu de traspàs s’inicia amb la benvinguda i la sessió d’usuari. Només aquest
laboratori desactiva `org.gnome.SettingsDaemon.Sharing.service`: la connexió
externa Docker no és primària per a aquest gestor i provoca que aturi RDP.
La gestió automàtica de compartició queda desactivada; RDP nadiu continua actiu.

Validat localment: accés RDP interactiu, sessió Wayland remota, panell GTK,
Termia amb terminal VTE i 819 tests automàtics. La revisió interactiva de tots
els idiomes i Firefox queda fora d’aquesta comprovació. No certifica una release.

El servei de color colord conserva la protecció excepte `PrivateUsers`, que es
desactiva per evitar l’error 217/USER dins Docker i les esperes d’inici RDP.
No s’afegeixen capacitats al contenidor.

Limitació observada de GNOME 46: la primera connexió després de recrear o
arrencar pot esgotar el temps de traspàs i mostrar negre. Espera que acabi i
torna a connectar amb el mateix perfil RDP. El segon accés permet iniciar sessió
i utilitzar l’escriptori. `healthy` només comprova serveis i port.
