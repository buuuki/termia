# Termia

Termia és un gestor de connexions SSH i espais de treball de terminal per a
escriptoris Linux. Reuneix sessions locals i remotes, espais de treball desats
i transferències de fitxers amb Python, GTK 4 i terminals VTE.

Documentació principal en anglès: [../README.md](../README.md)
Documentació en castellà: [README.es.md](README.es.md)

## Funcionalitats

- Executar connexions SSH i terminals locals en terminals VTE de GTK 4 integrats.
- Treballar amb diverses pestanyes, finestres independents i panells de terminal
  dividits que es poden connectar independentment a diferents servidors SSH o
  terminals locals.
- Desar dissenys de divisió per servidor SSH o perfil de terminal local per reobrir un espai de treball preparat.
- Desar espais de treball amb diverses pestanyes i, si s'activa l'opció
  corresponent, restaurar la sessió anterior en iniciar. La restauració està
  desactivada per defecte.
- Pujar fitxers locals a servidors remots amb SCP des del menú contextual del terminal o del servidor.
- Explorar fitxers remots mitjançant un explorador SFTP natiu amb navegació,
  transferències, progrés, cancel·lació i operacions confirmades.
- Cercar versions oficials i instal·lar actualitzacions verificades des de
  **Quant a**.
- Desar snippets d'ordres reutilitzables per categoria i limitar-los a tots
  els terminals, un grup o un servidor; previsualitzar les variables abans
  d'enviar-los explícitament al terminal seleccionat. Gestionar-los des d'una
  vista de tres columnes amb categories i comptadors, llista de snippets,
  previsualització de l'ordre en només lectura i cerca global. Crear, canviar el
  nom, duplicar i suprimir categories per separat; quan se suprimeix una
  categoria, els seus snippets passen a Sense categoria.
- Mantenir les dades de connexió en local amb emmagatzematge en text pla, ofuscat o xifrat opcional protegit per una contrasenya mestra.
- Organitzar connexions amb grups imbricats, favorits i una secció Recent sense duplicats; trobar-les ràpidament amb `Ctrl+F`.
- Desar host, usuari, port, contrasenya i ruta de clau privada de cada connexió SSH.
- Importar i exportar configuració de Termia, incloses connexions bàsiques, grups imbricats i credencials disponibles de YAML d'Asbru.
- Consultar l'historial de connexions i estadístiques locals opcionals d'ús, incloses durades i servidors més usats.
- Crear notes personals o associades a servidors, organitzar-les per categories i editar-les mentre s'utilitzen els terminals. Les notes es desen automàticament i tenen importació/exportació independents.
- Personalitzar colors i tipus de lletra del terminal, prompts locals, dreceres, confirmacions, barres d'estat de sessió, idioma i comportament segur amb diverses instàncies.

## Novetats de 0.6.0-beta.3

- Crear snippets d'ordres reutilitzables, organitzar-los en categories
  persistents i gestionar les categories (canviar-ne el nom, duplicar-les i
  suprimir-les).
- Cercar snippets a totes les categories des d'una vista de tres columnes amb
  comptadors, una llista de snippets i una previsualització de només lectura.
- Previsualitzar les ordres amb les variables i confirmar-les abans d'enviar-les
  al terminal. Els snippets es desen localment al fitxer de connexions.
- Tractar una sortida normal del shell SSH amb un codi diferent de zero com un
  tancament net, sense oferir la reconnexió per error.
- Aclarir la compatibilitat de la configuració i les còpies de seguretat en
  canviar de versió.

L'explorador SFTP i les actualitzacions des de Quant a ja estaven disponibles a
0.6.0-beta.2.

## Explorador SFTP

Obre **Explora fitxers (SFTP)** des del menú d'un servidor o panell SSH.
Instal·la les dependències amb `scripts/termia-setup.sh install`. La finestra
independent permet navegar, pujar fitxers/carpetes, baixar, crear carpetes,
canviar noms i suprimir fitxers o carpetes buides. No sobreescriu destinacions
existents ni transfereix enllaços simbòlics. Cancel·lar desconnecta SFTP;
reconnecta per continuar. Poden quedar fitxers remots o carpetes incomplets.
El progrés és per fitxer. Tancar la pestanya propietària o Termia tanca SFTP.

