# Termia

Termia es un gestor de conexiones SSH para escritorios Linux desarrollado con
Python, GTK 4 y terminales VTE embebidas.

Documentación principal en inglés: [../README.md](../README.md)

## Funciones

- Crear, editar, mover y eliminar grupos y subgrupos de servidores.
- Guardar servidores con nombre, host o IP, usuario, puerto, contraseña y ruta de
  clave privada.
- Filtrar servidores y abrir varias sesiones al mismo host en pestañas.
- Reordenar pestañas arrastrándolas y mover una pestaña a una ventana independiente.
- Abrir terminales locales embebidas.
- Guardar estadísticas locales agregadas de conexiones, comandos, pulsaciones y duración.
- Mostrar estadísticas por terminal y cerrar opcionalmente la pestaña al desconectar.
- Configurar confirmaciones para desconectar sesiones y cerrar Termia.
- Enviar opcionalmente la contraseña SSH guardada a un terminal remoto con `Super+Shift+P`, con o sin `Enter`.
- Configurar fuente, tamaño, colores y tema del terminal.
- Usar la interfaz en castellano, catalán o inglés.
- Importar y exportar configuraciones de Termia.
- Importar conexiones y grupos anidados básicos desde YAML de Asbru.

## Entorno probado

Termia se ha probado en Ubuntu 24.04.4 LTS con kernel Linux
6.8.0-117-generic, GNOME 46.0 y Wayland.

## Descargar e instalar

Clona el repositorio completo:

```bash
git clone https://github.com/buuuki/termia.git
cd termia
chmod +x scripts/*.sh
./scripts/install_dependencies.sh
./scripts/install_desktop.sh
```

También puedes ejecutar Termia directamente desde el repositorio:

```bash
python3 run_termia.py
```

Comprueba dependencias sin modificar el sistema:

```bash
./scripts/install_dependencies.sh --check
```

Elimina únicamente el lanzador de escritorio:

```bash
./scripts/uninstall_desktop.sh
```

## Datos del usuario y seguridad

Las conexiones y preferencias se guardan fuera del repositorio:

```text
~/.config/termia/connections.json
```

Las contraseñas guardadas y los ficheros exportados pueden contener credenciales
en texto plano. Los contadores locales agregados se guardan por separado en:

```text
~/.local/state/termia/statistics.json
```

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
src/termia/app.py             Implementación de la aplicación
src/termia/assets/            Imágenes utilizadas por Termia
scripts/                      Instalación y desinstalación
docs/                         Documentación adicional
LICENSE                       Licencia MIT
```

## Licencia

Termia se publica bajo la [licencia MIT](../LICENSE). Las dependencias se instalan
por separado mediante el gestor de paquetes del sistema. Consulta
[../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
