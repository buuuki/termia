# Reproducir el laboratorio Docker de Termia

[English](README.md) · [Català](README.ca.md)

Este paquete permite reconstruir el escritorio visual, los servidores sintéticos
SSH/SFTP/SCP y las pruebas de memoria y ciclos de vida desde un clon nuevo. El
cliente monta el código en solo lectura, sin tu escritorio, agente SSH ni perfil
personal de Termia.

## Primer arranque en otro PC

Necesitas Linux, Docker Engine local accesible para tu usuario, Git, Python 3,
`ssh-keygen` (cliente OpenSSH), un navegador, el puerto 6080 libre y varios GB
de disco y RAM disponibles. Zenity y `xdg-open` son opcionales para el gestor.
La imagen usa Ubuntu 24.04. La construcción descarga paquetes; las redes SSH
de ejecución son internas. No se han validado Windows/macOS ni Docker remoto.

Mientras #377 esté pendiente de fusión, usa su rama de publicación. Después de
fusionarla, el paquete también estará en la rama activa de desarrollo.

```bash
git clone https://github.com/buuuki/termia.git
cd termia
git switch maintenance/377-docker-lab
docker info
bash tools/docker-lab/run.sh prepare
bash tools/docker-lab/run.sh check
bash tools/docker-lab/run.sh start
```

Abre la dirección que imprime `start`, normalmente
`http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale`.
El panel inferior inicia Termia con 16 pestañas locales y dos conexiones SSH
sintéticas guardadas: contraseña y clave. Úsalas para probar SSH, SFTP y envío
de archivos. La contraseña generada se carga automáticamente; no debes copiar
contraseñas ni claves del PC anterior. El servidor contiene archivos sintéticos
en `/home/lab/pruebas`.

Cierra Termia normalmente y pulsa **Iniciar / nueva prueba** para obtener un
perfil nuevo. El panel permite elegir Wayland/X11, pestañas (1–40), trazas y GDB.
Los cambios de código se cargan al crear un proceso nuevo. Si cambias scripts o
dependencias del laboratorio, ejecuta `prepare`, detén y elimina el contenedor
del escritorio y vuelve a iniciarlo. Para usar otro puerto en un escritorio nuevo:

```bash
LAB_PORT=6081 bash tools/docker-lab/run.sh start
```

## Gestionar el escritorio

```bash
bash tools/docker-lab/manage.sh
```

El gestor Zenity opcional usa etiquetas comunes en inglés; el panel del
escritorio conserva las etiquetas en español. También puedes usar la consola:

| Comando tras `bash tools/docker-lab/run.sh` | Resultado |
| --- | --- |
| `start`, `url` | Iniciar el escritorio o mostrar su dirección |
| `status-desktop`, `logs` | Consultar recursos de este clon y registro del contenedor |
| `restart` | Reiniciar el contenedor; interrumpe sus sesiones |
| `restart-wayland` | Reiniciar solo Weston; interrumpe las aplicaciones Wayland |
| `stop-desktop` | Detener escritorio y servidor SSH manual |
| `remove` | Eliminar el escritorio detenido para usar imágenes reconstruidas |
| `monitor`, `stop monitor` | Iniciar/detener observación pasiva de memoria |
| `cleanup` | Eliminar contenedores/redes propios; conservar imágenes, credenciales y resultados |

Cierra las sesiones antes de reiniciar o detener. Las operaciones comprueban
la propiedad de los recursos y no ejecutan una limpieza general de Docker.
Cada ruta de clon tiene nombres diferentes; este paquete no toca el laboratorio
antiguo que permanece en el directorio ignorado.

## Ejecutar un ensayo

Ejecuta un único diagnóstico a la vez. Este ejemplo inicia el trabajo en segundo
plano y espera su resultado final; iniciarlo no demuestra que haya pasado.

```bash
bash tools/docker-lab/run.sh run ssh-smoke
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh status
```

| Modo | Prueba |
| --- | --- |
| `smoke-x11`, `smoke-wayland` | Arranque, creación/selección/cierre de terminales y limpieza de procesos |
| `ssh-smoke` | SSH con contraseña y clave, comparación de subida/bajada SFTP y limpieza |
| `lifecycle` | Cierre de paneles, pestañas, ventanas y aplicación; cancelación SCP/SFTP activos |
| `memory`, `memory-trace` | 20 ciclos mixtos, hashes, RSS/memoria privada y referencias débiles; tracemalloc opcional |
| `close-live` | Cierre desde la cruceta nativa con SSH/SFTP y una subida activa |
| `menus` | 300 aperturas del mismo menú nativo de pestañas |
| `churn-disabled`, `churn-enabled` | 20 ciclos de terminales con herramientas opcionales desactivadas/activadas |
| `behavior-x11`, `behavior-wayland` | Arrastres y cancelaciones mediante eventos de ratón |
| `valgrind` | Diagnóstico de asignaciones nativas; mucho más lento |

Para un ensayo corto de memoria, o cancelar el diagnóstico de este clon:

```bash
LAB_MEMORY_CYCLES=1 bash tools/docker-lab/run.sh run memory
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh stop diagnostic
```

Los diagnósticos usan cliente y servidor independientes de tus conexiones SSH
manuales. Los resultados se guardan en `.runtime/evidence/`, junto a esta guía:
los manifiestos indican huellas del código, fechas, finalización/cancelación y
registros. Revisa también `result.json` y las muestras de cada modo. Terminar no
certifica ausencia de fugas: comprueba objetos retenidos, trabajadores y conexiones,
y distingue calentamiento del asignador y coste de trazas de retención real.
Los experimentos de GC/asignador de las sondas son diagnósticos, no arreglos de producción.

## Privacidad, reconstrucción y límites

`prepare` crea contextos nuevos con una lista de archivos permitidos. Solo entran
el código/recursos de la aplicación seguidos por Git y los scripts indicados del
laboratorio. La imagen del servidor contiene scripts, sin credenciales. Las claves
y contraseñas sintéticas se generan localmente al preparar/iniciar y se montan
durante la ejecución. `.runtime/` está ignorado. No debes subir ni trasladar al
otro PC imágenes, claves, perfiles, volcados, registros, capturas ni archivos históricos.

Los resultados pueden contener rutas locales y lo que escribas en el laboratorio;
consérvalos privados y usa datos sintéticos. noVNC escucha solo en loopback y no
tiene autenticación: no publiques ese puerto. El cliente usa tu UID numérico,
raíz de solo lectura, hogar temporal, renderizado por software y límites de recursos.
El cliente visual permite ptrace para GDB, sin modo privilegiado ni socket de Docker.
El escritorio visual usa el puente normal de Docker para el puerto local del
navegador y una red interna adicional para SSH. Los clientes de diagnóstico usan
solo su red SSH interna, o ninguna red en las pruebas exclusivamente visuales.

Los repositorios Ubuntu no están fijados a una instantánea: reconstruir puede
cambiar GTK/VTE. El escritorio registra versiones de paquetes y huellas del código.
Se reproduce el montaje, no una imagen idéntica bit a bit ni una certificación
de release. Los ensayos largos y las actualizaciones de sistemas soportados
necesitan validación independiente. Consulta el [registro de investigación](../../docs/DOCKER_LABORATORY.md)
y las [comprobaciones de regresión](../../docs/REGRESSION_CHECKS.md).

Si falla el arranque, revisa `status-desktop`, `logs` y `.runtime/evidence/desktop`.
Si falla el permiso de Docker, corrige primero el acceso al daemon local;
evita alternar ejecuciones como root y como usuario en el mismo directorio de resultados.
