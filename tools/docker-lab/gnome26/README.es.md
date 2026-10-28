# Laboratorio Ubuntu 26.04 GNOME: escritorio experimental

[English](README.md) · [Català](README.ca.md)

La issue #430 dispone de un prototipo funcional de GNOME sobre Wayland con
RDP, ejecutado directamente con Docker. Termia y el panel aún no están
integrados. Se revisarán contigo las siguientes personalizaciones,
optimizaciones y medidas de aislamiento. El laboratorio sigue incompleto.

## Reconstrucción en otro PC y alcance de la portabilidad

Las recetas permiten reconstruir el sistema; no hace falta exportar una imagen,
importar un disco ni instalar manualmente Ubuntu dentro de un volumen. A fecha
2026-10-28, el despliegue sigue en desarrollo en la rama
`maintenance/430-docker-gnome`. Usar esa rama y registrar el commit elegido;
`main` no contiene este despliegue. No se ha validado aún
la reconstrucción en un segundo PC ni una segunda descarga sin caché.

```bash
git clone --branch maintenance/430-docker-gnome --single-branch https://github.com/buuuki/termia.git
cd termia
git rev-parse HEAD
```

| Requisito del anfitrión | Estado o motivo |
| --- | --- |
| Linux x86-64 y Docker Engine local con permisos suficientes | Probado en kernel 6.8, Engine 28.5.1, Compose 2.40.0 y cgroups v2 con driver systemd |
| Cgroups privados y remontaje con escritura | Systemd se ejecuta dentro del contenedor; depende del kernel y de los permisos del runtime |
| FUSE y dispositivo `/dev/fuse` | Necesarios para los montajes de GNOME; no se instala ni carga un módulo del anfitrión automáticamente |
| Política de seguridad compatible | `SYS_ADMIN`, AppArmor sin confinamiento para este contenedor y seccomp versionado; revisar las restricciones del nuevo anfitrión |
| Recursos disponibles | El escritorio tiene límites de 2 CPU, 4 GiB RAM y 256 MiB de memoria compartida; reservar margen para el anfitrión y las capas de construcción |
| Red y puerto | Descargas de Docker Hub y snapshot Ubuntu; puerto local 13389 libre |
| Cliente gráfico | Remmina con GFX probado; GPU y sesión gráfica del anfitrión no compartidas |
| Windows, macOS, ARM, Docker Desktop, rootless o SELinux | Sin validar; no se garantiza compatibilidad |

Comprobaciones previas desde la raíz del clon:

```bash
uname -m
uname -r
docker version
docker compose version
docker info --format 'architecture={{.Architecture}} cgroups={{.CgroupVersion}} driver={{.CgroupDriver}}'
test -c /dev/fuse && ls -l /dev/fuse
docker compose -f tools/docker-lab/gnome26/compose.yaml config --quiet
```

Systemd, GDM, D-Bus, GNOME Shell y GNOME Remote Desktop pertenecen a la imagen.
No se conectan al D-Bus ni a la sesión gráfica del anfitrión. Docker comparte
su kernel Linux: no reproduce el kernel ni el arranque de una ISO de Ubuntu.
Si faltan requisitos, hay que revisar el anfitrión; no se cambia a QEMU/KVM.