Paramiko usa el host i la identitat desats, SSH-agent/claus predeterminades o
contrasenya en memòria. Confirma les empremtes desconegudes; es rebutgen claus
modificades. No s'inclouen àlies d'OpenSSH, ProxyJump, proveïdors de claus
hardware ni MFA interactiu. SCP continua disponible. Aquesta funció es va
introduir a beta.2 i continua disponible a beta.3.

## Descarregar i instal·lar (Ubuntu 24.04+)

### Actualitzacions

Obre **Quant a → Cerca actualitzacions** per consultar les versions oficials.
Les betes/RC es mantenen dins la seva línia, inclosa la versió estable final;
les instal·lacions estables només ofereixen versions estables més recents.
La consulta és manual i no envia configuració ni dades SSH.

**Baixa i instal·la** demana confirmació. Per a Debian es verifica el SHA-256
publicat per GitHub i la identitat i versió del paquet. Calen APT, `pkexec` i un
agent d’autenticació d’escriptori. Si falten eines o metadades verificables,
s’ofereix l’enllaç oficial per instal·lar manualment.

Git només permet actualitzar un repositori net, exactament a l’etiqueta de la
versió actual, a `main` o separat d’una branca en aquella etiqueta. Baixa
l’etiqueta oficial seleccionada i només avança sense crear merges. Les branques
de desenvolupament, canvis locals i historials divergents requereixen una
actualització manual. Després executa `scripts/termia-setup.sh install` per
verificar les dependències i reinicia Termia manualment.

Es poden cancel·lar consultes i baixades. Un cop iniciada la instal·lació, cal
deixar-la acabar; tancar Termia no atura el gestor de paquets. Aquesta funció
s'inclou al paquet beta.2 i no actualitza revisions exclusivament Debian de la
mateixa versió de l'aplicació.

### Paquet publicat

