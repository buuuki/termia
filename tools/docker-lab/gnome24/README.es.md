# Laboratorio persistente Ubuntu 24.04 con GNOME

[English](README.md) · [Català](README.ca.md)

Infraestructura de #459. La construcción, el inicio de sesión GNOME/Wayland
y la entrada/imagen RDP se han validado localmente.
No equivale al laboratorio X11/Weston ni a la VM XFCE. No sustituye ni elimina
el laboratorio Ubuntu 26 ni los entornos anteriores.

## Requisitos y recursos

Linux amd64, Docker Engine local y Compose, cgroups v2, `/dev/fuse`, Python 3
y Git en el anfitrión. No se instalan herramientas en el anfitrión. Reserva
espacio para el escritorio completo y sus capas: el contenedor tiene 2 CPU,
4 GiB de RAM y 256 MiB de memoria compartida. El puerto 12389 debe estar libre.
No se ha validado Docker Desktop, rootless, ARM ni un segundo anfitrión.

La imagen fija el digest de Ubuntu 24.04 y una instantánea APT; instala
`ubuntu-desktop` con sus recomendaciones, GNOME Remote Desktop, idiomas
EN/ES/CA, Firefox nativo, dependencias de Termia, Git, Xvfb, GDB y Valgrind.
Ruff, Bandit y Coverage se instalan en un entorno virtual dentro de la imagen,
con las versiones declaradas en los requisitos del repositorio. Construir
puede descargar paquetes. No se ejecutan pruebas ni actualizaciones de Termia
al importar las herramientas o abrir el escritorio.

APT fija las versiones desde los índices firmados de la instantánea. Descarga
hasta ocho paquetes en paralelo desde el archivo oficial de Ubuntu, con
Snapshot como alternativa, y exige el SHA-256 de esos índices para cada archivo.
Cambiar el servidor de descarga no cambia las versiones ni los bytes aceptados.

## Construir y abrir

Desde la raíz del repositorio, con los archivos de la implementación añadidos
a Git para que formen parte de la instantánea:

```bash
python3 tools/docker-lab/gnome24/lab.py start
remmina -c tools/docker-lab/gnome24/laboratory.remmina
```

`start` prepara una instantánea permitida de archivos versionados, incluidos
sus cambios locales, construye con caché y crea o actualiza el mismo proyecto
`termia-459-gnome24`. Rechaza Docker remoto y recursos de otro checkout.
Una reconstrucción puede interrumpir la sesión RDP. Si falla la preparación
o construcción, no recrea el escritorio existente. Conserva una etiqueta de
la imagen anterior y no borra volúmenes.

Conecta a `127.0.0.1:12389`, usuario `lab`, dominio vacío. Consulta la
contraseña sintética solo cuando la necesites:

```bash
python3 tools/docker-lab/gnome24/lab.py password
```

Usa el acceso remoto nativo de GNOME 46: autentica primero RDP y
luego el usuario `lab` en GDM, con la misma contraseña sintética. El cliente
debe admitir redirección RDP; el comportamiento exacto se verificará en la
prueba de integración. La salud del listener no demuestra una sesión gráfica.
Comprueba la huella TLS antes de aceptar el certificado local:

```bash
docker exec termia-459-gnome24-desktop-1 openssl x509 -in /var/lib/gnome-remote-desktop/termia-tls/tls.crt -noout -sha256 -fingerprint
```

## Uso habitual y persistencia

```bash
python3 tools/docker-lab/gnome24/lab.py status
python3 tools/docker-lab/gnome24/lab.py logs
python3 tools/docker-lab/gnome24/lab.py stop
python3 tools/docker-lab/gnome24/lab.py resume
```

`stop` conserva el contenedor y sus datos. `resume` reabre la imagen existente;
no actualiza el código. `start` sí vuelve a preparar y comprobar la instantánea.
El panel muestra su identificador. No hay borrado automático ni reinicio
obligatorio al arrancar el anfitrión. Conserva credenciales, TLS y perfil antes
de cualquier retirada o recreación manual; nunca uses una limpieza global.

Abre el panel **Laboratorio de pruebas de Termia** desde las aplicaciones.
**Abrir Termia** reutiliza el perfil persistente del laboratorio; **Nueva prueba
aislada** crea otro perfil y conserva sus registros. El panel también abre
una terminal y permite ejecutar la batería con pantalla/bus privados. Todos
los datos de prueba se guardan en `~/termia-lab-evidence` del volumen `profile`.
Los temporales de pruebas viven ahí, en un directorio ejecutable, no en `/tmp`,
que Docker monta con `noexec`. No introduzcas credenciales reales.

Los volúmenes `profile`, `credentials` y `remote-state` pertenecen solo a este
proyecto. No se monta el escritorio, el hogar, el agente SSH ni el socket Docker
del anfitrión. Las imágenes contienen la instantánea de código y herramientas,
no perfiles ni contraseñas. Elegir idioma y reiniciar sesión debe conservar las
preferencias; esta persistencia requiere comprobación interactiva.

## Permisos y validación

Como el laboratorio Ubuntu 26, el laboratorio usa `SYS_ADMIN`, AppArmor sin
confinamiento para este contenedor, cgroups privados y el perfil seccomp
versionado existente de `gnome26`. Comparte `/dev/fuse`, pero no GPU, KVM ni el
árbol completo de cgroups del anfitrión. Son permisos amplios, no una garantía
de aislamiento mínimo. No cambia PAM ni las reglas polkit.

GNOME 46 exige pasar la contraseña sintética como argumento a su herramienta
de configuración: puede ser visible brevemente para procesos autorizados dentro
del contenedor. La utilidad evita registrar argumentos, errores con credenciales
o salida cruda. Nunca se usan contraseñas reales ni se publican datos generados.

Las entradas Xorg de Ubuntu se conservan porque GDM 46 las necesita para
inicializarse, incluso sin pantalla física. La sesión remota validada es Wayland.
El componente nativo de entrega se inicia con la pantalla de bienvenida y con
la sesión de usuario. Se desactiva `org.gnome.SettingsDaemon.Sharing.service`
solo en este laboratorio: la conexión Docker externa no constituye una conexión
primaria para ese gestor y provoca que detenga RDP. La gestión automática de
compartición de GNOME queda deshabilitada; el acceso RDP nativo sigue activo.

Validado localmente: inicio de sesión RDP con imagen e interacción, sesión
Wayland remota, panel y Termia con terminal VTE, y 819 tests automáticos.
La revisión interactiva de todos los idiomas y Firefox no forma parte de esa
comprobación. Esta infraestructura no certifica una publicación de Termia.

El servicio de color `colord` conserva su endurecimiento salvo `PrivateUsers`,
que se desactiva para evitar el fallo de inicio 217/USER dentro de Docker y
la espera de GNOME al iniciar RDP. No se añaden capacidades al contenedor.

Limitación observada de GNOME 46: la primera conexión después de recrear o
arrancar el contenedor puede agotar el tiempo de entrega y mostrar negro.
Espera a que termine esa conexión y vuelve a conectar con el mismo perfil RDP;
el segundo acceso permite iniciar sesión y utilizar el escritorio. El estado
`healthy` solo comprueba servicios y puerto, no elimina esta limitación.