Con las recetas disponibles en el nuevo PC, construir y arrancar:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml build desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop cat /var/lib/termia-lab/password
```

| Dato de conexión | Valor |
| --- | --- |
| Protocolo | RDP |
| IP desde el propio anfitrión Docker | `127.0.0.1` |
| Puerto | `13389` |
| Login | `lab` |
| Password | Generado; consultar el comando anterior en cada instalación |
| Dominio | Vacío |
| Resolución y gráficos | 1440 × 900, GFX (`colordepth=63` en Remmina) |

`127.0.0.1` siempre corresponde al PC donde se abre el cliente. El puerto está
publicado solo en loopback: escribir la IP LAN del servidor desde otro equipo
no proporciona acceso con este Compose. El certificado es propio de cada
perfil; verificar su huella al conectar, especialmente tras destruir volúmenes.

Reconstruir desde cero conserva la configuración declarativa, pero genera otra
contraseña, otra clave TLS y un perfil vacío. Para conservar los datos de una
sesión hay que respaldar y restaurar **ambos** volúmenes (`profile` y
`credentials`) con el contenedor detenido y permisos/propietarios preservados.
Contienen datos y secretos: no se guardan en Git. La migración de esos volúmenes
a otro anfitrión todavía no está validada; no es necesaria para reconstruir
el sistema. No usar `down --volumes` si se quieren conservar esos datos.

## Mapa de configuración y operación

| Archivo | Responsabilidad |
| --- | --- |
| `Dockerfile`, `ubuntu.sources`, `.dockerignore` | Base, paquetes fijados, etapas y contexto permitido |
| `compose.yaml` | Recursos, aislamiento, FUSE, puerto y volúmenes |
| `init.sh`, `termia-lab.target` | Cgroups privados y arranque de systemd |
| `termia-lab-rdp.service`, `configure-rdp.py` | Usuario sintético, credenciales y configuración TLS/RDP |
| `termia-lab-session.service`, `after-rdp.conf` | Sesión Wayland creada por GDM y orden de arranque |
| `termia-lab-user-rdp.service` | Configuración del servidor RDP dentro de la sesión |
| `rendering.conf` | Renderizado por software |
| `seccomp-desktop.json`, `LICENSE.seccomp` | Perfil seccomp, permiso `pivot_root` y licencia de origen |
| `laboratory.remmina` | Perfil humano sin contraseña guardada |
| `rdp-probe.sh` | Cliente opcional aislado para validar RDP |

Para consultar el estado sin cambiarlo:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml ps
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop systemctl --failed --no-pager
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop journalctl -b --no-pager _COMM=gnome-shell -n 60
```

Si el bloqueo por inactividad deja la imagen negra, la recuperación probada
interrumpe la sesión pero conserva los volúmenes y las credenciales:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml restart desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
```

No equivale a resolver el bloqueo. Los apartados siguientes distinguen lo
validado, los fallos observados y los requisitos pendientes antes del commit
final y de considerar aceptado el laboratorio.

## Arrancar y conectar

Desde la raíz del repositorio:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml build desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml up -d --wait --wait-timeout 120 desktop
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop cat /var/lib/termia-lab/password
install -Dm600 tools/docker-lab/gnome26/laboratory.remmina tools/docker-lab/.runtime/gnome26.remmina
remmina -c tools/docker-lab/.runtime/gnome26.remmina
```

Conexión RDP a `127.0.0.1:13389`, usuario `lab`, resolución 1440 × 900.
Introduce la contraseña sintética que muestra el comando explícito anterior;
no la publiques ni la guardes en archivos versionados. La plantilla Remmina
desactiva portapapeles y almacenamiento de contraseñas. Antes de aceptar el
certificado autofirmado, compara su huella:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop \
  openssl x509 -in /home/lab/.local/share/gnome-remote-desktop/tls.crt \
  -noout -sha256 -fingerprint
