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

Usa la rama activa de desarrollo, que contiene el laboratorio publicado.

```bash
git clone https://github.com/buuuki/termia.git
cd termia
git switch release/0.6.0-beta.4-dev
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

Los comandos existentes `churn-disabled` y `churn-enabled` usan X11. Para
probar ambos casos como clientes Wayland sobre Weston aislado:

```bash
bash tools/docker-lab/run.sh run churn-disabled-wayland
bash tools/docker-lab/run.sh wait
bash tools/docker-lab/run.sh run churn-enabled-wayland
bash tools/docker-lab/run.sh wait
```

Comprueba en el `result.json` de cada probe que `runtime.display` sea
`GdkWaylandDisplay`, `completed` sea true, `retention_detected` sea false y
`cleanup.running_children` sea cero. Revisa las muestras de memoria; terminar
no demuestra ausencia de fugas. Weston se ejecuta sobre Xvfb privado; estas
pruebas no cubren GNOME/Mutter. Compara memoria dentro del mismo entorno y caso.

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

## VM Ubuntu observable: sudo y polkit reales

Para observar la instalación y actualización con autorización real del sistema,
usa la VM opcional Ubuntu 24.04 con XFCE/X11. El laboratorio Docker anterior
sigue disponible para las pruebas ligeras de X11 y Wayland.

Requisitos: Linux x86-64, `/dev/kvm` utilizable, Docker local, Python 3, navegador,
puerto 6081, 4 GB de RAM disponibles y 15 GB de disco. La preparación descarga
la imagen oficial de Ubuntu, verifica su SHA256SUMS por HTTPS y descarga el
paquete beta.3 con hash fijado. La instalación inicial del escritorio necesita
Internet. No se instalan paquetes ni se utiliza la sesión gráfica del anfitrión.

Desde la raíz del repositorio:

```bash
python3 tools/docker-lab/vm.py prepare
python3 tools/docker-lab/vm.py start
python3 tools/docker-lab/vm.py status
```

Abre la URL que imprime `start`, normalmente
`http://127.0.0.1:6081/vnc.html?autoconnect=1&resize=scale`.
Espera a ver el panel XFCE; la preparación puede tardar varios minutos.
`status` muestra el progreso hasta `DESKTOP_READY`. El panel muestra la contraseña
sintética generada para la VM. Cuando estés observándolo, habilita las pruebas:

```bash
python3 tools/docker-lab/vm.py ready
```

Pulsa los seis botones del panel en orden. En el primero espera la petición de
contraseña sudo y cancela con Ctrl+C. En el segundo introduce la contraseña de
la VM. El tercero verifica el paquete candidato. En el cuarto cancela el diálogo
gráfico de autorización; en el quinto autorízalo con la contraseña de la VM.
El sexto comprueba conexiones, grupos, snippets, notas y su copia de seguridad.
No cambies los datos sintéticos ni lances otra prueba mientras haya una activa.
También puedes enviar cada fase desde la terminal, esperando su resultado antes
de continuar:

```bash
python3 tools/docker-lab/vm.py trial source-cancel
python3 tools/docker-lab/vm.py trial source-accept
python3 tools/docker-lab/vm.py trial debian-prepare
python3 tools/docker-lab/vm.py trial debian-cancel
python3 tools/docker-lab/vm.py trial debian-accept
python3 tools/docker-lab/vm.py trial verify
python3 tools/docker-lab/vm.py show
python3 tools/docker-lab/vm.py evidence
```

Exige `running: false` y `passed: true` en el JSON de cada fase; arrancar una
prueba no significa superarla. Los resultados se guardan en la VM bajo
`/home/lab/termia-lab-evidence`; `evidence` exporta un archivo y una captura a
`.runtime/visible-vm/results`. `guest /bin/cat /home/lab/termia-lab-evidence/state.json`
consulta el estado. `guest` usa el agente local de QEMU, sin SSH; un comando que
supere 45 segundos puede seguir ejecutándose y debe inspeccionarse antes de repetirlo.

```bash
python3 tools/docker-lab/vm.py stop
python3 tools/docker-lab/vm.py remove
```

Los discos y evidencias se conservan. Tras parar y quitar el contenedor, mueve
`.runtime/visible-vm` a otro destino antes de preparar una VM nueva. No se
sobrescribe un laboratorio preparado ni se limpian recursos ajenos.
Usa `start --port 6082` si necesitas otro puerto local.

Es un ensayo beta.3 → beta.4 local: solo cambia la versión en una copia temporal,
sin publicar releases ni tags. La descarga candidata usa una fixture local;
queda validar el artefacto final y la descarga pública. No certifica Ubuntu
26.04 ni Wayland. Solo se copian archivos versionados permitidos, incluidos sus
cambios actuales. Discos, contraseñas, datos y capturas quedan ignorados. Usa
solo datos sintéticos y no expongas el visor, que no tiene autenticación.
El contenedor recibe únicamente el directorio de ejecución y `/dev/kvm`, con
recursos limitados y sin capacidades, socket Docker ni perfil personal. Las
imágenes y los repositorios APT no son instantáneas fijadas.
