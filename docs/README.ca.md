# Termia

Termia és un gestor de connexions SSH per a escriptoris Linux desenvolupat amb
Python, GTK 4 i terminals VTE incrustats.

Documentació principal en anglès: [../README.md](../README.md)
Documentació en castellà: [README.es.md](README.es.md)

## Funcionalitats

- Crear, editar, moure i eliminar grups i subgrups de servidors.
- Desar servidors amb nom, host o IP, usuari, port, contrasenya i ruta de clau
  privada.
- Filtrar servidors i obrir diverses sessions al mateix host en pestanyes.
- Usar pestanyes incrustades que reparteixen l'amplada disponible i moure una pestanya a una finestra independent.
- Obrir terminals locals incrustats.
- Desar estadístiques locals agregades de connexions, ordres, pulsacions, durada i ús per servidor.
- Obrir un dashboard d'estadístiques amb targetes de mètriques, resum de durada i servidors més usats.
- Mostrar o amagar globalment la barra d'estat de sessió, amagar-la per sessió i restaurar-la des del menú contextual del terminal.
- Configurar confirmacions per desconnectar sessions i tancar Termia.
- Enviar opcionalment la contrasenya SSH desada a un terminal remot amb `Ctrl+P`, amb `Enter` o sense.
- Configurar per separat opcions generals, tipus de lletra i colors del terminal VTE, i el prompt PS1.
- Personalitzar el prompt local amb colors, temes predefinits i prefixos d'hora o data sense canviar fitxers d'inici ni ordres remotes.
- Usar la interfície en castellà, català o anglès. L'idioma inicial segueix el locale del sistema quan està suportat.
- Importar i exportar configuracions de Termia.
- Importar connexions i grups imbricats bàsics des de YAML d'Asbru.

## Notes d'ús

El menú `Configuració` es divideix en `General`, `Terminal` i `Prompt`:

- `General` controla tema, idioma, confirmacions, comportament en iniciar, dreceres de contrasenya i barra d'estat de sessió.
- `Terminal` controla el tipus de lletra, mida, colors i paletes del terminal VTE incrustat.
- `Prompt` personalitza el PS1 de terminals locals amb color, temes predefinits i prefixos d'hora o data. No altera ordres SSH ni modifica fitxers d'inici remots.

Cada sessió pot mostrar una barra d'estat amb estat, PID, temps transcorregut, botó compacte per amagar-la i desconnexió. Pots activar o desactivar les barres d'estat des de `General`; si amagues la barra d'una sessió, pots recuperar-la amb el botó dret dins del terminal i `Mostrar barra d'estat de la sessió`. La barra lateral de servidors té el seu propi botó a la capçalera.

## Entorn provat

Termia s'ha provat en Ubuntu 24.04.4 LTS amb kernel Linux
6.8.0-117-generic, GNOME 46.0 i Wayland.

## Descarregar i instal·lar

Clona el repositori complet:

```bash
git clone https://github.com/buuuki/termia.git
cd termia
chmod +x scripts/install_dependencies.sh
```

Comprova primer les dependències sense modificar el sistema:

```bash
./scripts/install_dependencies.sh --check
```

Si la comprovació indica que falten dependències, instal·la-les amb:

```bash
./scripts/install_dependencies.sh
```

L'instal·lador verifica el resultat després d'instal·lar. També intenta instal·lar JetBrains Mono per al tipus de lletra per defecte del terminal; si no està disponible, Termia usa Ubuntu Mono o Monospace com a fallback. Pots repetir la
comprovació en qualsevol moment:

```bash
./scripts/install_dependencies.sh --check
```

Si la comprovació indica que falta el namespace `Vte 3.91`, falta el paquet
d'introspecció GTK 4 VTE. En Debian, Ubuntu o Linux Mint el paquet necessari és
`gir1.2-vte-3.91`.

Instal·la el llançador d'escriptori amb:

```bash
./scripts/install_desktop.sh
```

També pots executar Termia directament des del repositori:

```bash
python3 run_termia.py
```

Elimina únicament el llançador d'escriptori:

```bash
./scripts/uninstall_desktop.sh
```

## Dades de l'usuari i seguretat

Les connexions, preferències i estadístiques es desen fora del repositori:

```text
~/.config/termia/connections.json   # grups i servidors
~/.config/termia/settings.json      # configuració de l'aplicació i del terminal
~/.local/state/termia/statistics.json
```

Les contrasenyes desades s'emmagatzemen en text pla a `connections.json`.
Els fitxers de connexions exportats també poden contenir credencials.
Els comptadors locals agregats es desen per separat a `statistics.json`.

Termia no desa el text escrit, el contingut de les ordres ni el contingut del
porta-retalls. Les estadístiques s'escriuen com a màxim cada 30 segons mentre
s'escriu, en finalitzar sessions i en tancar Termia. Consulta
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
