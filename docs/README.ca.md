# Termia

Termia és un gestor de connexions SSH per a escriptoris Linux desenvolupat amb
Python, GTK 4 i terminals VTE incrustats.

Documentació principal en anglès: [../README.md](../README.md)
Documentació en castellà: [README.es.md](README.es.md)

## Funcionalitats

- Executar connexions SSH i terminals locals en terminals VTE de GTK 4 integrats.
- Treballar amb diverses pestanyes, finestres independents i panells de terminal
  dividits que es poden connectar independentment a diferents servidors SSH o
  terminals locals.
- Desar dissenys de divisió per servidor SSH o perfil de terminal local per reobrir un espai de treball preparat.
- Pujar fitxers locals a servidors remots amb SCP des del menú contextual del terminal o del servidor.
- Mantenir les dades de connexió en local amb emmagatzematge en text pla, ofuscat o xifrat opcional protegit per una contrasenya mestra.
- Organitzar connexions amb grups imbricats, favorits i una secció Recent sense duplicats; trobar-les ràpidament amb `Ctrl+F`.
- Desar host, usuari, port, contrasenya i ruta de clau privada de cada connexió SSH.
- Importar i exportar configuració de Termia, incloses connexions bàsiques, grups imbricats i credencials disponibles de YAML d'Asbru.
- Consultar l'historial de connexions i estadístiques locals opcionals d'ús, incloses durades i servidors més usats.
- Personalitzar colors i tipus de lletra del terminal, prompts locals, dreceres, confirmacions, barres d'estat de sessió, idioma i comportament segur amb diverses instàncies.

## Descarregar i instal·lar (Ubuntu 24.04+)