Descarrega [termia_0.6.0.beta.3-1_all.deb](https://github.com/buuuki/termia/releases/download/v0.6.0-beta.3/termia_0.6.0.beta.3-1_all.deb)
i instal·la'l amb APT, que resoldrà les dependències necessàries:

```bash
sudo apt install ./termia_0.6.0.beta.3-1_all.deb
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
./scripts/run_test_instance.sh --copy-current-config review
```

L'opció copia les connexions, notes, ajustos, historial de connexions,
estadístiques i el registre de depuració al perfil de proves. Els canvis fets
allà mai no modifiquen les dades habituals de Termia.

Termia pot migrar fitxers de configuració compatibles de versions anteriors.
Quan una versió més nova desa una configuració, una versió anterior pot deixar
de poder obrir-la. Fes una còpia de seguretat de la configuració abans
d'actualitzar o alternar versions, i utilitza perfils aïllats quan provis
branques de desenvolupament.

Per obtenir informació de diagnòstic sobre pestanyes, splits, processos VTE,
avisos de GTK, bloquejos d'emmagatzematge, xifratge i inici en mode només lectura,
activa `Mode debug` a les preferències Generals. També pots activar-lo per a una
execució amb:

```bash
python3 run_termia.py --debug
```

La informació es desa a `~/.local/state/termia/debug.log`. Quan és possible, els
senyals fatals també hi escriuen les piles Python actives. No registra
contrasenyes, ordres, contingut del terminal, destinacions de connexió ni rutes
privades.

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

El fitxer `termia_0.6.0~beta.3-1_all.deb` es crea al directori pare.
Les branques de desenvolupament poden incloure codi més recent abans
d'actualitzar les metadades Debian per a la versió següent; no distribueixis
aquest paquet com una versió oficial.

Instal·la'l amb:

```bash
sudo apt install ../termia_0.6.0~beta.3-1_all.deb
```

El paquet Debian instal·la l'ordre `termia`, el llançador d'escriptori i la
icona; APT instal·la les dependències de GTK, VTE, Python, SSH i xifratge.

## Notes d'ús

El menú `Configuració` es divideix en `General`, `Terminal`, `Dreceres` i `Seguretat`:

- `General` controla tema, idioma, confirmacions, comportament en iniciar, recuperació de la sessió anterior, dreceres de contrasenya i barra d'estat de sessió, que comença amagada per defecte. La recuperació de la sessió anterior està desactivada per defecte.
- `Terminal` combina l'aparença del VTE i el prompt local amb una única vista prèvia. Els canvis d'aparença s'apliquen a terminals oberts; els del prompt només a Bash locals nous o duplicacions i mai injecten ordres en shells locals actius ni sessions SSH. Les instal·lacions noves comencen amb JetBrains Mono i la paleta Polaris.
- `Dreceres` mostra les dreceres actives i permet gravar combinacions per a accions com filtrar servidors, mostrar la llista, obrir un terminal local, navegar pel focus, copiar, enganxar, canviar de pestanya, ampliar la lletra i enviar la contrasenya desada. `Ctrl+F` enfoca el filtre, `Ctrl+Shift+B` mostra o amaga la llista, `F10` obre o tanca el menú principal, `Ctrl+Shift+T` obre un terminal local i `Ctrl+F6`/`Ctrl+Shift+F6` recorre les regions principals. Les altres tecles de funció sense modificadors s'envien a les aplicacions del terminal.
- `Ctrl+Esquerra`, `Ctrl+Dreta`, `Ctrl+Amunt` i `Ctrl+Avall` mouen el focus
  entre panells dividits segons la direcció visual. Es poden reassignar o
  desactivar si una aplicació del terminal necessita aquestes combinacions.
- `Seguretat` controla el mode d'emmagatzematge de connexions.
- `Gestiona les notes` obre una finestra reutilitzable que no bloqueja els
  terminals. Les notes es desen automàticament en un fitxer separat; també hi
  ha un botó **Desa**. En obrir la finestra es crea un esborrany nou o es reprèn
  un de pendent del mateix context; en mode de només lectura no es creen esborranys.
  Els esborranys buits no s'emmagatzemen; en tancar-ne un amb canvis sense desar,
  es pregunta què cal fer. El botó **Tanca la pestanya** de l'editor segueix el
  mateix diàleg de desar, descartar o continuar editant que la X de la pestanya.
  La llista organitza les notes en un arbre: **Personals** conté les categories
  personals i **Servidors** conté els servidors amb notes o categories desades,
  a més del servidor en què s'està treballant. En desplegar-lo se'n mostren les
  notes i categories; les categories buides desades també són visibles. Un
  esborrany «Nota nova» apareix temporalment a «Sense categoria» i només es desa
  quan s'hi escriu contingut. Les categories pertanyen al seu àmbit i es poden
  repetir entre notes personals i servidors. «Sense categoria» apareix si hi ha
  notes sense categoria o un esborrany actiu en aquell àmbit. La llista té
  cerca global i files
  compactes; el diàleg compacte de Propietats mostra, entre altres dades, la
  categoria desada de cada nota. Un clic selecciona la nota i un doble clic l'obre en una
  pestanya d'edició. La pestanya activa té un subratllat blau fosc i fi de
  banda a banda. L'àrea d'escriptura té un fons i una vora diferenciats que
  s'adapten al tema. Els menús contextuals de notes i Propietats comparteixen
  la superfície i l'estil del menú principal de Termia. Els controls a
  l'esquerra de la barra de títol amaguen la
  llista i obren el menú d'importació/exportació. El botó de nota nova es manté
  a la barra superior al costat del control de la llista, fins i tot quan
  s'amaga. Sobre el cercador, un botó crea categories. Amb un clic dret sobre
  una categoria pots canviar-ne el nom,
  duplicar-la amb les seves notes o suprimir-la. El gestor del menú principal
  mostra l'arbre complet i ofereix importar i exportar. Obrir les
  notes des d'un servidor el desplega i amaga importar/exportar.
  Les pestanyes mostren una icona de l'àmbit i, en passar el cursor per una nota
  de servidor, se'n veu el nom. Els títols nous es numeren per àmbit (Nota nova,
  Nota nova 2, etc.). Les notes poden ser personals o associades a un servidor. En
  suprimir un servidor, les notes es conserven com a personals. La importació
  substitueix les notes després d'oferir una còpia de seguretat. Abans
  d'exportar, Termia explica que triar «Sense contrasenya» crea un fitxer de
  text pla llegible, mentre que triar una contrasenya xifra l'exportació i
  caldrà introduir-la per importar les notes. Fes clic dret en una nota per
  editar-la, canviar-ne el nom, clonar-la, veure'n les propietats o suprimir-la.
  En clonar, es desa una còpia amb una identitat nova i el mateix contingut i
  associacions.
