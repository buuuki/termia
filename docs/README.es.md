# Termia

Termia es un gestor de conexiones SSH para escritorios Linux desarrollado con
Python, GTK 4 y terminales VTE embebidas.

Documentación principal en inglés: [../README.md](../README.md)
Documentación en catalán: [README.ca.md](README.ca.md)

## Funciones

- Crear, editar, mover y eliminar grupos y subgrupos de servidores.
- Guardar servidores con nombre, host o IP, usuario, puerto, contraseña y ruta de
  clave privada.
- Filtrar servidores y abrir varias sesiones al mismo host en pestañas.
- Usar pestañas embebidas que reparten el ancho disponible y mover una pestaña a una ventana independiente.
- Abrir terminales locales embebidas.
- Guardar estadísticas locales agregadas de conexiones, comandos, pulsaciones, duración y uso por servidor.
- Abrir un dashboard de estadísticas con tarjetas de métricas, resumen de duración y servidores más usados.
- Mostrar u ocultar globalmente la barra de estado de sesión, ocultarla por sesión y restaurarla desde el menú contextual del terminal.
- Configurar confirmaciones para desconectar sesiones y cerrar Termia.
- Enviar opcionalmente la contraseña SSH guardada a un terminal remoto con `Ctrl+P`, con o sin `Enter`.
- Configurar por separado opciones generales, fuente y colores del terminal VTE, y el prompt PS1.
- Personalizar el prompt local con colores, temas predefinidos y prefijos de hora o fecha sin cambiar ficheros de inicio ni comandos remotos.
- Usar la interfaz en castellano, catalán o inglés. El idioma inicial sigue el locale del sistema cuando está soportado.
- Importar y exportar configuraciones de Termia.
- Importar conexiones y grupos anidados básicos desde YAML de Asbru.

## Notas de uso

El menú `Configuración` se divide en `General`, `Terminal` y `Prompt`:

- `General` controla tema, idioma, confirmaciones, comportamiento al iniciar, atajos de contraseña y barra de estado de sesión.
- `Terminal` controla la fuente, tamaño, colores y paletas del terminal VTE embebido.
- `Prompt` personaliza el PS1 de terminales locales con color, temas predefinidos y prefijos de hora o fecha. No altera comandos SSH ni modifica ficheros de inicio remotos.

Cada sesión puede mostrar una barra de estado con estado, PID, tiempo transcurrido, botón compacto para ocultarla y desconexión. Puedes activar o desactivar las barras de estado desde `General`; si ocultas la barra de una sesión, puedes recuperarla con botón derecho dentro del terminal y `Mostrar barra de estado de la sesión`. La barra lateral de servidores tiene su propio botón en la cabecera.

## Entorno probado

Termia se ha probado en Ubuntu 24.04.4 LTS con kernel Linux
6.8.0-117-generic, GNOME 46.0 y Wayland.

## Descargar e instalar

Clona el repositorio completo:

```bash
git clone https://github.com/buuuki/termia.git
cd termia
chmod +x scripts/install_dependencies.sh
```

Comprueba primero las dependencias sin modificar el sistema:

```bash
./scripts/install_dependencies.sh --check
```

Si la comprobación indica que faltan dependencias, instálalas con:

```bash
./scripts/install_dependencies.sh
```

El instalador verifica el resultado después de instalar. También intenta instalar JetBrains Mono para la fuente por defecto del terminal; si no está disponible, Termia usa Ubuntu Mono o Monospace como fallback. Puedes repetir la
comprobación en cualquier momento:

```bash
./scripts/install_dependencies.sh --check
```

Si la comprobación indica que falta el namespace `Vte 3.91`, falta el paquete de
introspección GTK 4 VTE. En Debian, Ubuntu o Linux Mint el paquete necesario es
`gir1.2-vte-3.91`.

Instala el lanzador de escritorio con:

```bash
./scripts/install_desktop.sh
```

También puedes ejecutar Termia directamente desde el repositorio:

```bash
python3 run_termia.py
```

Elimina únicamente el lanzador de escritorio:

```bash
./scripts/uninstall_desktop.sh
```

## Datos del usuario y seguridad

Las conexiones, preferencias y estadísticas se guardan fuera del repositorio:

```text
~/.config/termia/connections.json   # grupos y servidores
~/.config/termia/settings.json      # configuración de la app y del terminal
~/.local/state/termia/statistics.json
```

Las contraseñas guardadas se almacenan en `connections.json`; el fichero puede mantenerse en texto plano u ofuscado desde las preferencias de Seguridad. La ofuscación no es cifrado.
Los ficheros de conexiones exportados también pueden contener credenciales.
Los contadores locales agregados se guardan por separado en `statistics.json`.

Termia no guarda el texto escrito, el contenido de los comandos ni el contenido del
portapapeles. Las estadísticas se escriben como máximo cada 30 segundos mientras se
escribe, al finalizar sesiones y al cerrar Termia. Consulta
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
