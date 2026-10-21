> Documento histórico del laboratorio. Los resultados corresponden a los commits indicados, no a una ejecución nueva de esta copia. Los registros originales permanecen locales. El estado actualizado y los límites están en [la investigación #373](https://github.com/buuuki/termia/issues/373).

# Cómo se montó el laboratorio de Termia

El laboratorio permite ejecutar Termia contra un servidor SSH/SFTP real y observar el cierre de procesos y conexiones en ambos extremos. Está guardado en `tools/ssh-lifecycle-lab/`, con artefactos generados excluidos de Git. Se preparó para comprobar el commit `2dd0e1d`, dentro del desarrollo de `0.6.0-beta.4`.

Se usó el sistema Ubuntu existente con Docker. No se creó ni se reconfiguró una VM adicional. Los paquetes de servidor y de cliente se instalan dentro de sus imágenes; el único componente nuevo requerido en el sistema anfitrión fue Docker y sus dependencias.

## Repetir las pruebas

Desde la raíz de Termia:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh'
```

El resultado esperado es una salida `PASS` por cada combinación y un resultado final `OK`. Hay 32 combinaciones agrupadas en tres métodos unittest; por eso unittest informa de tres tests al ejecutar la matriz completa.

Para ejecutar solo un grupo:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh DockerLifecycleTests.test_ssh_lifecycle'
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh DockerLifecycleTests.test_sftp_active_transfer_cleanup'
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh DockerLifecycleTests.test_scp_active_transfer_cleanup'
```

Para comprobar la preparación y parada sin ejecutar otra vez las pruebas:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --help'
```

Este último comando construye y arranca el entorno, muestra la ayuda de unittest y ejecuta la limpieza del guion. No valida el comportamiento de Termia.

## 1. Instalación y acceso a Docker

Al empezar no estaban disponibles el ejecutable Docker ni su socket. El usuario instaló Docker y activó el servicio mediante los comandos propuestos:

```bash
sudo apt update
sudo apt install docker.io
sudo systemctl enable --now docker
sudo docker info
```

La instalación comprobada posteriormente fue Docker `29.1.3`, con el servicio activo. El socket `/var/run/docker.sock` pertenecía a `root:docker` y el usuario de trabajo no tenía acceso inicialmente.

Se solicitó añadir el usuario al grupo:

```bash
sudo usermod -aG docker "$USER"
```

La pertenencia quedó registrada, pero el proceso de Codex conservaba los grupos anteriores. Se resolvió ejecutando los comandos con `sg docker`, que inicia el comando con ese grupo sin exigir reiniciar otra vez la sesión. No se abrió el socket a todos los usuarios ni se modificaron sus permisos para hacerlo globalmente accesible.

El acceso al grupo Docker permite administrar contenedores con efectos sobre el sistema anfitrión. En el laboratorio se usa para preparar la infraestructura; Termia se ejecuta como un usuario sin privilegios dentro del cliente.

Comprobación de acceso:

```bash
sg docker -c 'docker --host=unix:///var/run/docker.sock version'
```

Todos los comandos del laboratorio seleccionan explícitamente el socket local. Así no dependen de un contexto Docker guardado que pudiera apuntar a otro equipo.

## 2. Distribución de los componentes

```text
Sistema anfitrión
  │
  ├─ run.sh: prepara imágenes, red, servidor y cliente
  ├─ monitor.py: consulta el servidor con docker exec
  │    └─ observations/status.json: estado sintético, actualizado de forma atómica
  │
  └─ Red Docker interna: termia-lifecycle-internal
       ├─ Servidor: termia-ssh-lifecycle-lab
       │    ├─ OpenSSH en el puerto 22
       │    ├─ usuario lab y comandos sintéticos
       │    └─ observe.py: lectura de procesos y conexiones del contenedor
       └─ Cliente temporal
            ├─ usuario tester, UID 1001
            ├─ Termia + GTK/VTE + SSH/SCP + Paramiko
            ├─ HOME, Xvfb y D-Bus privados del runner
            └─ lectura de /observations/status.json
```

La red interna permite la comunicación entre los contenedores. La instalación de dependencias ocurre al construir las imágenes, antes de ejecutar los tests; no necesita acceso exterior desde esa red de pruebas.

## 3. Servidor OpenSSH

La imagen `termia-ssh-lifecycle-lab:local` se define en [Dockerfile](Dockerfile):

| Elemento | Configuración |
| --- | --- |
| Base | `ubuntu:24.04` |
| Paquetes | `openssh-server`, `python3`, `procps`, `iproute2`, `ca-certificates` y sus dependencias |
| Usuario remoto | `lab`, con shell `/bin/bash`; UID observado 1001 |
| Contraseña sintética | `termia-synthetic-only`, exclusiva del laboratorio |
| Clave pública | `synthetic.pub`, instalada en `/home/lab/.ssh/authorized_keys` |
| Permisos SSH | Directorio `.ssh` 700, `authorized_keys` 600, propietario `lab` |
| Autenticación | Contraseña y clave habilitadas; acceso de root deshabilitado |
| Opciones del servidor | `UsePAM no`, `PrintMotd no`, `LogLevel VERBOSE` |
| Inicio | Generación de claves de host que falten y `sshd -D -e` |
| Gestión de hijos | Contenedor iniciado con `--init` |

El servicio SFTP lo proporciona OpenSSH. El paquete `openssh-sftp-server` se instaló como dependencia del servidor. El comando `scp` del cliente utiliza el modo SFTP predeterminado de OpenSSH; no se forzó el protocolo SCP antiguo.

El par de claves del cliente se generó así, solo para este entorno:

```bash
ssh-keygen -q -t ed25519 -N '' -C termia-synthetic-lab \
  -f tools/ssh-lifecycle-lab/synthetic
```

`run.sh` solo lo genera si falta la clave privada. La clave privada entra únicamente en la imagen del cliente; la pública entra también en la imagen del servidor. [.dockerignore](.dockerignore) limita el contexto del servidor a su Dockerfile, la clave pública y el trabajo remoto. Ninguna de estas claves sirve como credencial personal.

El servidor lleva la etiqueta `termia.purpose=lifecycle-tests`. El guion comprueba esa etiqueta antes de reutilizar un contenedor existente con el nombre reservado.

## 4. Por qué se añadió un contenedor cliente

La primera preparación publicó SSH únicamente en `127.0.0.1:32768`. Una comprobación desde el anfitrión confirmó que OpenSSH respondía, pero la conexión desde el sandbox de Codex fue rechazada: su red de loopback no alcanzaba el puerto del anfitrión.

La prueba no se trasladó al escritorio del usuario ni se ejecutó Termia con privilegios. Se construyó un cliente dentro de Docker, conectado al servidor por su nombre interno `termia-ssh-lifecycle-lab`, puerto 22.

El contenedor servidor original conserva su publicación local cuando se reutiliza. Si se crea uno nuevo mediante `run.sh`, se crea directamente en la red interna, sin publicar ningún puerto al anfitrión. Las pruebas no dependen del puerto 32768.

La construcción inicial del contexto del cliente mediante entrada estándar falló al interpretar el Dockerfile. Se utilizó un directorio de contexto preparado explícitamente, que es el procedimiento conservado en el guion actual.

## 5. Imagen y aislamiento del cliente

La imagen `termia-lifecycle-client:local` está definida en [Dockerfile.client](Dockerfile.client). Usa Ubuntu 24.04 e instala:

- Python, PyGObject, YAML, Cryptography y Paramiko.
- GTK 4, VTE y GtkSourceView 5 mediante sus paquetes de introspección.
- OpenSSH cliente y `sshpass` para comprobar los dos métodos de autenticación.
- Xvfb, xauth y D-Bus para ejecutar la interfaz sin utilizar el escritorio.
- xdotool, fuentes DejaVu y certificados del sistema.

La imagen crea `tester` con UID 1001 y establece `USER tester`. El contenedor se inicia con:

```text
--init
--network termia-lifecycle-internal
--read-only
--tmpfs /tmp:rw,nosuid,size=512m
--cap-drop ALL
--security-opt no-new-privileges
```

El único montaje es la carpeta de observaciones sintéticas en `/observations`, en modo lectura. No se monta el repositorio completo, el socket Docker, el agente SSH, el directorio personal ni la sesión gráfica. El código de Termia ya está copiado dentro de la imagen.

[prepare_client_context.py](prepare_client_context.py) copia los archivos que `git ls-files` selecciona en `src`, `tests` y `scripts`, además de los guiones del laboratorio y sus claves sintéticas. En la ejecución validada se comprobaron 142 archivos versionados, idénticos byte por byte al checkout.

El contexto es una copia local, no un checkout autónomo. La preparación copia el contenido de trabajo de los archivos seleccionados, aunque estén modificados; no añade archivos sin seguimiento de Git. Tampoco elimina automáticamente archivos antiguos de `client-context/`. Si cambia la estructura del código, debe revisarse o regenerarse ese directorio antes de atribuir un resultado al código nuevo.

Las imágenes usan una etiqueta de Ubuntu y paquetes de los repositorios, sin fijar todas las versiones por digest. Los resultados registrados corresponden a la construcción ejecutada; una reconstrucción futura puede actualizar las dependencias.

## 6. Runner gráfico y confianza SSH

[run_probe.py](run_probe.py) carga `scripts/run_sandbox_tests.py` y mantiene su preparación del entorno. Sustituye únicamente el comando unittest por el guion del laboratorio, conservando el directorio de trabajo y el entorno aislado que crea el runner.

Ese runner prepara un HOME y directorios XDG temporales, una pantalla Xvfb por TCP, autenticación X11, D-Bus privado y renderizado por software. También elimina `SSH_AUTH_SOCK`. Todo ello se elimina cuando termina la ejecución del runner.

El cliente recibe:

```text
TERMIA_LAB_HOST=termia-ssh-lifecycle-lab
TERMIA_LAB_PORT=22
TERMIA_LAB_STATUS=/observations/status.json
```

Las pruebas obtienen las claves del servidor sintético con `ssh-keyscan` y escriben un `known_hosts` dentro del HOME temporal. En este laboratorio controlado se conoce y administra el servidor; este procedimiento no pretende sustituir la verificación de identidad de un servidor de producción.

Para impedir que OpenSSH lea configuraciones personales, el guion añade a los argumentos generados por Termia:

```text
-F /dev/null
-o UserKnownHostsFile=<HOME temporal>/.ssh/known_hosts
-o StrictHostKeyChecking=yes
-o IdentitiesOnly=yes
-o ConnectTimeout=5
```

La sustitución temporal de `build_ssh_command` conserva el comando de Termia y añade esas opciones de aislamiento. No simula la conexión ni cambia las funciones de cierre. SFTP usa el backend Paramiko real y las ventanas y servicios reales de Termia. SCP usa el constructor de comandos y el controlador reales, con opciones equivalentes para el entorno sintético.

## 7. Observación independiente del servidor

[observe.py](observe.py) lee `/proc` dentro del contenedor servidor. Recoge:

| Campo | Significado |
| --- | --- |
| `processes` | Procesos del UID 1001, comandos de trabajo remoto y cualquier proceso zombi detectado en el contenedor |
| `jobs` | PID del padre y del hijo registrados por cada trabajo sintético; es un historial y puede contener PID ya desaparecidos |
| `established` | Número de conexiones TCP en estado ESTABLISHED cuyo puerto local es 22, en IPv4 e IPv6 |
| `time` | Hora de la observación, para rechazar datos antiguos |

El UID 1001 es una suposición de este laboratorio basada en la imagen construida. Si cambia el usuario o la base, debe verificarse con `docker exec ... id lab` y ajustarse el observador si corresponde.

[monitor.py](monitor.py) ejecuta el observador mediante `docker exec`, espera 0,2 segundos entre iteraciones y sustituye el JSON de forma atómica. El cliente puede leer las observaciones pero no escribirlas. La prueba rechaza observaciones con más de cuatro segundos de antigüedad.

En el cliente se capturan los PID y sus tiempos de inicio para no confundir un PID reutilizado con el proceso original. Al terminar se exige que esas identidades hayan desaparecido de `/proc`, incluidos los zombis.

TIME_WAIT se distingue de ESTABLISHED: un socket que conserva temporalmente el estado del cierre TCP no se considera una conexión abierta del programa.

## 8. Cargas y escenarios probados

[remote_job.py](remote_job.py) crea un padre Python y un hijo `sleep 300`, y registra sus PID en `/tmp/termia-job-<identificador>/pids`. El padre termina y recoge el hijo ante SIGHUP, SIGTERM o SIGINT. Se ejecuta con `exec` desde el comando de inicio de la sesión SSH.

| Grupo | Preparación y acciones |
| --- | --- |
| SSH: 20 combinaciones | Dos pestañas y un panel SSH; contraseña/clave; opcionales activados/desactivados; desconectar panel, desconectar sesión, cerrar pestaña, cerrar ventana separada y cerrar aplicación |
| SFTP: 8 combinaciones | Subida real de un fichero sintético de 32 MiB; contraseña/clave; cancelar y reconectar, desconectar, cerrar explorador y cerrar aplicación |
| SCP: 4 combinaciones | Fichero sintético de 32 MiB con límite `-l 512`, en Kbit/s, para asegurar una transferencia activa; contraseña/clave; cancelar y cerrar aplicación |

Las subidas SFTP se ralentizan con pausas breves en el callback de progreso. Antes de cerrar se comprueba que haya empezado una operación real. Los casos SCP comprueban también que la cancelación no invoque el callback de éxito.

Con opcionales activados, las pruebas SSH abren además un explorador SFTP asociado a la primera pestaña. Al cerrar esa sesión se comprueba la limpieza del explorador. La pestaña ajena debe conservar su conexión hasta que se cierre explícitamente.

Los casos terminan verificando cero conexiones establecidas, cero procesos del usuario de laboratorio y cero zombis del servidor. Los cierres de aplicación deben registrar `cleanup=stopped`.

Esto cubre comandos remotos que cooperan con las señales de cierre. No implica terminar servicios remotos desacoplados, procesos lanzados con `nohup` o tareas que abandonan su sesión. Las pruebas locales anteriores cubrieron por separado hijos VTE resistentes a SIGTERM/SIGHUP. El detalle de resultados y límites está en [RESULTS.md](RESULTS.md).

## 9. Orden exacto del guion reutilizable

[run.sh](run.sh) realiza estas operaciones:

1. Se sitúa en la raíz del proyecto y comprueba Docker en su socket local.
2. Genera la clave sintética si falta y construye la imagen del servidor.
3. Prepara el contexto del cliente y construye su imagen.
4. Crea la red interna si no existe y crea o arranca el servidor etiquetado.
5. Asegura su conexión a la red, copia el observador e inicia el monitor.
6. Espera brevemente una observación reciente y ejecuta el cliente temporal.
7. Al salir del bloque con la limpieza registrada, señala la parada del monitor, espera a que termine y detiene el servidor.

El cliente habitual usa `--rm`, por lo que Docker lo elimina al terminar. Las dos ejecuciones de diagnóstico iniciales usaron nombres fijos y conservaron los contenedores detenidos para guardar sus logs. El servidor, imágenes, red y archivos locales se conservan para repetir la prueba.

La limpieza del guion se registra después de iniciar el monitor. Si falla un paso anterior o se interrumpe bruscamente el proceso, conviene consultar el estado con los comandos siguientes. No se ejecuta limpieza global de Docker.

## 10. Consultar el estado y detener el servidor

Estado de los contenedores iniciales y del servidor:

```bash
sg docker -c 'docker --host=unix:///var/run/docker.sock ps -a --filter name=termia-lifecycle --filter name=termia-ssh-lifecycle-lab'
```

Logs del servidor:

```bash
sg docker -c 'docker --host=unix:///var/run/docker.sock logs --tail 50 termia-ssh-lifecycle-lab'
```

Última observación, que puede ser histórica si el monitor está detenido:

```bash
python3 -m json.tool tools/ssh-lifecycle-lab/observations/status.json
```

Si quedó el laboratorio en ejecución, detener primero el monitor y después el servidor:

```bash
touch tools/ssh-lifecycle-lab/monitor.stop
sg docker -c 'docker --host=unix:///var/run/docker.sock stop termia-ssh-lifecycle-lab'
```

Estos comandos solo afectan a los recursos dedicados del laboratorio. No se utilizó `docker system prune` ni se tocaron contenedores ajenos.

## 11. Evidencias y mantenimiento

| Archivo | Uso |
| --- | --- |
| [README.md](README.md) | Entrada rápida y comandos de ejecución |
| [RESULTS.md](RESULTS.md) | Resultados, código probado y alcance |
| `ssh-sftp-results.log` (evidencia local no publicada) | Salida de las 28 combinaciones SSH/SFTP iniciales |
| `scp-results.log` (evidencia local no publicada) | Salida de las cuatro combinaciones SCP iniciales |
| `final-server-state.json` (evidencia local no publicada) | Observación final independiente de aquella ejecución |
| `observations/status.json` | Último estado observado; se actualiza al repetir el laboratorio |
| `synthetic`, `synthetic.pub` | Par de claves exclusivamente sintético |
| `client-context/` | Copia generada para construir el cliente |

El guion no sobrescribe los logs históricos de las ejecuciones iniciales. Para conservar la salida de una nueva ejecución sin perder su código de salida:

```bash
bash -o pipefail -c "sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh' 2>&1 | tee tools/ssh-lifecycle-lab/nueva-ejecucion.log"
```

No ejecutar dos copias del laboratorio a la vez: comparten servidor, nombres, estado del monitor y observaciones. El inicio de cada caso exige que el anterior no deje recursos activos.

Los avisos de APIs GTK/VTE obsoletas y del constructor Docker legacy quedaron registrados. No se instalaron Buildx ni Compose porque no eran necesarios para ejecutar estas pruebas.

Esta guía describe y permite repetir el laboratorio local. No añade cobertura permanente a la suite compartida ni declara completadas las pruebas de instalación y actualización necesarias para publicar beta.4.

## 12. Ampliación para medir memoria

Se añadió [memory_probe.py](memory_probe.py) y el selector `--memory` de `run.sh`. `prepare_client_context.py` incluye esa sonda en la imagen, y `run_probe.py` la selecciona mediante `TERMIA_LAB_MEMORY=1`. La matriz SSH/SFTP/SCP original conserva su modo predeterminado.

El proceso supervisor se mantiene vivo en el display privado y abre un subproceso independiente para cada instancia de Termia. La sonda crea una ventana real mediante `TermiaWindow`, ejecuta los flujos reales de conexión y transferencia y procesa los eventos de GLib. Al cerrar invoca el flujo de cierre de la ventana, exige `application.shutdown_finished` con `cleanup=stopped` y deja terminar el subproceso. No es una medición del lanzador de escritorio ni de una sesión Wayland.

Se leen `/proc/<pid>/smaps_rollup`, el número de descriptores abiertos y los contadores de hilos. También se registra `memory.current` del cgroup del contenedor, si está disponible. `tracemalloc` permite observar asignaciones Python; sus propios metadatos consumen memoria, por lo que se ofrece un modo sin instrumentación. No detecta por sí solo todas las asignaciones nativas de GTK/VTE.

En cada ciclo se crean dos pestañas SSH y un panel dividido, alternando contraseña y clave; se abre SFTP asociado, se sube y descarga un archivo sintético de 16 MiB y se verifica SHA-256. Se elimina el archivo remoto de esa prueba y la descarga local. Después se cierran las sesiones, se exige la parada de SFTP y se comprueba que no queden procesos ni conexiones remotos. Se deja un periodo de reposo y se solicita recolección de basura Python antes de la muestra de fin de ciclo.

Las fases registradas son `window-idle`, `connected`, `after-upload`, `after-download`, `cycle-clean` y `shutdown-callback-finished`. Esta última muestra todavía pertenece al proceso de la sonda; el supervisor verifica por separado su desaparición completa tras la salida. Los logs incluyen `MEMORY_SAMPLE`, `MEMORY_EXIT` y un JSON final `MEMORY_RESULT`.

Las opciones `--runs` y `--cycles` controlan las repeticiones. El modo inicial hace tres instancias de cinco ciclos. La comprobación extendida usa una instancia de veinte ciclos con `--no-tracemalloc`. Los resultados se guardan en [MEMORIA.md](MEMORIA.md), los logs y sus JSON derivados. La memoria del cgroup incluye cachés e infraestructura: no debe exigirse que su contador regrese exactamente al mismo byte tras cerrar Termia.

La variante `--close-live` abre tres sesiones SSH y un explorador SFTP, inicia una subida y exige cuatro conexiones establecidas. Localiza el botón GTK nativo de la cabecera con clase CSS `close`, calcula su centro respecto a la ventana y obtiene el identificador X11. `xdotool` eleva la ventana, mueve el puntero hasta la cruceta y envía un clic izquierdo real. No llama antes a desconectar, cerrar pestañas ni cancelar la transferencia. La confirmación de cierre está desactivada en el perfil sintético para automatizar esta comprobación; el diálogo de confirmación no queda cubierto.

La sonda registra `MEMORY_CROSS_VERIFIED`, con coordenadas, clase del botón, cuatro conexiones activas y cero desconexiones manuales. Exige limpieza correcta de aplicación, transportes, hilos, procesos locales y recursos remotos antes de ejecutar su limpieza defensiva final. Después el supervisor recoge el proceso y comprueba la desaparición de `/proc/<pid>` y de sus mapas de memoria. Este caso se repitió tres veces, alternando contraseña y clave, con Xvfb/X11 privado.

## 13. Diagnóstico de objetos retenidos

El modo `--investigate` selecciona `retention_probe.py` mediante `TERMIA_LAB_RETENTION=1`. Cada variante se ejecuta en un proceso distinto y puede reconstruir solo el menú de desbordamiento o abrir/cerrar terminales locales. Se comparan la RSS, asignaciones Python y contadores de objetos todavía vivos.

La sonda aplica sustituciones temporales dentro del proceso de diagnóstico para desactivar el menú, retirar el grupo de acciones anterior o desconectar handlers propios de Termia de los widgets ya cerrados. Los módulos de aplicación no se editan ni se modifica la instancia personal del usuario. Se espera siempre el fin de los procesos antes de retirar sus callbacks en el experimento.

Para distinguir la vida del wrapper Python de la del widget nativo, el contador VTE y el registro de handlers usan `GObject.weak_ref()`. El recorrido del árbol incluye páginas, etiquetas y los controladores GTK obtenidos mediante `observe_controllers()`. La sonda registra los IDs de las conexiones Python hechas por callbacks del módulo `termia`, y no destruye indiscriminadamente los handlers internos de GTK.

Los resultados y los límites de estas intervenciones están en [INVESTIGACION_MEMORIA.md](INVESTIGACION_MEMORIA.md). El contexto del cliente incorpora esta nueva sonda; el procedimiento de construcción, red y aislamiento no cambia.

## 14. Depuración nativa y arranque real

El cliente incluye GDB y Valgrind, instalados solo en la imagen Docker. Termia
sigue ejecutándose como `tester`, sin capacidades y con sistema de archivos de
solo lectura. No se sustituyen las bibliotecas del equipo ni se usa su escritorio.

```bash
# Código real bajo Valgrind, sin sustituir métodos de Termia.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --valgrind DockerLifecycleTests.test_ssh_lifecycle'

# Intervención causal explícita: omitir el foco de divisiones aún no mapeadas.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --diagnose-focus DockerLifecycleTests.test_ssh_lifecycle'

# Lanzador real con perfil temporal, nueva pestaña por teclado y SIGTERM.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --launch'
```

La última sonda ejecuta `scripts/run_test_instance.sh --fresh` dentro del Xvfb y
D-Bus privados. El contexto Docker incluye ahora `run_termia.py`. La prueba de
cruceta con conexiones vivas sigue siendo la variante independiente `--close-live`.

La opción `--trim-diagnostic`, después de `--memory`, ejecuta `malloc_trim(0)`
únicamente al terminar los ciclos medidos y toma otra muestra. Permite distinguir
memoria libre conservada por el asignador de objetos todavía vivos. No existe
esa llamada en Termia y no se usa para presentar la memoria previa como liberada.
La sonda también cuenta referencias débiles a sesiones, VTE y ventanas SFTP.

No se debe editar `run.sh` mientras una ejecución suya esté activa: Bash puede
continuar leyendo el archivo y una modificación puede invalidar el envoltorio.
Las pruebas y resultados de #374 se resumen en [CORRECCION_374.md](CORRECCION_374.md).
