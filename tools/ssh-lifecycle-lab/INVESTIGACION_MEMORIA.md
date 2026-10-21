> Documento histórico del laboratorio. Los resultados corresponden a los commits indicados, no a una ejecución nueva de esta copia. Los registros originales permanecen locales. El estado actualizado y los límites están en [la investigación #373](https://github.com/buuuki/termia/issues/373).

# Diagnóstico: retención de menús y widgets de pestañas cerradas

Código analizado: `2dd0e1d`, rama `release/0.6.0-beta.4-dev`. Investigación local con Docker, usuario cliente sin privilegios, Xvfb y D-Bus privados. No se modificó el código versionado ni se creó issue, rama, commit o PR. No requiere cambiar la versión para realizar el diagnóstico.

Actualización de seguimiento, 21 de octubre: el diagnóstico original se registró después en la [investigación #373](https://github.com/buuuki/termia/issues/373) y la [issue de corrección #374](https://github.com/buuuki/termia/issues/374), ambas asignadas a `buuuki`. La implementación autorizada está en la rama `fix/374-memory-retention`, todavía sin commit ni PR. Su validación y el bloqueo nativo encontrado se documentan en [CORRECCION_374.md](CORRECCION_374.md).

Se confirmaron dos fuentes de retención de objetos de interfaz: menús de desbordamiento sustituidos y árboles de widgets de pestañas cerradas. No son procesos SSH que hayan quedado vivos. Los procesos se comprobaron por separado y habían terminado.

## Evidencia principal

Cada caso usa una instancia independiente, ocho ciclos y dos terminales locales por ciclo. No necesita SSH, SFTP ni una transferencia para reproducir el problema. Se espera el cierre de las identidades de los procesos, se procesan eventos durante 1,3 segundos y se solicita recolección de basura Python entre muestras.

| Variante de diagnóstico | Sesiones vivas al final | VTE nativos vivos | Menús vivos | RSS ciclo 1 → 8 |
| --- | ---: | ---: | ---: | ---: |
| Código actual | 16 | 16 | 113 | 152,06 → 165,04 MiB |
| Retirar callbacks propios de los widgets cerrados | 0 | 0 | 113 | 151,77 → 158,35 MiB |
| Retirar esos callbacks y las acciones del menú sustituido | 0 | 0 | 1, el actual | 151,29 → 152,32 MiB |

Las variantes se aplican con sustituciones temporales de métodos dentro de la sonda. No se guardan cambios en los módulos de Termia. No son todavía una implementación de producción ni validan todos sus comportamientos.

El crecimiento entre el primer y el octavo ciclo baja de 12,98 a 1,03 MiB en la última comparación. La diferencia inicial de memoria por carga de GTK y cachés no se confunde con el crecimiento entre ciclos. La instrumentación conserva contadores, referencias débiles, registros de handlers y muestras, por lo que tampoco debe exigirse que la RSS de la sonda sea idéntica después de cada ciclo.

Evidencia autoritativa de esta comparación: `retention-widget-results.log` (evidencia local no publicada) y `retention-widget-results.json` (evidencia local no publicada).

## 1. Menús sustituidos que conservan sus acciones

En `src/termia/tabs.py`, `rebuild_tab_overflow_popover`, líneas 104–141 del código analizado:

- Se crea un `Gtk.PopoverMenu`, un grupo de acciones y una acción `select`.
- El callback `activate`, desde la línea 123, captura `popover` y `self`.
- El menú contiene el grupo; el grupo contiene la acción; la acción conserva el callback que vuelve a referenciar el menú.
- `set_popover` sustituye el menú anterior en el botón, pero esa operación no rompe por sí sola el circuito de referencias observado.

La sonda reconstruyó el menú 200 veces, sin abrir ningún terminal:

| Variante | Menús creados | Menús vivos al final | Crecimiento RSS respecto al inicio |
| --- | ---: | ---: | ---: |
| Código actual | 201, incluido el inicial | 201 | 7,54 MiB |
| Retirar el grupo `tab-overflow` del menú anterior antes de sustituirlo | 201 | 1 | 0,00 MiB a la precisión registrada |

La intervención de diagnóstico fue únicamente `old.insert_action_group('tab-overflow', None)` antes de reconstruir. La prueba confirma que la propiedad del grupo/callback participa causalmente en la retención. No basta con atribuir este resultado a una caché genérica de GTK.

Evidencia: `retention-results.log` (evidencia local no publicada) y `retention-results.json` (evidencia local no publicada).

## 2. Referencias de los widgets a sesiones y a otros widgets

`src/termia/terminal_sessions.py` conecta señales que llevan la sesión y el terminal como datos:

- Botones de ocultar estado y desconectar, alrededor de las líneas 268–269 y 382–383.
- La señal `child-exited` de VTE, líneas 309 y 733.
- Controladores de teclado, foco y clic derecho, líneas 878–888.

La sesión conserva sus widgets; esos widgets o sus controladores conservan callbacks con la sesión. Las referencias observadas por el recolector incluían cinco tuplas `TerminalSession, Terminal` y una tupla `TerminalSession` en una sesión ya cerrada.

Además, `build_tab_label`, en `src/termia/tabs.py`, conecta handlers que conservan la propia etiqueta o la página:

- El cierre y el botón central reciben `page`, líneas 246 y 253.
- La fuente de arrastre recibe `box`, líneas 257–258.
- El clic derecho recibe `box`, línea 263.

La caja contiene sus controladores y estos referencian de nuevo la caja mediante los datos de sus señales. La etiqueta también puede conservar la página a través del botón de cierre. Por ello liberar solo las referencias que contienen directamente un `TerminalSession` es insuficiente para liberar todo el árbol nativo.

`close_tab`, líneas 715–736, termina los procesos, cancela transferencias, retira la página y elimina la sesión del registro. En el escenario medido esos pasos no deshacen todas las referencias de señales de los widgets retirados.

### Cómo se verificó

La sonda registra los identificadores de las conexiones de señales realizadas por callbacks del módulo `termia`. Después de cerrar la pestaña y verificar la muerte de los procesos, recorre la página, la etiqueta y sus controladores, y desconecta solo los handlers registrados por Termia en ese árbol. No usa destrucción indiscriminada de handlers internos de GTK.

Cuando se retiran todos esos handlers en el diagnóstico, las 16 sesiones y los 16 VTE nativos dejan de existir. Retirar además las acciones de los menús deja un solo menú, el instalado en el botón actual.

Esta desconexión deliberadamente tardía sirve para el experimento. Una corrección real debe decidir con precisión cuándo liberar cada handler sin perder callbacks de salida, registro de historial, estadísticas ni limpieza forzada pendiente.

## Precaución con las referencias débiles de PyGObject

Una referencia débil Python a un widget solo demuestra la vida del wrapper Python. El objeto nativo puede seguir vivo aunque ese wrapper desaparezca.

Una primera intervención retiró algunos handlers mediante referencias débiles Python y no alcanzó controladores cuyo wrapper ya había desaparecido. Se cambió el registro a `GObject.weak_ref()`. Esto permitió recuperar y desconectar el objeto nativo mientras siguiera existiendo.

También se cambió el contador de VTE a referencias débiles nativas. La tabla principal usa esta medida. Las comparaciones intermedias que contaban solo wrappers no se usan para afirmar que un VTE nativo se destruyera.

Los registros intermedios se conservan para explicar esa distinción:

- `retention-signals-results.log` (evidencia local no publicada) y `retention-signals-results.json` (evidencia local no publicada).
- `retention-native-signals-results.log` (evidencia local no publicada) y `retention-native-signals-results.json` (evidencia local no publicada).

## Lo confirmado y lo que falta

Confirmado:

- Hay objetos cerrados o sustituidos que permanecen vivos mientras Termia continúa abierto.
- Los menús pueden acumularse sin crear procesos terminales.
- Las sesiones y VTE pueden acumularse usando solo terminales locales.
- Retirar las conexiones adecuadas en el diagnóstico libera esos objetos.
- Esto es compatible con que los procesos SSH/locales mueran y con que el sistema libere la memoria al terminar Termia por completo.

Pendiente:

- Diseñar e implementar una gestión explícita de la propiedad de callbacks en el Core.
- Conservar la selección, el arrastre, los menús, las ventanas separadas, los paneles y las rutas de reintento/reconexión.
- Mantener los callbacks de salida necesarios hasta completar historial, estadísticas y limpieza de procesos.
- Repetir el escenario mixto original de veinte ciclos, los cierres por cruceta y las pruebas con opcionales activados/desactivados sobre la corrección final.
- No se ha demostrado que estas sean las únicas fuentes posibles de retención de toda la aplicación.

## Corrección propuesta para revisión

La responsabilidad afectada es el Core: pestañas, widgets y ciclo de vida del terminal. No exige nuevos enlaces con implementaciones de add-ons ni un cambio de controles GTK. Se conservarían los controles y los estilos actuales.

La corrección debería liberar las acciones del menú que se sustituye y gestionar explícitamente las conexiones de señales de los widgets de una sesión/panel cuando se retiran definitivamente. No debería desactivar todos los handlers de un widget ni retirar antes de tiempo los callbacks de procesos.

Los archivos previsiblemente afectados serían `src/termia/tabs.py`, `src/termia/terminal_sessions.py` y, si hace falta guardar la propiedad de los handlers, `src/termia/ui_state.py`; las pruebas de pestañas, paneles y limpieza en `tests/test_tabs.py`, `tests/test_terminal_panes.py` y `tests/test_terminal_cleanup.py`; y `CHANGELOG.md` bajo Unreleased. El alcance exacto y los contratos deben revisarse antes de implementar.

La validación debería comprobar destrucción de sesiones y widgets mediante referencias débiles, además de procesos y conexiones. Los umbrales rígidos de RSS no serían una buena aserción unitaria porque dependen del asignador y de GTK. La medición sostenida en el laboratorio complementaría las pruebas de propiedad de objetos.

No se ha autorizado ni iniciado esa implementación. Su issue de seguimiento es ahora #374. Si se aprueba la solución, corresponde crear una rama vinculada sobre la línea activa; el arreglo pertenecería al trabajo de beta.4 y no requiere editar la versión mientras se implementa.

## Reproducir la investigación

Desde la raíz del repositorio, una ejecución a la vez:

```bash
# Aislar terminales y menús.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --investigate'

# Comparación con contador nativo de VTE y liberación de handlers del árbol cerrado.
sg docker -c 'bash tools/ssh-lifecycle-lab/run.sh --investigate --modes local local-release-widget-signals local-release-all'
```

Los logs históricos corresponden a la versión de la sonda usada en cada etapa. La versión actual usa referencias débiles nativas para VTE y para registrar los handlers. No se modifica el programa que el usuario tiene abierto ni su configuración personal. El servidor del laboratorio se detiene al terminar.