- Fes servir el botó amb forma de terminal de la barra lateral per crear un nou perfil de terminal local; apareix a la llista com una connexió i s'obre en una terminal incrustada en activar-lo.
- Si una altra instància de Termia ja té el bloqueig d'escriptura, una finestra nova s'obre en mode només lectura, mostra un indicador a la capçalera, desactiva les accions que escriuen i continua permetent navegar, connectar i exportar la configuració.
- Si actives la restauració de la sessió anterior a `General`, en tancar Termia
  es desa la disposició de les pestanyes i panells oberts. En tornar-lo a
  iniciar, després de desbloquejar les connexions xifrades si escau, pregunta
  si les vols restaurar. Aquesta opció està desactivada per defecte; no desa la
  sortida dels terminals, processos, PID, contrasenyes ni rutes privades.
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
~/.config/termia/connections.json   # grups, servidors i snippets desats si estan disponibles
~/.config/termia/notes.json        # notes i categories
~/.config/termia/settings.json      # configuració de l'aplicació i del terminal
~/.config/termia/instance.lock      # bloqueig d'escriptor únic per al mode multiinstància
~/.local/state/termia/connections-history.jsonl
~/.local/state/termia/statistics.json
~/.local/state/termia/last-session.json  # només si s'activa la restauració
```

Les contrasenyes desades s'emmagatzemen a `connections.json`; el fitxer es pot mantenir en text pla, ofuscat o xifrat amb una contrasenya mestra des de les preferències de Seguretat. Quan el xifratge està activat, Termia demana la contrasenya mestra en arrencar i no pot recuperar les dades de connexió si aquesta contrasenya es perd. Les notes es desen a part a `notes.json` i segueixen el mateix mode de protecció local; no s'inclouen en importar o exportar connexions. Les notes exportades sense contrasenya són JSON sense xifrar i llegible; si tries una contrasenya per a l'exportació, el fitxer es xifra i aquesta contrasenya cal per importar-lo. Aquesta contrasenya d'exportació és independent de la contrasenya mestra. Tracta els fitxers exportats com a dades sensibles. Les contrasenyes importades des d'Ásbrú es desaran igual quan el YAML d'origen les exposi al camp `pass`.
Els fitxers de connexions exportats també poden contenir credencials.
Els comptadors locals agregats es desen per separat a `statistics.json` i venen desactivats per defecte. Des de **Complements** al menú principal pots activar o desactivar les Estadístiques i l'explorador SFTP. Els canvis s'apliquen en reiniciar Termia; desactivar un complement n'amaga les accions, però no n'esborra les dades. Quan hi ha diversos processos de Termia oberts al mateix temps, només la instància que manté `instance.lock` escriu connexions, ajustos o estadístiques; les següents romanen en només lectura per evitar corrompre aquests fitxers.
L'historial es desa a part a `connections-history.jsonl`; la secció Recent de
la barra lateral s'obté de les connexions SSH correctes d'aquest historial.

Termia no registra les ordres escrites o executades als terminals, la seva
sortida, el contingut del porta-retalls ni comptadors d'ordres o pulsacions.
Els snippets, quan estan disponibles, són plantilles d'ordres que l'usuari desa
expressament a `connections.json`; no són un historial d'ordres executades.
Quan estan activades, les estadístiques només registren connexions agregades,
ús per servidor i durada de sessions; s'escriuen com a màxim cada 30 segons,
en finalitzar sessions i en tancar Termia. Consulta
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
