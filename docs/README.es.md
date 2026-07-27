# Termia

Termia es un gestor de conexiones SSH para escritorios Linux desarrollado con
Python, GTK 4 y terminales VTE embebidas.

Documentación principal en inglés: [../README.md](../README.md)
Documentación en catalán: [README.ca.md](README.ca.md)

## Funciones

- Ejecutar conexiones SSH y terminales locales en terminales VTE de GTK 4 integrados.
- Trabajar con varias pestañas, ventanas independientes y paneles de terminal divididos.
- Guardar diseños de división por servidor SSH o perfil de terminal local para reabrir un espacio de trabajo preparado.
- Subir ficheros locales a servidores remotos con SCP desde el menú contextual del terminal o del servidor.
- Mantener los datos de conexión en local con almacenamiento en texto plano, ofuscado o cifrado opcional protegido por una contraseña maestra.
- Organizar conexiones con grupos anidados, favoritos y una sección Recent sin duplicados; encontrarlas rápidamente con `Ctrl+F`.
- Guardar host, usuario, puerto, contraseña y ruta de clave privada de cada conexión SSH.
- Importar y exportar configuración de Termia, incluidas conexiones básicas, grupos anidados y credenciales disponibles de YAML de Asbru.
- Consultar el historial de conexiones y estadísticas locales opcionales de uso, incluidas duraciones y servidores más usados.
- Personalizar colores y fuente del terminal, prompts locales, atajos, confirmaciones, barras de estado de sesión, idioma y comportamiento seguro con varias instancias.

## Descargar e instalar

Clona el repositorio completo:

```bash
git clone https://github.com/buuuki/termia.git
cd termia
chmod +x scripts/termia-setup.sh
```

Instala las dependencias que falten, comprueba el resultado y añade el lanzador
local de Termia con:

```bash
./scripts/termia-setup.sh install
```

Antes de modificar el sistema, el script muestra las acciones previstas y espera
10 segundos para poder cancelarlo. En Debian, Ubuntu y Linux Mint, si `apt-get
update` falla porque algún repositorio configurado no está disponible, pregunta
antes de usar la caché APT disponible para instalar los paquetes necesarios.
Si todas las dependencias de ejecución ya están disponibles, no ejecuta el gestor
de paquetes del sistema.

El instalador verifica el resultado después de instalar. También intenta instalar JetBrains Mono para la fuente por defecto del terminal; las instalaciones nuevas usan la paleta Polaris y el color blanco del prompt por defecto, y si no está disponible, Termia usa Ubuntu Mono o Monospace como fallback.

Si la comprobación indica que falta el namespace `Vte 3.91`, falta el paquete de
introspección GTK 4 VTE. En Debian, Ubuntu o Linux Mint el paquete necesario es
`gir1.2-vte-3.91`.

También puedes ejecutar Termia directamente desde el repositorio:

```bash
python3 run_termia.py
```

Para probar una rama sin cerrar la ventana habitual de Termia, inicia un perfil
aislado. Utiliza una configuración, estado y bloqueo de escritura propios:

```bash
./scripts/run_test_instance.sh --copy-current-config pr-152
```

La opción copia las conexiones, ajustes, historial de conexiones, estadísticas y
el registro de depuración en el perfil de pruebas. Los cambios realizados allí
nunca modifican los datos habituales de Termia.

Para obtener información de diagnóstico sobre GTK, VTE, los bloqueos de
almacenamiento, el cifrado y el arranque en modo solo lectura, activa `Modo
debug` en las preferencias Generales. También puedes activarlo para una ejecución con:

```bash
python3 run_termia.py --debug
```

La información se guarda en `~/.local/state/termia/debug.log`. No registra
contraseñas ni el contenido de las conexiones.

Elimina únicamente el lanzador de escritorio, sin borrar ajustes, conexiones,
estadísticas ni paquetes del sistema:

```bash
./scripts/termia-setup.sh uninstall
```

## Crear un paquete Debian

En Debian, Ubuntu 24.04 o posterior, o una distribución compatible, instala las
dependencias de compilación y crea el paquete desde la raíz del repositorio.
Ubuntu 22.04 y anteriores no incluyen el entorno VTE para GTK 4 necesario:

```bash
sudo apt build-dep .
dpkg-buildpackage -us -uc -b
```

El fichero `termia_0.5.0~beta-4_all.deb` se crea en el directorio padre.
Instálalo con:

```bash
sudo apt install ../termia_0.5.0~beta-4_all.deb
```

El paquete Debian instala el comando `termia`, el lanzador de escritorio y el
icono; APT instala las dependencias de GTK, VTE, Python, SSH y cifrado.

## Notas de uso

El menú `Configuración` se divide en `General`, `Terminal`, `Prompt`, `Atajos` y `Seguridad`:

- `General` controla tema, idioma, confirmaciones, comportamiento al iniciar, atajos de contraseña y barra de estado de sesión, que empieza oculta por defecto.
- `Terminal` controla la fuente, tamaño, colores, grosor y color del separador de división, y paletas del terminal VTE embebido. Las instalaciones nuevas empiezan con JetBrains Mono y la paleta Polaris.
- `Prompt` personaliza el PS1 de terminales locales con color, temas predefinidos y prefijos de hora o fecha. El color predeterminado del prompt es blanco. No altera comandos SSH ni modifica ficheros de inicio remotos.
- `Atajos` muestra los atajos activos y permite grabar combinaciones para acciones como filtrar servidores, mostrar la lista, abrir un terminal local, navegar por el foco, copiar, pegar, cambiar de pestaña, ampliar la fuente y enviar la contraseña guardada. `Ctrl+F` enfoca el filtro, `Ctrl+Shift+B` muestra u oculta la lista, `F10` abre o cierra el menú principal, `Ctrl+Shift+T` abre un terminal local y `Ctrl+F6`/`Ctrl+Shift+F6` recorre las regiones principales. Las demás teclas de función sin modificadores se envían a las aplicaciones del terminal.
- `Seguridad` controla el modo de almacenamiento de conexiones.
- Usa el botón con forma de terminal de la barra lateral para crear un nuevo perfil de terminal local; aparece en la lista como una conexión y se abre en una terminal incrustada al activarlo.
- Si otra instancia de Termia ya tiene el bloqueo de escritura, una nueva ventana se abre en modo solo lectura, muestra un indicador en la cabecera, desactiva las acciones que escriben y sigue permitiendo navegar, conectar y exportar la configuración.
- Haz clic derecho en un terminal o en un servidor para subir ficheros a `/tmp/.termia/` en el host destino.
- El menú principal incluye historial de conexiones, ubicaciones de ficheros de datos y acciones de importación/exportación.

Cada sesión puede mostrar una barra de estado con estado, PID, tiempo transcurrido, botón compacto para ocultarla y desconexión. Puedes activar o desactivar las barras de estado desde `General`; si ocultas la barra de una sesión, puedes recuperarla con botón derecho dentro del terminal y `Mostrar barra de estado de la sesión`. La barra lateral de servidores tiene su propio botón en la cabecera. Con botón derecho dentro del terminal puedes abrir los submenús traducidos de `Dividir` y `Pestaña`; los paneles se pueden crear arriba, abajo, a la izquierda o a la derecha, y desaparecen automáticamente cuando su shell termina. Una pestaña solo se cierra con `exit` cuando ha salido el último terminal y ya no quedan paneles divididos.

## Entorno probado

Termia se ha probado en Ubuntu 24.04.4 LTS con kernel Linux
6.8.0-117-generic, GNOME 46.0 y Wayland.

## Base de ejecución compatible

Termia requiere Python 3.10 o posterior, GTK 4.0/GDK 4.0 y el espacio de
introspección de VTE para GTK 4, `Vte 3.91`. El entorno actual de validación
proporciona GTK 4.14.5 y VTE 0.76.0. Las comprobaciones de compatibilidad para
métodos GTK opcionales como `set_handle_menubar_accel` y
`set_show_separators` son intencionadas, porque las distribuciones pueden
exponer distintos niveles de API de GTK.

## Datos del usuario y seguridad

Las conexiones, preferencias y estadísticas se guardan fuera del repositorio:

```text
~/.config/termia/connections.json   # grupos y servidores
~/.config/termia/settings.json      # configuración de la app y del terminal
~/.config/termia/instance.lock      # bloqueo de escritor único para el modo multiinstancia
~/.local/state/termia/recent_connections.jsonl
~/.local/state/termia/statistics.json
```

Las contraseñas guardadas se almacenan en `connections.json`; el fichero puede mantenerse en texto plano, ofuscado o cifrado con una contraseña maestra desde las preferencias de Seguridad. Cuando el cifrado está activado, Termia pide la contraseña maestra al arrancar y no puede recuperar los datos de conexión si esa contraseña se pierde. Las contraseñas importadas desde Ásbrú se guardan igual cuando el YAML de origen las expone en el campo `pass`.
Los ficheros de conexiones exportados también pueden contener credenciales.
Los contadores locales agregados se guardan por separado en `statistics.json`, vienen desactivados por defecto y se pueden activar o desactivar desde las preferencias generales. Cuando hay varios procesos de Termia abiertos al mismo tiempo, solo la instancia que mantiene `instance.lock` escribe conexiones, ajustes o estadísticas; las siguientes permanecen en solo lectura para evitar corromper esos ficheros.
Las conexiones recientes se guardan aparte en `recent_connections.jsonl` para que la barra lateral pueda mostrar una sección Recent pequeña y sin duplicados basada en las últimas conexiones SSH correctas.

Termia no guarda el texto escrito, el contenido de los comandos, el contenido del
portapapeles, contadores de comandos ni contadores de pulsaciones. Cuando están activadas, las estadísticas solo registran conexiones agregadas, uso por servidor y duración de sesiones; se escriben como máximo cada 30 segundos, al finalizar sesiones y al cerrar Termia. Consulta
[../SECURITY.md](../SECURITY.md).

Python puede crear directorios `__pycache__/` junto a los módulos ejecutados.
Solo contienen bytecode generado, están excluidos por `.gitignore` y no deben
subirse a GitHub.

## Estructura

```text
run_termia.py                     Lanzador para ejecutar desde el repositorio
src/termia/app.py             Composición principal y ventana
src/termia/                Módulos de almacenamiento, diálogos, pestañas, terminales y utilidades
src/termia/assets/            Imágenes utilizadas por Termia
scripts/                      Instalación y desinstalación
docs/                         Documentación adicional
LICENSE                       Licencia GPL-3.0-o-posterior
```

## Licencia

Termia se publica bajo la [GNU General Public License v3.0 o posterior](../LICENSE). Las dependencias se instalan
por separado mediante el gestor de paquetes del sistema. Consulta
[../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
