> Documento histórico del laboratorio. Los resultados corresponden a los commits indicados, no a una ejecución nueva de esta copia. Los registros originales permanecen locales. El estado actualizado y los límites están en [la investigación #373](https://github.com/buuuki/termia/issues/373).

# Resultado: cierre de procesos y conexiones verificado en el laboratorio

Código de Termia: `2dd0e1d` en `release/0.6.0-beta.4-dev`. Fecha: 20 de octubre de 2026. No se modificó el código versionado ni se crearon issues, ramas, commits o PR. No se cambió la versión: es validación de la beta.4 en desarrollo.

## Comprobaciones completadas

| Comprobación | Resultado |
| --- | --- |
| Suite completa con el runner privado del proyecto | 645 pruebas, sin fallos ni omisiones; 96.816 s |
| Sintaxis Python del proyecto y tests | Correcta |
| Sintaxis del instalador shell | Correcta |
| Sincronización de traducciones | Correcta: 580 mensajes |
| Sonda local de aplicación/VTE | 8 combinaciones correctas: panel, pestaña, ventana separada y aplicación; opcionales activados/desactivados |
| Sonda local de transporte SFTP con socketpair real | 6 combinaciones correctas: conexión inactiva y operación en curso, tres ciclos cada una |
| SSH real contra OpenSSH en Docker | 20 combinaciones correctas |
| SFTP real con subida en curso contra Docker | 8 combinaciones correctas |
| SCP real con transferencia en curso contra Docker | 4 combinaciones correctas |

La suite completa incluye pruebas VTE reales con un hijo que ignora SIGTERM/SIGHUP y cambia de grupo de procesos, limpieza forzada tras salir el líder, supervivencia de un proceso ajeno, identidad de PID, paneles y cancelación SCP. También incluye pruebas unitarias de reutilización de PID, fallos y límites de tiempo de limpieza, y comportamiento SFTP habilitado/deshabilitado.

## Evidencia de Docker

- `ssh-sftp-results.log` (evidencia local no publicada): 28 líneas PASS, dos métodos unittest correctos, 37.321 s.
- `scp-results.log` (evidencia local no publicada): 4 líneas PASS, un método unittest correcto, 3.429 s.
- `final-server-state.json` (evidencia local no publicada): lista de procesos vacía y cero conexiones TCP establecidas. El mapa de trabajos conserva identificadores históricos; no indica que sus PID sigan vivos.

Las combinaciones se ejecutaron como subcasos de tres métodos unittest, de ahí que el contador de unittest sea 2 + 1 y no 32. Los clientes terminaron con código 0, usuario `tester`, raíz de solo lectura y modo privilegiado desactivado. Se verificó que los 142 archivos versionados seleccionados para el contexto de pruebas coincidieran byte por byte con el checkout.

En cada escenario SSH se comprobaron las identidades locales PID/tiempo de inicio y la desaparición de los procesos remotos sintéticos. El cierre de una sesión mantuvo utilizable la pestaña ajena. Las pruebas con explorador SFTP asociado verificaron su cierre al retirar el propietario. Los escenarios de cierre de aplicación terminaron con `cleanup=stopped`, sin resultado de limpieza no verificada.

Las subidas SFTP usaron un fichero sintético de 32 MiB con pausas de progreso para asegurar una operación en curso. Se verificaron cierre de trabajadores y transporte Paramiko, cancelación, reconexión con un servicio nuevo, cierre de explorador y cierre de aplicación. Las pruebas SCP usaron 32 MiB y límite de velocidad para cancelar una transferencia realmente activa; comprobaron que no se notificara éxito después de cancelarla.

## Alcance y límites

Los resultados verifican los escenarios descritos, no la ausencia universal de fugas. Los comandos remotos de prueba recogen a sus hijos al recibir las señales de cierre. Servicios remotos desacoplados, `nohup`, procesos que crean otra sesión y servidores de producción con políticas diferentes no quedan cubiertos. Los procesos locales resistentes a señales sí tienen cobertura específica en las pruebas anteriores.

No se usaron servidores, credenciales ni datos reales. No se inspeccionó ni se cerró la instancia personal de Termia. No se elevó el usuario de ejecución de Termia: Docker administra los contenedores y el cliente ejecuta el runner privado como UID 1001, sin capacidades y con `no-new-privileges`.

La suite mostró dos avisos de GLib relacionados con IDs de temporizadores de notificaciones ya retirados y avisos de APIs GTK/VTE obsoletas. Docker avisó de que el constructor legacy está obsoleto. Ninguno produjo fallos en estas comprobaciones; no se hicieron cambios ajenos a la validación para resolverlos.

## Estado final y siguiente comprobación

El guion reutilizable pasó la comprobación de sintaxis y su ciclo de preparación, arranque, ayuda y parada, sin repetir pruebas ya correctas. El servidor queda detenido; se conservan imágenes, red y contenedores detenidos como material local de diagnóstico. Consulta [README](README.md) para repetir la matriz.

La instalación y actualización Debian/Git desde beta.3 en Ubuntu 24.04 y 26.04 ya se probaron en el trabajo de #371, documentado en `docs/DOCKER_UPGRADE_VALIDATION.md`; no deben repetirse sin cambios que afecten su cobertura. La investigación conjunta está registrada en [#373](https://github.com/buuuki/termia/issues/373). El siguiente trabajo es corregir las retenciones de memoria de [#374](https://github.com/buuuki/termia/issues/374) y repetir las comprobaciones afectadas. Este informe no declara completada la preparación de la publicación.