```

El perfil fija `colordepth=63` para habilitar GFX, que GNOME exige. El modo
simple de 32 bits fue rechazado. Tras corregirlo, un cliente Remmina aislado
autenticó con la contraseña generada y mostró GNOME. La validación inicial
con FreeRDP no detectó el error del perfil Remmina. Cierra la pestaña antigua
antes de abrir el perfil corregido. La negociación del portapapeles abortaba
el servidor por falta de `/dev/fuse`; Compose ya declara ese dispositivo y
un cliente Remmina con portapapeles habilitado no provoca ese cierre.

Se mantiene el bloqueo normal por inactividad. Durante el diagnóstico, una
sesión bloqueada devolvió una imagen RDP negra. Reiniciar el contenedor,
conservando los volúmenes, recuperó el escritorio; reiniciar solo los servicios
de sesión no lo recuperó de forma fiable por una carrera durante el cierre.
La recuperación tras el bloqueo y la estabilidad global siguen sin validar.
No se desactiva el bloqueo ni se cambia la autenticación sin revisar la decisión.

El asistente de bienvenida de Ubuntu permanece habilitado y puede abrir una
petición nativa de autenticación para sus opciones de privacidad. No se han
aceptado opciones automáticamente. Para comprobar la entrada se detuvo su
servicio de primer inicio solo en aquella sesión, sin deshabilitarlo ni
cambiar las preferencias de privacidad.

## Configuración y limitaciones actuales

Systemd es PID 1. Compose usa cgroups privados, `SYS_ADMIN` y
`apparmor=unconfined`; mantiene seccomp y no usa `privileged`.
El perfil versionado `seccomp-desktop.json` procede de Moby `seccomp/v0.1.0`
(commit `a33e0005c5fd43eba98562c826376cac2517e437`, Apache-2.0;
consulta `LICENSE.seccomp`). Solo añade permiso para `pivot_root`, necesario
para el aislamiento de los cargadores Glycin mediante bubblewrap. Sin ese
permiso no cargan los iconos ni el fondo. Se mantiene el aislamiento de Glycin.
Permite otra operación de montaje dentro del modelo de capacidades existente;
hay que revisar el perfil al actualizar Docker, pues queda fijado en Git.
La validación visual por RDP confirmó el fondo, los iconos del dock y el icono
de la carpeta personal después del cambio.
El script de
entrada remonta con escritura los cgroups del contenedor. No hay montajes de
carpetas del anfitrión, sockets de su escritorio o Docker, GPU ni `/dev/kvm`.
El anfitrión debe ofrecer FUSE en el kernel y `/dev/fuse`, que se comparte con
lectura y escritura para el portapapeles de GNOME. Es una configuración experimental con permisos amplios, no
una configuración mínima ni un despliegue endurecido.

GDM crea la sesión individual de `lab` mediante su herramienta estándar
`gdm-new-session`, ejecutada por un servicio root según la política existente.
La sesión gráfica y GNOME Remote Desktop headless funcionan como `lab`.
El helper root permanece activo para gestionar el cierre de sesión. Se pide
autenticación RDP antes de acceder; no hay una segunda pantalla de acceso GDM.
PAM y polkit no se modifican, y las acciones administrativas siguen pidiendo
la contraseña del usuario sintético. La pantalla de acceso con el usuario
dinámico de GDM falló en la prueba inicial y no se presenta como operativa.

Renderizado: `LIBGL_ALWAYS_SOFTWARE=1`, sin GPU compartida. Límites: 2 CPU,
4 GiB de RAM, 4.096 procesos/hilos y 256 MiB de memoria compartida. Con el
límite anterior de 1.024, la porción del usuario solo permitía 337 tareas y
GNOME agotaba ese margen al arrancar. Se ha probado Linux amd64 con cgroups v2,
Docker Engine 28.5.1 y Compose 2.40.0. El anfitrión debe permitir los permisos
y el remontaje ensayados. No se instalan servicios ni módulos de kernel en él.
Docker rootless, Docker Desktop, anfitriones SELinux y otras arquitecturas
siguen sin validar.

Los volúmenes guardan únicamente el perfil `lab` —incluida su clave TLS— y
la contraseña generada. `/run`, `/run/lock` y `/tmp` son temporales. El sistema
y la configuración de servicios están en la imagen. Reiniciar conserva las
credenciales; eliminar los volúmenes las regenera.

Hay fallos observados en Netplan/udev, colord, TPM y RealtimeKit, un aviso BPF
en logind y un error en una extensión de búsqueda web de Ubuntu. No se han
ocultado. Declarar `/dev/fuse` resolvió el cierre observado al negociar el
portapapeles. La transferencia sostenida del portapapeles, archivos compartidos,
portales de documentos, audio y aceptación
de autenticación administrativa siguen sin validar. No se añadirán dispositivos
ni se ampliarán permisos sin revisar el impacto.

## Comprobación y destrucción

El cliente opcional ejecuta FreeRDP sobre su propio Xvfb. Esa pantalla de
cliente no cambia el backend Wayland del servidor ni utiliza tu escritorio:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation build rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation up -d rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml exec desktop loginctl list-sessions
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation logs --tail 30 rdp-probe
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation stop rdp-probe
```

