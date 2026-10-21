> Documento histórico del laboratorio. Los resultados corresponden a los commits indicados, no a una ejecución nueva de esta copia. Los registros originales permanecen locales. El estado actualizado y los límites están en [la investigación #373](https://github.com/buuuki/termia/issues/373).

# Memoria: cierre correcto y retenciones identificadas

Se midió el código `2dd0e1d` de Termia en el laboratorio Docker con Ubuntu 24.04. Las pruebas previas de procesos no incluían estas mediciones: esta sonda se añadió posteriormente, sin modificar el código versionado de la aplicación.

**El cierre completo libera la memoria del proceso en los escenarios probados, incluida la cruceta con conexiones y transferencia activas. Durante la reutilización de una misma instancia sí se observó crecimiento sostenido de memoria que requiere investigación.** No se considera validada la ausencia de retención durante sesiones largas.

La investigación posterior confirmó retención de menús sustituidos y widgets de pestañas cerradas mediante pruebas comparativas de vida de objetos. Consulta [INVESTIGACION_MEMORIA.md](INVESTIGACION_MEMORIA.md) para el diagnóstico, las evidencias y la corrección propuesta. Las mediciones siguientes se conservan como resultado del código original.

## Cierre con la cruceta sin desconexión previa

Se hicieron tres arranques independientes. En cada uno:

1. Se creó una ventana real de Termia, dos pestañas SSH y un panel SSH dividido: tres sesiones conectadas.
2. Se abrió el explorador SFTP asociado y se inició una subida sintética de 16 MiB, ralentizada para mantenerla en curso.
3. Se comprobaron cuatro conexiones TCP establecidas y el servicio de transferencia ocupado.
4. Se pulsó físicamente con `xdotool` el centro del botón GTK de la cabecera cuya clase CSS era `close`. No se desconectó ninguna sesión ni se canceló la transferencia antes del clic.
5. Se exigió el resultado de aplicación `cleanup=stopped`, la parada del servicio SFTP y su transporte, y la desaparición de los procesos VTE/SSH capturados.
6. El monitor independiente exigió cero conexiones establecidas y cero procesos del usuario de pruebas, incluidos zombis, en el servidor.
7. El supervisor recogió el proceso de Termia con código 0 y comprobó que ya no existieran `/proc/<pid>` ni sus mapas de memoria.

El perfil sintético desactiva la confirmación de cierre; esta prueba no cubre pulsar el botón de confirmación de un diálogo. Se usa X11 privado con Xvfb, no el escritorio personal ni Wayland. Las tres ejecuciones alternaron contraseña, clave y contraseña.

| Instancia | RSS inicial | RSS con SSH y subida activa | Descriptores activos → tras limpieza | Hilos Python activos → tras limpieza | Proceso recogido |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 143,96 MiB | 155,56 MiB | 19 → 11 | 3 → 1 | Sí |
| 2 | 144,03 MiB | 154,98 MiB | 19 → 11 | 3 → 1 | Sí |
| 3 | 143,37 MiB | 155,12 MiB | 19 → 11 | 3 → 1 | Sí |

La muestra tomada inmediatamente después del callback de cierre todavía pertenece al proceso de la sonda, que conserva referencias para verificar los resultados. Su RSS ronda aún 155 MiB en ese momento. La prueba de liberación completa viene después: el proceso termina, el supervisor lo recoge y sus mapas desaparecen. No se confunde cerrar visualmente la ventana con terminar el proceso.

La memoria del cgroup completo pasó de 82,48 MiB antes del primer arranque a 83,47, 87,64 y 87,65 MiB después de cada salida. Ese cgroup incluye al supervisor, Xvfb, D-Bus, cachés y memoria del kernel; no es memoria anónima retenida por un proceso Termia que ya ha desaparecido.

Evidencia: `memory-cross-results.log` (evidencia local no publicada) y `memory-cross-results.json` (evidencia local no publicada). Cada ejecución contiene `MEMORY_CROSS_VERIFIED` con `manual_disconnects: 0`, `active_connections: 4` y `button_classes: ["close"]`.

## Reutilización de una instancia: crecimiento observado

Primero se ejecutaron tres instancias independientes de cinco ciclos cada una, con `tracemalloc`. Cada ciclo abrió tres sesiones SSH y SFTP, subió y descargó 16 MiB, verificó SHA-256, eliminó los ficheros de la transferencia y cerró las sesiones. Se tomaron muestras tras un reposo de 0,6 s y recolección de basura Python.

| Instancia | RSS tras ciclo 1 | RSS tras ciclo 5 | Memoria privada tras ciclo 1 → 5 | Python observado tras ciclo 1 → 5 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 162,31 MiB | 175,80 MiB | 76,20 → 89,69 MiB | 2,81 → 3,22 MiB |
| 2 | 162,55 MiB | 176,04 MiB | 76,30 → 89,79 MiB | 2,81 → 3,22 MiB |
| 3 | 162,00 MiB | 175,37 MiB | 76,04 → 89,40 MiB | 2,81 → 3,22 MiB |

Se repitió la comprobación con veinte ciclos en una misma instancia y **sin tracemalloc**, para evitar atribuir el crecimiento únicamente al instrumento de Python:

| Ciclo | RSS al terminar el ciclo |
| --- | ---: |
| 1 | 156,82 MiB |
| 5 | 169,27 MiB |
| 10 | 183,04 MiB |
| 15 | 196,94 MiB |
| 20 | 210,76 MiB |

Entre el primer y el vigésimo ciclo, RSS y memoria privada aumentaron aproximadamente 53,94 MiB. La memoria privada pasó de 74,61 a 128,55 MiB; PSS pasó de 112,83 a 166,77 MiB. El aumento medio entre esos dos extremos fue de unos 2,84 MiB por ciclo, sin estabilización observada en los veinte ciclos.

Los descriptores regresaron a 11 y los hilos Python a 1 después de cada ciclo. En esa ejecución los hilos nativos registrados pasaron de 39 a 38 entre el primer y el último ciclo; no se observó acumulación de hilos. Los procesos y conexiones remotos volvieron a cero. Tras cerrar la instancia, el proceso fue recogido y desapareció de `/proc`; la memoria del cgroup pasó de 82,01 a 84,61 MiB.

Esto es evidencia de crecimiento reproducible durante el uso. No identifica todavía su causa ni demuestra por sí solo una fuga irrecuperable: falta distinguir objetos retenidos, cachés, pools y comportamiento del asignador nativo de GTK/VTE y otras bibliotecas. La sonda también conserva muestras y usa mocks para servicios auxiliares; el resultado debe contrastarse con un perfil de asignaciones y una prueba mínima antes de atribuirlo a un módulo concreto de Termia.

Evidencia: `memory-results.log` (evidencia local no publicada), `memory-results.json` (evidencia local no publicada), `memory-long-results.log` (evidencia local no publicada) y `memory-long-results.json` (evidencia local no publicada).

## Qué mide cada contador

| Medida | Interpretación |
| --- | --- |
| RSS | Páginas residentes del proceso, incluidas bibliotecas compartidas |
| PSS | Memoria residente repartiendo proporcionalmente las páginas compartidas |
| Privada | `Private_Clean + Private_Dirty` de `smaps_rollup` |
| Python | Asignaciones seguidas por tracemalloc; no incluye toda la memoria nativa de GTK/VTE |
| Descriptores | Entradas de `/proc/self/fd`, útiles para buscar recursos abiertos que se acumulan |
| Hilos Python/nativos | `threading.enumerate()` y contador `Threads` de `/proc/self/status`; son medidas distintas |
| Cgroup | Consumo conjunto del cliente de laboratorio, incluyendo infraestructura y cachés |

El supervisor comprueba PID y tiempo de inicio cuando corresponde, y usa `wait` para recoger la instancia. Los resultados no se basan en el indicador global de memoria libre del sistema ni exigen que desaparezcan inmediatamente todas las cachés del kernel.

## Reproducir

Desde la raíz del repositorio, ejecutar solo una variante a la vez:

```bash
# Tres instancias, cinco ciclos cada una, con medición de asignaciones Python.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --memory'

# Veinte ciclos en una instancia, sin tracemalloc.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --memory --runs 1 --cycles 20 --no-tracemalloc'

# Tres cierres por clic en la cruceta, con conexiones y transferencia activas.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --memory --runs 3 --close-live --no-tracemalloc'
```

El guion deja detenido el servidor al terminar. Los archivos de resultados son locales y están excluidos de Git. [MONTAJE.md](MONTAJE.md) explica la infraestructura y sus límites.

## Próximo paso

Revisar y autorizar la corrección de las retenciones identificadas en [INVESTIGACION_MEMORIA.md](INVESTIGACION_MEMORIA.md), ahora registradas en la [issue #374](https://github.com/buuuki/termia/issues/374), relacionada con la [investigación #373](https://github.com/buuuki/termia/issues/373). No se ha corregido código. No debe darse por validada la estabilidad de memoria durante uso prolongado a partir del cierre correcto del proceso.
