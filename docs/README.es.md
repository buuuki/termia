# Termia

Termia es un gestor de conexiones SSH y espacios de trabajo de terminal para Linux.
Reúne sesiones locales y remotas, espacios de trabajo guardados y transferencias
de archivos en terminales VTE integrados con GTK 4.

![Termia con varias sesiones SSH integradas](../img/termia-screenshot.png)

[English](../README.md) · [Català](README.ca.md) · [Hoja de ruta](../ROADMAP.md)

## Características

- Terminales locales y SSH con pestañas, paneles divididos y ventanas separables.
- Conexiones organizadas en grupos anidados, favoritos y conexiones recientes.
- Espacios de trabajo guardados y restauración opcional de la sesión anterior.
- Subidas SCP y explorador SFTP nativo con transferencias y cancelación.
- Snippets reutilizables con categorías, ámbito, variables y atajos;
  los comandos se previsualizan antes de enviarlos.
- Notas personales o asociadas a servidores, con guardado automático,
  categorías e importación/exportación.
- Datos de conexión locales con cifrado opcional mediante contraseña maestra.
- Importación/exportación de Termia e importación de conexiones desde Ásbrú YAML.
- Historial de conexiones y complementos opcionales de Estadísticas y SFTP.
- Apariencia y atajos configurables; interfaz en castellano, catalán e inglés.

## Estado de la versión

**[0.6.1-beta](https://github.com/buuuki/termia/releases/tag/v0.6.1-beta)** es una
versión preliminar de mantenimiento. Consulta [CHANGELOG.md](../CHANGELOG.md)
para ver los cambios desde 0.6.0-beta.4.

## Instalar en Ubuntu 24.04 o posterior

Paquete Debian:
[termia_0.6.1.beta-1_all.deb](https://github.com/buuuki/termia/releases/download/v0.6.1-beta/termia_0.6.1.beta-1_all.deb).

```bash
sudo apt install ./termia_0.6.1.beta-1_all.deb
```

APT instala las dependencias necesarias, el lanzador y el icono.
Abre **Termia** desde el menú de aplicaciones o ejecuta `termia`.

### Ejecutar desde el código fuente

```bash
git clone https://github.com/buuuki/termia.git
cd termia
./scripts/termia-setup.sh install
python3 run_termia.py
```

El script comprueba las dependencias e instala un lanzador para el usuario.
Admite los gestores de paquetes de Debian/Ubuntu/Linux Mint, Fedora y Arch.
Reinicia Termia solo cuando termine correctamente; repítelo si mueves el checkout.
Usa `./scripts/termia-setup.sh uninstall` para quitar el lanzador conservando los datos.

### Requisitos

Python 3.10+, GTK 4, GtkSourceView 5 y el namespace VTE para GTK 4 `Vte 3.91`.
Las comprobaciones se realizan en laboratorios Ubuntu 24.04 y 26.04.
Ubuntu 22.04 y anteriores no proporcionan el VTE para GTK 4 necesario.

## Actualizaciones

**Beta.3 y beta.4 requieren una primera actualización manual a 0.6.1-beta.**
Haz una copia del perfil, cierra Termia e instala el nuevo .deb sobre el anterior.
No hace falta desinstalar primero.

Para un checkout limpio, una vez publicada la etiqueta:

```bash
git status --short
git fetch https://github.com/buuuki/termia.git tag v0.6.1-beta
git merge --ff-only v0.6.1-beta
./scripts/termia-setup.sh install
```

Detente si el primer comando muestra cambios locales o el merge no puede avanzar
mediante fast-forward. Completa el setup antes de reiniciar y consulta la
[compatibilidad de datos](STORAGE_MIGRATIONS.md) antes de volver a una versión anterior.

Desde 0.6.1-beta, **Acerca de → Buscar actualizaciones** detecta versiones de
mantenimiento beta/RC posteriores de la misma serie MAJOR.MINOR, incluidas
versiones estables posteriores. Las instalaciones estables solo reciben estables.

El actualizador verifica las descargas y revisa las dependencias antes de instalar.
Las instalaciones compatibles desde Git o Debian pueden usar la autorización
administrativa nativa para los paquetes necesarios. Git requiere un checkout limpio
de una release en main o en su etiqueta; las ramas de desarrollo y cambios locales
se actualizan manualmente. En casos no compatibles se conserva el enlace oficial.
Deja terminar la instalación y reinicia Termia; no actualiza revisiones exclusivamente
Debian de la misma versión de la aplicación.

## Ayuda y pruebas aisladas

Abre **Ayuda** desde el menú principal para consultar los flujos de uso y tus atajos.
Los complementos opcionales de Estadísticas y SFTP se gestionan desde
**Complementos**; los cambios requieren reiniciar y desactivarlos conserva sus datos.

Para probar un checkout con un perfil vacío o una copia separada de tus datos:

```bash
./scripts/run_test_instance.sh --fresh
./scripts/run_test_instance.sh --copy-current-config review
```

El primer comando crea un perfil vacío; el segundo copia los datos actuales.
Ninguno modifica tu perfil habitual. Consulta
[CONTRIBUTING.md](../CONTRIBUTING.md) para las comprobaciones y el diagnóstico.

## Datos y seguridad

La configuración y las notas se guardan en `~/.config/termia/`; el historial y
las estadísticas, en `~/.local/state/termia/`. Haz una copia antes de actualizar.
Las credenciales y exportaciones pueden contener contraseñas legibles si no se
cifran. La ofuscación no es cifrado y una contraseña maestra perdida no se recupera.

Los comandos de inicio SSH se ejecutan cada vez que se inicia su conexión;
trátalos como configuración ejecutable. Termia no registra los comandos del
terminal, su salida ni las pulsaciones. Consulta [SECURITY.md](../SECURITY.md)
para el almacenamiento, las exportaciones y las actualizaciones.

El explorador SFTP admite los datos guardados, claves del agente SSH o por defecto
y contraseñas; no admite alias de OpenSSH, ProxyJump, proveedores de claves físicas
ni MFA interactivo. No sobrescribe destinos existentes y puede dejar archivos o
directorios parciales al cancelar o fallar una transferencia. Verifica las huellas
de hosts desconocidos antes de aceptarlas; los cambios de clave se rechazan.

## Crear un paquete Debian

Desde la raíz del repositorio en Ubuntu 24.04+ o un sistema Debian compatible:

```bash
sudo apt build-dep .
dpkg-buildpackage -us -uc -b
```

El paquete se crea en el directorio padre como `termia_0.6.1~beta-1_all.deb`.
Es independiente del archivo oficial de la release.

## Documentación

- [Contribución y validación](../CONTRIBUTING.md)
- [Laboratorios Docker](../tools/docker-lab/README.es.md)
- [Versionado](VERSIONING.md) y [migraciones de datos](STORAGE_MIGRATIONS.md)
- [Arquitectura](architecture/overview.md)

## Licencia

[GNU GPL v3.0 o posterior](../LICENSE). El sistema operativo proporciona las
dependencias por separado; consulta los [avisos de terceros](../THIRD_PARTY_NOTICES.md).