El cliente lee la contraseña sintética mediante un volumen de solo lectura,
retira todas las capacidades, usa no-new-privileges, no publica puertos y
desactiva el portapapeles. Solo en esta prueba aislada acepta el certificado
autofirmado con `/cert:ignore`; la plantilla humana de Remmina pide confirmación.

Se observó GNOME Shell como servidor Wayland, con renderizador sin GPU;
logind confirmó una sesión remota Wayland activa y una comprobación GTK
devolvió `GdkWaylandDisplay`. Se inspeccionó la imagen recibida por RDP y se
escribió `TERMIA_RDP_INPUT_OK_430` en el editor estándar mediante teclado y
ratón RDP. Ctrl+S guardó un archivo con ese contenido exacto. Desconectar y
reconectar el cliente conservó sesión y archivo. Esto no valida todavía Termia
ni todos los servicios del escritorio.

El segundo ciclo retiró contenedores, red y todos los volúmenes de este
proyecto, reconstruyó usando la caché de Docker y repitió correctamente las
pruebas Wayland/GTK y de entrada/archivo por RDP. Se generaron credenciales
nuevas y no existía el marcador del perfil anterior. Esto comprueba la
reconstrucción sin datos privados previos; no se ha repetido una descarga
completa de paquetes sin caché. El healthcheck solo comprueba el socket de
sesión y el puerto RDP, no todos los servicios Ubuntu.

Para detener el proyecto o destruir expresamente sus datos sintéticos:

```bash
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation stop
docker compose -f tools/docker-lab/gnome26/compose.yaml --profile validation down --volumes
```

Repite construcción y arranque tras `down --volumes` para reconstruirlo.
Las imágenes y la caché permanecen; `down --volumes --rmi all` retira además
las imágenes de los servicios de este proyecto. Los laboratorios privados
anteriores no se seleccionan. Antes de cerrar #430 faltan Termia, los límites
de ejecución pendientes y la aceptación del despliegue final.

## Validación observada de la imagen base — 2026-10-28

Construcción Linux amd64 correcta con Docker Engine 28.5.1. Tamaño:
3.228.534.874 bytes (3,007 GiB). Los 1.510 registros de paquetes tienen estado
instalado; `dpkg --audit` no mostró problemas y `apt-get --simulate check`
terminó correctamente. El inventario coincide con una consulta nueva; SHA-256:
`afb1de6f3e7d5c45d85fa70f1b1e5a3315ffc2011bad0fa6095bdd2d9818d51d`.

Versiones instaladas: `ubuntu-desktop` 1.570.4, GNOME Shell 50.1-0ubuntu1.4,
GNOME Remote Desktop 50.2-0ubuntu0.1, Mutter 50.1-0ubuntu2.5, systemd
259.9-0ubuntu0.1 y PipeWire 1.6.2-1ubuntu1.2. El contenedor temporal de
inspección usó un sistema de archivos de solo lectura, sin red, montajes ni
capacidades adicionales, y se eliminó automáticamente. No se creó ningún
volumen persistente ni escritorio activo. No había aplicaciones Snap.
Pasaron las 18 pruebas existentes de infraestructura del laboratorio;
no validan la ejecución gráfica de esta imagen nueva.

## Pruebas observadas de systemd — 2026-10-28

