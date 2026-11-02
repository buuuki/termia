# Termia

Termia és un gestor de connexions SSH i espais de treball de terminal per a Linux.
Reuneix sessions locals i remotes, espais de treball desats i transferències de
fitxers en terminals VTE integrats amb GTK 4.

![Termia amb diverses sessions SSH integrades](../img/termia-screenshot.png)

[English](../README.md) · [Castellà](README.es.md) · [Full de ruta](../ROADMAP.md)

## Funcionalitats

- Terminals locals i SSH amb pestanyes, panells dividits i finestres separables.
- Connexions organitzades en grups imbricats, preferits i connexions recents.
- Espais de treball desats i restauració opcional de la sessió anterior.
- Pujades SCP i explorador SFTP nadiu amb transferències i cancel·lació.
- Snippets reutilitzables amb categories, àmbit, variables i dreceres;
  les ordres es previsualitzen abans d'enviar-les.
- Notes personals o associades a servidors, amb desament automàtic,
  categories i importació/exportació.
- Dades de connexió locals amb xifratge opcional mitjançant contrasenya mestra.
- Importació/exportació de Termia i importació de connexions des d'Ásbrú YAML.
- Historial de connexions i complements opcionals d'Estadístiques i SFTP.
- Aparença i dreceres configurables; interfície en català, castellà i anglès.

## Estat de la versió

**[0.6.1-beta](https://github.com/buuuki/termia/releases/tag/v0.6.1-beta)** és una
versió preliminar de manteniment. Consulta [CHANGELOG.md](../CHANGELOG.md)
per veure els canvis des de 0.6.0-beta.4.

## Instal·lar a Ubuntu 24.04 o posterior

Paquet Debian:
[termia_0.6.1.beta-1_all.deb](https://github.com/buuuki/termia/releases/download/v0.6.1-beta/termia_0.6.1.beta-1_all.deb).

```bash
sudo apt install ./termia_0.6.1.beta-1_all.deb
```

APT instal·la les dependències necessàries, el llançador i la icona.
Obre **Termia** des del menú d'aplicacions o executa `termia`.

### Executar des del codi font

```bash
git clone https://github.com/buuuki/termia.git
cd termia
./scripts/termia-setup.sh install
python3 run_termia.py
```

L'script comprova les dependències i instal·la un llançador per a l'usuari.
Admet els gestors de paquets de Debian/Ubuntu/Linux Mint, Fedora i Arch.
Reinicia Termia només quan acabi correctament; repeteix-lo si mous el checkout.
Usa `./scripts/termia-setup.sh uninstall` per treure el llançador conservant les dades.

### Requisits

Python 3.10+, GTK 4, GtkSourceView 5 i l'espai VTE per a GTK 4 `Vte 3.91`.
Les comprovacions es fan en laboratoris Ubuntu 24.04 i 26.04.
Ubuntu 22.04 i anteriors no proporcionen el VTE per a GTK 4 necessari.

## Actualitzacions

**Beta.3 i beta.4 requereixen una primera actualització manual a 0.6.1-beta.**
Fes una còpia del perfil, tanca Termia i instal·la el nou .deb sobre l'anterior.
No cal desinstal·lar primer.

Per a un checkout net, un cop publicada l'etiqueta:

```bash
git status --short
git fetch https://github.com/buuuki/termia.git tag v0.6.1-beta
git merge --ff-only v0.6.1-beta
./scripts/termia-setup.sh install
```

Atura't si la primera ordre mostra canvis locals o el merge no pot avançar
mitjançant fast-forward. Completa el setup abans de reiniciar i consulta la
[compatibilitat de dades](STORAGE_MIGRATIONS.md) abans de tornar a una versió anterior.

Des de 0.6.1-beta, **Quant a → Cerca actualitzacions** detecta versions de
manteniment beta/RC posteriors de la mateixa sèrie MAJOR.MINOR, incloses
versions estables posteriors. Les instal·lacions estables només reben estables.

L'actualitzador verifica les descàrregues i revisa les dependències abans d'instal·lar.
Les instal·lacions compatibles des de Git o Debian poden usar l'autorització
administrativa nadiua per als paquets necessaris. Git requereix un checkout net
d'una release a main o a la seva etiqueta; les branques de desenvolupament i canvis
locals s'actualitzen manualment. En casos no compatibles es conserva l'enllaç oficial.
Deixa acabar la instal·lació i reinicia Termia; no actualitza revisions exclusivament
Debian de la mateixa versió de l'aplicació.

## Ajuda i proves aïllades

Obre **Ajuda** des del menú principal per consultar els fluxos d'ús i les dreceres.
Els complements opcionals d'Estadístiques i SFTP es gestionen des de
**Complements**; els canvis requereixen reiniciar i desactivar-los conserva les dades.

Per provar un checkout amb un perfil buit o una còpia separada de les teves dades:

```bash
./scripts/run_test_instance.sh --fresh
./scripts/run_test_instance.sh --copy-current-config review
```

La primera ordre crea un perfil buit; la segona copia les dades actuals.
Cap de les dues modifica el perfil habitual. Consulta
[CONTRIBUTING.md](../CONTRIBUTING.md) per a les comprovacions i el diagnòstic.

## Dades i seguretat

La configuració i les notes es desen a `~/.config/termia/`; l'historial i les
estadístiques, a `~/.local/state/termia/`. Fes una còpia abans d'actualitzar.
Les credencials i exportacions poden contenir contrasenyes llegibles si no es
xifren. L'ofuscació no és xifratge i una contrasenya mestra perduda no es recupera.

Les ordres d'inici SSH s'executen cada vegada que s'inicia la connexió;
tracta-les com a configuració executable. Termia no registra les ordres del
terminal, la sortida ni les pulsacions. Consulta [SECURITY.md](../SECURITY.md)
per a l'emmagatzematge, les exportacions i les actualitzacions.

L'explorador SFTP admet les dades desades, claus de l'agent SSH o per defecte
i contrasenyes; no admet àlies d'OpenSSH, ProxyJump, proveïdors de claus físiques
ni MFA interactiva. No sobreescriu destinacions existents i pot deixar fitxers o
directoris parcials en cancel·lar o fallar una transferència. Verifica les empremtes
d'amfitrions desconeguts abans d'acceptar-les; els canvis de clau es rebutgen.

## Crear un paquet Debian

Des de l'arrel del repositori a Ubuntu 24.04+ o un sistema Debian compatible:

```bash
sudo apt build-dep .
dpkg-buildpackage -us -uc -b
```

El paquet es crea al directori pare com a `termia_0.6.1~beta-1_all.deb`.
És independent del fitxer oficial de la release.

## Documentació

- [Contribució i validació](../CONTRIBUTING.md)
- [Laboratoris Docker](../tools/docker-lab/README.ca.md)
- [Versionat](VERSIONING.md) i [migracions de dades](STORAGE_MIGRATIONS.md)
- [Arquitectura](architecture/overview.md)

## Llicència

[GNU GPL v3.0 o posterior](../LICENSE). El sistema operatiu proporciona les
dependències per separat; consulta els [avisos de tercers](../THIRD_PARTY_NOTICES.md).
