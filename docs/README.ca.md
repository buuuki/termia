# Termia

Termia és un gestor de connexions SSH per a escriptoris Linux desenvolupat amb
Python, GTK 4 i terminals VTE incrustats.

Documentació principal en anglès: [../README.md](../README.md)
Documentació en castellà: [README.es.md](README.es.md)

## Funcionalitats

- Crear, editar, moure i eliminar grups i subgrups de servidors.
- Desar servidors amb nom, host o IP, usuari, port, contrasenya i ruta de clau
  privada.
- Filtrar servidors amb `Ctrl+F` i obrir diverses sessions al mateix host en pestanyes.
- Reobrir els 10 servidors connectats més recentment des d'una secció Recent a sobre de Favorites, sense duplicats.
- Usar pestanyes incrustades que reparteixen l'amplada disponible i moure una pestanya a una finestra independent.
- Crear i obrir perfils configurables de terminal local des de la barra lateral.
- Dividir una pestanya de terminal en diversos panells des del menú contextual del terminal.
- Configurar dissenys bàsics de divisió per a cada servidor SSH o perfil de terminal local.
- Enviar fitxers locals a un servidor des del menú contextual del terminal o del servidor.
- Executar diverses instàncies de Termia; la primera conserva accés d'escriptura i les següents passen automàticament a mode només lectura.
- Registrar opcionalment estadístiques locals agregades de connexions, durada i ús per servidor.
- Obrir un dashboard d'estadístiques amb targetes de mètriques, resum de durada i servidors més usats.
- Veure un historial local de connexions amb marques de temps, resultats i durades.
- Mostrar o amagar globalment la barra d'estat de sessió, amagar-la per sessió i restaurar-la des del menú contextual del terminal.
- Configurar confirmacions per desconnectar sessions i tancar Termia.
- Configurar dreceres de terminal fent clic en un control i prement la combinació que vulguis, incloent `Ctrl+Shift+C` per copiar i `Ctrl+Shift+V` per enganxar. Les tecles de funció sense modificadors es reserven per a les aplicacions del terminal, excepte `F10`, configurable i assignada per defecte al menú principal.
- Enviar opcionalment la contrasenya SSH desada a un terminal remot amb `Ctrl+P`, amb `Enter` o sense.
- Configurar per separat opcions generals, tipus de lletra i colors del terminal VTE, i el prompt PS1.
- Personalitzar el prompt local amb colors, temes predefinits i prefixos d'hora o data sense canviar fitxers d'inici ni ordres remotes.
- Usar la interfície en castellà, català o anglès. L'idioma inicial segueix el locale del sistema quan està suportat.
- Importar i exportar configuracions de Termia.
- Importar connexions, grups imbricats i contrasenyes desades des de YAML d'Asbru quan estiguin disponibles.

## Notes d'ús

El menú `Configuració` es divideix en `General`, `Terminal`, `Prompt`, `Dreceres` i `Seguretat`:

- `General` controla tema, idioma, confirmacions, comportament en iniciar, dreceres de contrasenya i barra d'estat de sessió, que comença amagada per defecte.
- `Terminal` controla el tipus de lletra, mida, colors, gruix i color del separador de divisió, i paletes del terminal VTE incrustat. Les instal·lacions noves comencen amb JetBrains Mono i la paleta Polaris.
- `Prompt` personalitza el PS1 de terminals locals amb color, temes predefinits i prefixos d'hora o data. El color predeterminat del prompt és blanc. No altera ordres SSH ni modifica fitxers d'inici remots.
- `Dreceres` mostra les dreceres actives i permet gravar combinacions per a accions com filtrar servidors, mostrar la llista, obrir un terminal local, navegar pel focus, copiar, enganxar, canviar de pestanya, ampliar la lletra i enviar la contrasenya desada. `Ctrl+F` enfoca el filtre, `Ctrl+Shift+B` mostra o amaga la llista, `F10` obre o tanca el menú principal, `Ctrl+Shift+T` obre un terminal local i `Ctrl+F6`/`Ctrl+Shift+F6` recorre les regions principals. Les altres tecles de funció sense modificadors s'envien a les aplicacions del terminal.
- `Seguretat` controla el mode d'emmagatzematge de connexions.
- Fes servir el botó amb forma de terminal de la barra lateral per crear un nou perfil de terminal local; apareix a la llista com una connexió i s'obre en una terminal incrustada en activar-lo.
- Si una altra instància de Termia ja té el bloqueig d'escriptura, una finestra nova s'obre en mode només lectura, mostra un indicador a la capçalera, desactiva les accions que escriuen i continua permetent navegar, connectar i exportar la configuració.
- Fes clic dret en un terminal o en un servidor per pujar fitxers a `/tmp/.termia/` a l'host destí.
- El menú principal inclou historial de connexions, ubicacions de fitxers de dades i accions d'importació/exportació.

Cada sessió pot mostrar una barra d'estat amb estat, PID, temps transcorregut, botó compacte per amagar-la i desconnexió. Pots activar o desactivar les barres d'estat des de `General`; si amagues la barra d'una sessió, pots recuperar-la amb el botó dret dins del terminal i `Mostrar barra d'estat de la sessió`. La barra lateral de servidors té el seu propi botó a la capçalera. Amb el botó dret dins del terminal pots obrir els submenús traduïts de `Dividir` i `Pestanya`; els panells es poden crear amunt, avall, a l'esquerra o a la dreta, i desapareixen automàticament quan la seva shell acaba. Una pestanya només es tanca amb `exit` quan ha sortit l'últim terminal i ja no queden panells dividits.

## Entorn provat

Termia s'ha provat en Ubuntu 24.04.4 LTS amb kernel Linux
6.8.0-117-generic, GNOME 46.0 i Wayland.

## Descarregar i instal·lar

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

Per obtenir informació de diagnòstic sobre GTK, VTE, els bloquejos
d'emmagatzematge, el xifratge i l'inici en mode només lectura, activa `Mode
debug` al menú principal. També pots activar-lo per a una execució amb:

```bash
python3 run_termia.py --debug
```

La informació es desa a `~/.local/state/termia/debug.log` i també es mostra
per stderr. No registra contrasenyes ni el contingut de les connexions.

Elimina únicament el llançador d'escriptori, sense esborrar ajustos, connexions,
estadístiques ni paquets del sistema:

```bash
./scripts/termia-setup.sh uninstall
```

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