Las pruebas temporales no modificaron la imagen ni establecen todavía un
despliegue soportado. Todas usaron cgroups privados, sin red ni montajes del
anfitrión, manteniendo seccomp. No se utilizó `--privileged`.

| Configuración | Resultado |
| --- | --- |
| Permisos y AppArmor predeterminados | systemd no puede crear `/init.scope`: cgroups en solo lectura |
| Añadir `SYS_ADMIN`, mantener AppArmor | Se rechazan montaje y remontaje de cgroups |
| AppArmor sin confinamiento, sin añadir `SYS_ADMIN` | Se rechaza el remontaje |
| Añadir `SYS_ADMIN`, AppArmor sin confinamiento | Funciona el remontaje con escritura y crear/eliminar un cgroup hijo |

Con la última configuración, systemd arrancó como PID 1 con `basic.target`;
D-Bus y logind quedaron activos, y una unidad temporal con `/usr/bin/true`
terminó correctamente. El sistema quedó **degradado**: `netplan-configure.service`
falló porque `udevadm` no pudo contactar con udev. logind registró además un
fallo al conectar un filtro BPF de salida, aunque siguió activo. No se han
ocultado ni corregido estos problemas.

`SYS_ADMIN` es un permiso amplio y quitar el confinamiento AppArmor reduce el
aislamiento. Se ha demostrado un mecanismo que funciona, no los permisos
mínimos ni la configuración definitiva. No se montó el árbol de cgroups del
anfitrión: se remontó el existente dentro de los espacios privados del contenedor.
Todos los contenedores de prueba se detuvieron/eliminaron. No se inició GNOME,
RDP ni Termia. Antes de desplegar hay que revisar una política de seguridad
más acotada, los ajustes necesarios de servicios y el arranque del escritorio.

## Entradas de construcción

- Imagen oficial Docker Ubuntu 26.04 fijada al digest
  `sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78`.
- Instantánea Ubuntu `20261027T000000Z`: `resolute`, `resolute-updates` y
  `resolute-security`, con `main`, `universe`, `restricted` y `multiverse`.
  No se añaden backports ni repositorios de terceros.
- Paquetes explícitos: `ubuntu-desktop`, `gnome-remote-desktop`, `systemd-sysv`,
  `dbus` y `ca-certificates`, con dependencias y recomendaciones. Se instala el
  metapaquete de escritorio completo y las aplicaciones estándar, sin sustituirlo
  por un escritorio ligero ni aplicar exclusiones personalizadas de paquetes.
- La base carece de certificados de confianza HTTPS. Una etapa separada descarga
  `ca-certificates_20260223_all.deb` de la instantánea, verifica SHA-256
  `f7025ab9b24cd73215510931037b02d6960d89584d0d00afba81851abdbe6ef1`
  y extrae los certificados públicos sin ejecutar scripts del paquete. APT los
  usa temporalmente para verificar HTTPS al instalar los paquetes normales,
  incluida la versión de certificados que ofrece la instantánea.
- Se mantienen las firmas de Ubuntu y la comprobación de hashes de APT.
  `Check-Valid-Until: no` permite reconstruir desde el archivo histórico;
  no desactiva firmas ni la verificación TLS.
- `.dockerignore` permite el Dockerfile, fuentes APT, scripts de arranque y
  RDP, unidades de servicios y configuración de renderizado de la imagen.
  El perfil seccomp de Compose y la plantilla del cliente quedan fuera del
  contexto. Tampoco entran código de Termia, archivos privados ni configuración
  del anfitrión.

Se fijan las recetas y los paquetes, sin prometer capas idénticas byte a byte:
los scripts de instalación pueden generar fechas y estado de máquina.
No se instalan las aplicaciones Snap: tener un DEB transicional como Firefox
no demuestra que su aplicación Snap esté instalada. La tienda Snap queda
fuera de la instantánea APT.

## Requisitos y comandos