Descarrega [termia_0.5.0.beta.3-1_all.deb](https://github.com/buuuki/termia/releases/download/v0.5.0-beta.3/termia_0.5.0.beta.3-1_all.deb)
i instal·la'l amb APT, que resoldrà les dependències necessàries:

```bash
sudo apt install ./termia_0.5.0.beta.3-1_all.deb
```

## Descarregar i instal·lar des del codi font

Clona el repositori complet:

```bash
git clone https://github.com/buuuki/termia.git
cd termia
chmod +x scripts/termia-setup.sh
```

Instal·la les dependències que faltin, comprova el resultat i afegeix el llançador
local de Termia amb:

```bash
./scripts/termia-setup.sh install
```

Abans de modificar el sistema, l'script mostra les accions previstes i espera
10 segons per poder-lo cancel·lar. A Debian, Ubuntu i Linux Mint, si `apt-get
update` falla perquè algun repositori configurat no està disponible, pregunta
abans d'utilitzar la memòria cau APT disponible per instal·lar els paquets necessaris.
Si totes les dependències d'execució ja estan disponibles, no executa el gestor de
paquets del sistema.

L'instal·lador verifica el resultat després d'instal·lar. També intenta instal·lar JetBrains Mono per al tipus de lletra per defecte del terminal; les instal·lacions noves fan servir la paleta Polaris i el color blanc del prompt per defecte, i si no està disponible, Termia usa Ubuntu Mono o Monospace com a fallback.

Si la comprovació indica que falta el namespace `Vte 3.91`, falta el paquet
d'introspecció GTK 4 VTE. En Debian, Ubuntu o Linux Mint el paquet necessari és
`gir1.2-vte-3.91`.

També pots executar Termia directament des del repositori:

```bash
python3 run_termia.py
```

Per provar una branca sense tancar la finestra habitual de Termia, inicia un
perfil aïllat. Utilitza una configuració, estat i bloqueig d'escriptura propis:

```bash
./scripts/run_test_instance.sh --copy-current-config pr-152
```

L'opció copia les connexions, ajustos, historial de connexions, estadístiques i
el registre de depuració al perfil de proves. Els canvis fets allà mai no
modifiquen les dades habituals de Termia.

Per obtenir informació de diagnòstic sobre GTK, VTE, els bloquejos
d'emmagatzematge, el xifratge i l'inici en mode només lectura, activa `Mode
debug` a les preferències Generals. També pots activar-lo per a una execució amb:

```bash
python3 run_termia.py --debug
```

La informació es desa a `~/.local/state/termia/debug.log`. No registra
contrasenyes ni el contingut de les connexions.

Elimina únicament el llançador d'escriptori, sense esborrar ajustos, connexions,
estadístiques ni paquets del sistema:

```bash
./scripts/termia-setup.sh uninstall
```

## Crear un paquet Debian

A Debian, Ubuntu 24.04 o posterior, o una distribució compatible, instal·la les
dependències de compilació i crea el paquet des de l'arrel del repositori.
Ubuntu 22.04 i anteriors no inclouen l'entorn VTE per a GTK 4 necessari:

```bash
sudo apt build-dep .
dpkg-buildpackage -us -uc -b
```

El fitxer `termia_0.5.0~beta.3-1_all.deb` es crea al directori pare. Instal·la'l
amb:

```bash
sudo apt install ../termia_0.5.0~beta.3-1_all.deb
```

El paquet Debian instal·la l'ordre `termia`, el llançador d'escriptori i la
icona; APT instal·la les dependències de GTK, VTE, Python, SSH i xifratge.

## Notes d'ús

El menú `Configuració` es divideix en `General`, `Terminal`, `Dreceres` i `Seguretat`:

- `General` controla tema, idioma, confirmacions, comportament en iniciar, recuperació de la sessió anterior, dreceres de contrasenya i barra d'estat de sessió, que comença amagada per defecte. La recuperació de la sessió anterior està desactivada per defecte.
- `Terminal` combina l'aparença del VTE i el prompt local amb una única vista prèvia. Els canvis d'aparença s'apliquen a terminals oberts; els del prompt només a Bash locals nous o duplicacions i mai injecten ordres en shells locals actius ni sessions SSH. Les instal·lacions noves comencen amb JetBrains Mono i la paleta Polaris.
- `Dreceres` mostra les dreceres actives i permet gravar combinacions per a accions com filtrar servidors, mostrar la llista, obrir un terminal local, navegar pel focus, copiar, enganxar, canviar de pestanya, ampliar la lletra i enviar la contrasenya desada. `Ctrl+F` enfoca el filtre, `Ctrl+Shift+B` mostra o amaga la llista, `F10` obre o tanca el menú principal, `Ctrl+Shift+T` obre un terminal local i `Ctrl+F6`/`Ctrl+Shift+F6` recorre les regions principals. Les altres tecles de funció sense modificadors s'envien a les aplicacions del terminal.
- `Seguretat` controla el mode d'emmagatzematge de connexions.
- Fes servir el botó amb forma de terminal de la barra lateral per crear un nou perfil de terminal local; apareix a la llista com una connexió i s'obre en una terminal incrustada en activar-lo.
- Si una altra instància de Termia ja té el bloqueig d'escriptura, una finestra nova s'obre en mode només lectura, mostra un indicador a la capçalera, desactiva les accions que escriuen i continua permetent navegar, connectar i exportar la configuració.
- En tancar Termia es desa de manera segura la disposició de les pestanyes i divisions obertes. En tornar-lo a iniciar, després de desbloquejar les connexions xifrades, pregunta si les vols restaurar; no desa la sortida dels terminals, processos, PID, contrasenyes ni rutes privades.
- Fes clic dret en un terminal o en un servidor per pujar fitxers a `/tmp/.termia/` a l'host destí.
- El menú principal inclou historial de connexions, ubicacions de fitxers de dades i accions d'importació/exportació.

Cada panell de terminal pot mostrar la seva pròpia barra d'estat amb el nom de
la connexió, l'estat, el PID, el temps transcorregut, un botó compacte per
amagar-la i l'acció de desconnexió. Activa o desactiva les barres des de
`General`; per canviar la d'un panell, fes clic dret dins seu i selecciona
`Mostra la barra d'estat de la sessió` o `Amaga la barra d'estat de la sessió`.
Les accions direccionals de `Divideix` dupliquen el panell seleccionat; usa
`Obre una connexió en un panell dividit…` per triar una direcció i un altre
servidor SSH o terminal local desat. Una pestanya admet fins a 16 panells.
Sortir o desconnectar-ne un no atura els altres. Un panell que espera una
reconnexió mostra automàticament la barra d'estat amb l'acció `Tanca`, mentre
que Retorn continua permetent reintentar la connexió.
Termia permet fins a 40 pestanyes obertes en total, incloses les que són en
finestres independents. Els espais de treball i grups de servidors que no caben
en la capacitat disponible es rebutgen abans d'iniciar-ne els processos.
Fes servir el botó de desar de la barra lateral per emmagatzemar les pestanyes
i divisions actuals com un espai de treball amb nom. Els espais de treball
apareixen a la barra lateral amb una icona de quadrícula; des del menú
contextual els pots obrir, actualitzar, reanomenar, duplicar o eliminar. Un
espai de treball pot contenir fins a 32 panells entre totes les pestanyes i
s'obre sense cap confirmació addicional. Els espais de treball també restauren
els títols personalitzats i el directori de treball de cada panell local. No es
capturen directoris SSH; si un directori local ja no està disponible, s'utilitza
el directori inicial normal del perfil.

## Entorn provat

Termia s'ha provat en Ubuntu 24.04.4 LTS amb kernel Linux
6.8.0-117-generic, GNOME 46.0 i Wayland.

## Base d'execució compatible

Termia requereix Python 3.10 o posterior, GTK 4.0/GDK 4.0 i l'espai
d'introspecció de VTE per a GTK 4, `Vte 3.91`. L'entorn actual de validació
proporciona GTK 4.14.5 i VTE 0.76.0. Les comprovacions de compatibilitat per a
mètodes GTK opcionals com `set_handle_menubar_accel` i
`set_show_separators` són intencionades, perquè les distribucions poden
exposar diferents nivells de l'API de GTK.

## Dades de l'usuari i seguretat

Les connexions, preferències i estadístiques es desen fora del repositori:

```text
~/.config/termia/connections.json   # grups i servidors
~/.config/termia/settings.json      # configuració de l'aplicació i del terminal
~/.config/termia/instance.lock      # bloqueig d'escriptor únic per al mode multiinstància
~/.local/state/termia/recent_connections.jsonl
~/.local/state/termia/statistics.json
```

Les contrasenyes desades s'emmagatzemen a `connections.json`; el fitxer es pot mantenir en text pla, ofuscat o xifrat amb una contrasenya mestra des de les preferències de Seguretat. Quan el xifratge està activat, Termia demana la contrasenya mestra en arrencar i no pot recuperar les dades de connexió si aquesta contrasenya es perd. Les contrasenyes importades des d'Ásbrú es desaran igual quan el YAML d'origen les exposi al camp `pass`.
Els fitxers de connexions exportats també poden contenir credencials.
Els comptadors locals agregats es desen per separat a `statistics.json`, venen desactivats per defecte i es poden activar o desactivar des de les preferències generals. Quan hi ha diversos processos de Termia oberts al mateix temps, només la instància que manté `instance.lock` escriu connexions, ajustos o estadístiques; les següents romanen en només lectura per evitar corrompre aquests fitxers.
Les connexions recents es desen a part a `recent_connections.jsonl` perquè la barra lateral pugui mostrar una secció Recent petita i sense duplicats basada en les últimes connexions SSH correctes.

Termia no desa el text escrit, el contingut de les ordres, el contingut del
porta-retalls, comptadors d'ordres ni comptadors de pulsacions. Quan estan activades, les estadístiques només registren connexions agregades, ús per servidor i durada de sessions; s'escriuen com a màxim cada 30 segons, en finalitzar sessions i en tancar Termia. Consulta
[../SECURITY.md](../SECURITY.md).

Python pot crear directoris `__pycache__/` al costat dels mòduls executats.
Només contenen bytecode generat, estan exclosos per `.gitignore` i no s'han de
pujar a GitHub.

## Estructura

```text
run_termia.py                 Llançador per executar des del repositori
src/termia/app.py             Composició principal i finestra
src/termia/                Mòduls d'emmagatzematge, diàlegs, pestanyes, terminals i utilitats
src/termia/assets/            Imatges utilitzades per Termia
scripts/                      Instal·lació i desinstal·lació
docs/                         Documentació addicional
LICENSE                       Llicència GPL-3.0-o-posterior
```

## Llicència

Termia es publica sota la [GNU General Public License v3.0 o posterior](../LICENSE). Les dependències s'instal·len
per separat mitjançant el gestor de paquets del sistema. Consulta
[../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
