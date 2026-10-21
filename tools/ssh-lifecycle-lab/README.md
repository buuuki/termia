# Laboratorio local de cierre SSH, SFTP y SCP

Este laboratorio comprueba Termia contra un servidor OpenSSH real en Docker. Esta copia publica únicamente guiones y documentación revisados; los artefactos generados quedan excluidos de Git. No requiere una VM adicional: Docker proporciona dos contenedores y una red de pruebas interna en el sistema existente.

Consulta [cómo se montó el laboratorio](MONTAJE.md) para ver requisitos, instalación, configuración, decisiones de aislamiento, comandos de reproducción y diagnóstico. Los [resultados de las pruebas](RESULTS.md) se documentan por separado.

Seguimiento en GitHub: [investigación y registro de validación #373](https://github.com/buuuki/termia/issues/373) y [corrección de retenciones de memoria #374](https://github.com/buuuki/termia/issues/374). Las issues contienen un resumen público de evidencias sintéticas; esta rama conserva los guiones revisados; las claves y los logs originales no se publican.

## Recuperar el trabajo desde otro ordenador

Esta rama es una copia de continuación del laboratorio de la [issue #377](https://github.com/buuuki/termia/issues/377), preparada para conservar el trabajo. No es una publicación de Termia ni una certificación de que todas las sondas funcionen en cualquier equipo.

```bash
git clone --branch maintenance/377-lifecycle-lab https://github.com/buuuki/termia.git
cd termia
```

El código de la corrección de memoria está en otra rama, `fix/374-memory-retention`, y en el [PR #376](https://github.com/buuuki/termia/pull/376). Esta copia parte de `release/0.6.0-beta.4-dev`; no incorpora ni modifica ese PR. Los informes conservan sus commits de referencia.

Las claves se generan al ejecutar `run.sh`; no se publican claves ni registros originales. Los contextos, observaciones y cachés también quedan excluidos. Antes de ejecutar las pruebas, revisa los requisitos y efectos sobre Docker en [MONTAJE.md](MONTAJE.md).

El cierre al arrastrar pestañas con flechas visibles sigue pendiente. Las pruebas temporales de Wayland no tienen todavía un guion conservado aquí; sus resultados y las comprobaciones pendientes están en [el informe consolidado](https://github.com/buuuki/termia/issues/373#issuecomment-6304805942). No repitas la suite completa ni las mediciones largas para retomar esa investigación.

Validación de esta copia: sintaxis Python y shell, enlaces relativos y exclusión de artefactos comprobados. La imagen cliente se construyó desde esta ubicación; una ejecución corta sin red confirmó el arranque con `--fresh`, la apertura de una segunda pestaña por teclado y el cierre gestionado sin hijos supervivientes. No se repitieron las matrices SSH/SFTP/SCP ni las mediciones de memoria con esta copia; los resultados históricos siguen referidos a sus commits originales. Esta rama es un punto de continuación, no un segundo PR listo para integrar.

## Ejecutar de nuevo

Desde la raíz del repositorio:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh'
```

Para repetir solo SCP:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh DockerLifecycleTests.test_scp_active_transfer_cleanup'
```

El script construye las imágenes, arranca el servidor dedicado, inicia el monitor y ejecuta el cliente sin privilegios. Al terminar detiene el servidor y el monitor. Conserva imágenes, red, contenedor servidor y archivos de referencia para volver a usar el laboratorio. No instala paquetes en el host.

## Qué comprueba

| Grupo | Escenarios |
| --- | --- |
| SSH | Contraseña y clave; SFTP/estadísticas activados y desactivados; desconectar panel, desconectar sesión, cerrar pestaña, cerrar ventana separada y cerrar aplicación: 20 combinaciones |
| SFTP | Contraseña y clave; cancelar y reconectar, desconectar, cerrar explorador y cerrar aplicación durante una subida real de 32 MiB: 8 combinaciones |
| SCP | Contraseña y clave; cancelar y cerrar aplicación durante una transferencia real limitada en velocidad: 4 combinaciones |

Las pruebas SSH crean dos pestañas y un panel dividido. Con herramientas opcionales activadas también abren un explorador SFTP asociado a la primera pestaña. Una pestaña distinta debe continuar conectada cuando se cierra la sesión objetivo. Se comprueba el resultado de limpieza de la aplicación y de las transferencias.

Se capturan PID y tiempo de inicio de los procesos locales. Tras el cierre debe desaparecer la misma identidad de `/proc`, también si estaba en estado zombi. El monitor inspecciona por separado los procesos del usuario de laboratorio, los zombis del contenedor y las conexiones TCP establecidas al puerto 22. Cada escenario termina con cero procesos de ese usuario, cero zombis y cero conexiones establecidas. Los sockets en TIME_WAIT no son conexiones abiertas y no se cuentan como fugas.

Los trabajos remotos son sintéticos: un padre Python con un hijo `sleep`. El padre recoge su hijo al recibir las señales normales de cierre. Esto comprueba sesiones y comandos que cooperan con el cierre SSH; no garantiza terminar servicios remotos deliberadamente desacoplados, trabajos con `nohup` o procesos que abandonan la sesión. Las pruebas resistentes a SIGTERM/SIGHUP de los procesos locales VTE pertenecen a la suite existente y a las sondas locales ejecutadas previamente.

## Aislamiento y autenticación

- Servidor: imagen Ubuntu 24.04 con OpenSSH; usuario `lab`, contraseña puramente sintética y clave Ed25519 generada para este laboratorio.
- Cliente: usuario UID 1001, sin capacidades Linux, con `no-new-privileges`, raíz de solo lectura y `/tmp` temporal. El runner del proyecto crea su HOME, display Xvfb y D-Bus privados.
- Red interna Docker. La primera ejecución de preparación publicó además el servidor exclusivamente en `127.0.0.1:32768`; las pruebas usan el nombre interno y puerto 22, y el servidor se detiene al terminar.
- Solo se monta la carpeta de observaciones sintéticas, en modo lectura. No se montan el escritorio, configuraciones personales, agente SSH ni socket Docker.
- El contexto del cliente se forma con archivos versionados de `src`, `tests` y `scripts`, más los guiones y claves sintéticas. El contexto del servidor excluye todos los archivos salvo Dockerfile, clave pública y trabajo remoto.
- Para aislar OpenSSH de la configuración personal se añaden `-F /dev/null`, un known_hosts privado, comprobación estricta de claves y selección explícita de identidad. Las funciones de autenticación, sesiones, cierre y transferencia de Termia conservan su implementación real.

## Archivos

`probe.py` contiene los casos; `run_probe.py` utiliza el runner privado del proyecto; `observe.py` se ejecuta en el servidor y `monitor.py` publica `observations/status.json`. Los Dockerfile definen ambas imágenes. `RESULTS.md` registra el resultado de la ejecución validada.

Las claves solo sirven para este entorno sintético. No deben reutilizarse ni incorporarse a Git.

## Pruebas de memoria

Para tres arranques independientes con cinco ciclos de conexiones y transferencias por instancia:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --memory'
```

Para observar veinte ciclos dentro de una instancia sin el coste de instrumentación de Python:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --memory --runs 1 --cycles 20 --no-tracemalloc'
```

Para cerrar mediante un clic real en la cruceta con tres sesiones SSH y una subida SFTP activas, sin desconectar previamente:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --memory --runs 3 --close-live --no-tracemalloc'
```

[memory_probe.py](memory_probe.py) mide RSS, PSS y memoria privada de Termia, descriptores, hilos y memoria del cgroup. En el modo instrumentado también mide asignaciones Python. Cada ciclo abre tres terminales SSH, sube y descarga 16 MiB por SFTP, verifica el hash y cierra sesiones y transferencias. Un supervisor comprueba la desaparición del proceso completo al cerrar cada instancia. Consulta [MEMORIA.md](MEMORIA.md) para los resultados y límites de interpretación.

La [investigación del crecimiento de memoria](INVESTIGACION_MEMORIA.md) documenta las retenciones identificadas y los experimentos temporales que permiten liberar los objetos, sin cambiar el código de Termia. Se repite mediante el modo `--investigate` de `run.sh`.
