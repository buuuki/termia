> Documento histórico del laboratorio. Los resultados corresponden a los commits indicados, no a una ejecución nueva de esta copia. Los registros originales permanecen locales. El estado actualizado y los límites están en [la investigación #373](https://github.com/buuuki/termia/issues/373).

# Corrección de memoria #374: trabajo y validación local

Estado: implementación validada y publicada para revisión. Commit `935ba7c`,
[PR #376](https://github.com/buuuki/termia/pull/376), asignado a `buuuki`. Rama
`fix/374-memory-retention`, basada en `release/0.6.0-beta.4-dev`. Se integra en
la beta.4 prevista; no se cambia la versión durante esta corrección.

## Cambios locales

- Los callbacks de los menús de desbordamiento usan referencias débiles al
  menú nativo y a la ventana para romper el ciclo de referencias.
- Cada panel conserva los identificadores de sus señales de interfaz y los
  retira cuando deja de pertenecer a una sesión. Se mantienen las señales de
  salida necesarias para registrar el historial antes de liberarlas.
- Las etiquetas de las pestañas también retiran sus señales propias. Se
  comprueba la vida de los widgets nativos, además de sus wrappers Python.
- Se está evaluando insertar la página y después asignar la etiqueta mediante
  las APIs públicas de GTK para evitar la referencia adicional retenida por
  la construcción con etiqueta explícita en GTK 4.14.

## Resultados comprobados

| Validación | Resultado |
| --- | --- |
| 100 pruebas específicas de pestañas, paneles y cierre | Correcto |
| Suite completa aislada final | 649 pruebas correctas en 125,006 s |
| Compilación sintáctica de Python | Correcto |
| Sintaxis del script de instalación | Correcto |
| Traducciones | 580 mensajes sincronizados |
| GTK aislado con dibujo, CSS y destrucción de ventanas | 100 ciclos correctos |
| Código real final bajo Valgrind | 20 combinaciones SSH; 0 accesos inválidos, sin supresiones |
| Laboratorio completo final | 32 combinaciones SSH/SFTP/SCP correctas |

Registros: `374-full-tests.log`, `374-notebook-rendered.log`,
`374-without-gdb.log`, `374-gdb-attach.log` y `374-gdb-mapping.log`.

## Bloqueo detectado en el laboratorio

El laboratorio repite ventanas con dos conexiones SSH y una conexión dividida,
con herramientas opcionales activadas y desactivadas. Sin depurador se
reproduce un fallo nativo al recargar el tema de una nueva ventana. Conservar
la inserción original con etiqueta explícita pasó las 20 combinaciones SSH,
pero deja pendiente la retención de esa etiqueta; esa comparación por sí sola
no identifica el origen del fallo.

Adjuntar GDB después del arranque permitió capturar el fallo. Una ejecución
mostró la destrucción de valores CSS durante `gtk_css_provider_load_named`.
La descarga de símbolos oficiales por debuginfod y por el paquete concreto
no estuvo disponible; no se modificaron bibliotecas del sistema anfitrión.

Valgrind encontró un error anterior: `g_nullify_pointer` escribe en memoria
de un GObject ya liberado cuando se destruye un VTE. La primera ejecución
terminó las 20 combinaciones SSH con seis errores de un mismo contexto;
no es una validación correcta de memoria. Registro: `374-valgrind.log`.

Retirar el foco antes de eliminar la página del notebook no eliminó los
errores: `374-valgrind-focus.log`. Se retiró ese cambio experimental. Se están
identificando los paneles nativos para determinar qué referencia permanece.

El cliente de diagnóstico incluye GDB y Valgrind. Sigue ejecutando Termia como
usuario sin privilegios, con capacidades eliminadas, red Docker interna,
Xvfb y D-Bus privados. No utiliza la sesión gráfica del usuario.

## Referencia nativa identificada y propuesta pendiente

La comparación de direcciones de `374-valgrind-paned.log` identifica el objeto
liberado como el `Gtk.Paned` de una división, no el panel principal. La escritura
afecta a su campo de foco del hijo final. El código público de GTK 4.14 limpia
estas referencias durante `unrealize`; su `dispose` no limpia esos dos campos.

`374-panel-state.log` confirmó que las divisiones afectadas estaban sin realizar
y sin mapear al retirarlas. El intento de cambiar el orden de desmontaje tampoco
eliminó el error (`374-valgrind-unparent-first.log`); se retiró ese experimento.

Una intervención temporal de la sonda que no da foco a VTE sin mapear pasó las
20 combinaciones SSH sin fallo nativo (`374-mapped-focus-probe.log`). Ahora se
valida con Valgrind una intervención más limitada: bloquear únicamente la
solicitud de foco hecha dentro de `SplitPaneController.split_terminal`.
Resultado final: las 20 combinaciones SSH pasan en 100,876 s y Valgrind informa
de cero errores de acceso a memoria, sin supresiones. Registro:
`374-valgrind-split-mapped.log`. No se activó el análisis de fugas de Valgrind:
este resultado no sustituye las mediciones de retención ni la implementación.

La intervención se ha separado en `focus_probe.py`. El laboratorio normal ya
no sustituye métodos de foco. Para reproducir únicamente el diagnóstico:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --diagnose-focus DockerLifecycleTests.test_ssh_lifecycle'
```

Para validar después el código real sin intervención de la sonda:

```bash
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --valgrind DockerLifecycleTests.test_ssh_lifecycle'
```

El usuario confirmó ampliar el plan a `src/termia/split_panes.py` y
`tests/test_split_panes.py`. Ya se implementó el foco al mapear la nueva división
y la retirada de esa solicitud si se cierra antes. La prueba también verifica
que un segundo mapeo no vuelve a robar el foco. Se conserva #374, la misma rama
y el único PR previsto; no se cambia la versión ni se crea otra issue.

El código real, sin sustituciones de foco, completó las 20 combinaciones SSH
bajo Valgrind en 100,963 s con cero errores de acceso y sin supresiones:
`374-production-valgrind.log`. La suite final pasó 649 pruebas y el laboratorio
normal completó sus 32 combinaciones en 49,499 s:
`374-final-full-tests.log` y `374-final-lifecycle.log`.

## Próxima validación necesaria

El acceso inválido ya está resuelto y se completaron las validaciones finales
indicadas a continuación. El diff y la privacidad se revisaron; se actualizaron
#373 y #374 y se publicó el PR #376. Próxima acción: revisión y confirmación
explícita de merge. No se ha hecho merge ni se ha borrado la rama. La retención
SFTP continúa por separado en #375, sin otra rama ni cambios iniciados.

## Comparación final de memoria y límites

| Recorrido | Antes | Corrección #374 |
| --- | --- | --- |
| Ocho ciclos locales: sesiones/VTE retenidos | 16 / 16 | 0 / 0 |
| RSS local, ciclos 1 a 8 | 152,06 → 165,04 MiB | 151,08 → 152,09 MiB |
| RSS mixta SSH/SFTP, ciclos 1 a 20 | 156,82 → 210,76 MiB | 157,58 → 183,35 MiB |

La sonda mixta se repitió sin tracemalloc y con referencias débiles nativas.
Durante sus veinte ciclos quedaron vivas 1, 5, 10, 15 y 20 ventanas SFTP cerradas.
Los descriptores volvieron a 11 y los hilos Python a 1; los procesos y conexiones
habían terminado. El crecimiento privado fue de 25,78 MiB. Un `malloc_trim(0)`
exclusivamente diagnóstico redujo la RSS a 178,57 MiB y dejó las veinte ventanas
vivas. Por tanto, no se presenta ese crecimiento como simple caché ni como un
problema completamente solucionado. Se registró en la [issue #375](https://github.com/buuuki/termia/issues/375),
asignada a `buuuki`, sin iniciar otra rama ni cambios SFTP.

En las muestras mixtas aparecen dos sesiones y tres VTE todavía vivos, con
cantidad constante a lo largo de los veinte ciclos; no se afirma que todos los
objetos de Termia se hayan liberado en esas muestras. La prueba local y las
regresiones nativas sí verifican la liberación completa del grafo que cubren.
Estos contadores distinguen la mejora del Core de la retención adicional SFTP.

La primera medición terminó el trabajador correctamente pero su envoltorio
devolvió 127 porque se editó `run.sh` mientras Bash seguía leyéndolo. Se repitió
íntegramente; la ejecución final devolvió 0. Evidencia final:
`374-memory20-diagnostic.log` y `374-memory20-diagnostic.json`. Los datos de la
primera ejecución se conservan, pero no se contabiliza como comando aprobado.

Los tres clics reales en la cruceta mantuvieron cuatro conexiones activas antes
del clic: tres SSH y una SFTP con subida en curso, sin desconexiones manuales.
En las tres ejecuciones el supervisor recogió el proceso, desaparecieron `/proc`
y `smaps`, y no quedaron procesos ni conexiones del laboratorio. Evidencia:
`374-final-cross.log` y `374-final-cross.json`.

También pasó el lanzador real `scripts/run_test_instance.sh --fresh` dentro del
cliente Docker, con una ventana visible, una segunda pestaña abierta mediante
Ctrl+Shift+T y cierre gestionado por SIGTERM sin hijos supervivientes:
`374-source-launch.log`. No se utilizó el escritorio ni la configuración personal.