Ejecuta desde la raíz del repositorio con Docker Engine local sobre Linux y
BuildKit. Necesitas acceso a Docker Hub y `snapshot.ubuntu.com`, y espacio para
el escritorio completo y las capas de construcción. El destino de construcción
es `linux/amd64`; otras arquitecturas, Docker rootless y Docker Desktop siguen
sin validar. No se instalan paquetes APT en el anfitrión ni se usa su escritorio.

```bash
docker build --progress=plain --platform linux/amd64 --target base \
  --tag termia-lab-430-ubuntu26-base:local tools/docker-lab/gnome26
```

Para inspeccionar los paquetes sin iniciar servicios, red, montajes del
anfitrión ni capacidades adicionales:

```bash
docker run --rm --network none --read-only --cap-drop ALL \
  termia-lab-430-ubuntu26-base:local \
  dpkg-query -W ubuntu-desktop gnome-shell gnome-session-bin ubuntu-session \
  gnome-remote-desktop systemd systemd-sysv dbus pipewire wireplumber

docker run --rm --network none --read-only --cap-drop ALL \
  termia-lab-430-ubuntu26-base:local \
  cat /usr/local/share/termia-lab/packages.tsv

docker image inspect termia-lab-430-ubuntu26-base:local
```

El inventario ordenado de paquetes, versiones, arquitecturas y estados está
en `/usr/local/share/termia-lab/packages.tsv`; la fecha del archivo, en
`/usr/local/share/termia-lab/apt-snapshot`. Se retiran índices y paquetes
descargados tras la instalación. `DEBIAN_FRONTEND=noninteractive` se aplica
solo al paso de construcción.

El destino base tiene `/bin/bash` como comando. No declara puertos, volúmenes,
usuarios de laboratorio personalizados ni arranque automático de GNOME/systemd.
Construir e inspeccionar no inicia ni sustituye los laboratorios anteriores.
El destino `desktop` y su Compose separado ejecutan el prototipo descrito arriba.

## Límites de la imagen base y trabajo de despliegue pendiente

Docker comparte el kernel Linux del anfitrión; no arranca un kernel Ubuntu.
No se usa QEMU/KVM, ningún disco preinstalado ni `/dev/kvm`. Construir esta base
no requiere GPU, cgroups del anfitrión, su bus de sesión, su socket Wayland,
un socket Docker dentro del contenedor ni ejecución privilegiada.

Los permisos de systemd/cgroups, el renderizado por software y los límites del
prototipo están documentados arriba. Instalar paquetes para hardware o servicios
no prueba que funcionen todos en un contenedor. Se conserva
la política de Ubuntu que impide iniciar servicios durante la instalación:
no equivale a tener un escritorio arrancado ni autenticación gráfica validada.

GNOME/Wayland, imagen/entrada RDP y reconstrucción con volúmenes nuevos han
pasado las pruebas del prototipo. Faltan Termia, su reconstrucción posterior y
la configuración final aceptada de permisos y servicios. No se recurrirá a una
VM, otro compositor ni al escritorio del anfitrión como alternativa.

## Actualización y retirada

Para actualizar, revisa conjuntamente digest, fecha de instantánea, URL y hash
del paquete inicial de certificados. Reconstruye, compara inventarios y repite
las comprobaciones afectadas. Una instantánea fija no recibe actualizaciones
de seguridad automáticamente. La reconstrucción depende de la disponibilidad
de los proveedores; Ubuntu expresa una intención de conservar instantáneas al
menos dos años, no una garantía de conservación ilimitada.

Cuando ya no necesites la imagen, elimina solo su etiqueta:

```bash
docker image rm termia-lab-430-ubuntu26-base:local
```

El destino base no crea volúmenes persistentes. No uses limpiezas generales de Docker
ni elimines discos o archivos de los laboratorios privados para reconstruirla.

Referencias: [imagen oficial Ubuntu](https://hub.docker.com/_/ubuntu),
[archivo de instantáneas Ubuntu](https://snapshot.ubuntu.com/) e
[issue #430](https://github.com/buuuki/termia/issues/430).
