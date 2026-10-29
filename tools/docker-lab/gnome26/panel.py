"""GTK 4 panel for disposable Termia upgrade trials."""
import sys
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

sys.path.insert(0, "/opt/review/src")
from termia.dialog_actions import DIALOG_ACTION_INSET_BOTTOM, configure_dialog_content

TITLE = "Laboratorio de pruebas de Termia"
LAB = Path("/opt/upgrade-lab")
OUTPUT = Path.home() / "termia-updater-evidence"
app = Gtk.Application(
    application_id="org.termia.TestingLab",
    flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
)
window = None
child = None
status = None


def message(text):
    status.set_text(text)


def finished(process, result, label):
    global child
    try:
        process.wait_check_finish(result)
        outcome = "Finalizado: " + label + "."
    except GLib.Error as error:
        outcome = "Error en " + label + ": " + str(error)
    if child is process:
        child = None
    message(outcome)


def start(command, label, *, exclusive=True, profile=False):
    global child
    if exclusive and child is not None:
        message("Cierra Termia o termina la prueba activa antes de continuar.")
        return
    try:
        directory = Path(tempfile.mkdtemp(prefix="trial-", dir=OUTPUT))
        launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDERR_MERGE)
        launcher.set_stdout_file_path(str(directory / "console.log"))
        launcher.setenv("PYTHONUNBUFFERED", "1", True)
        if profile:
            launcher.setenv("XDG_CONFIG_HOME", str(directory / "config"), True)
            launcher.setenv("XDG_STATE_HOME", str(directory / "state"), True)
            launcher.setenv("TERMIA_CONFIG_DIR", str(directory / "config"), True)
            launcher.setenv("TERMIA_STATE_DIR", str(directory / "state"), True)
        process = launcher.spawnv(command)
    except (GLib.Error, OSError) as error:
        message("No se pudo iniciar " + label + ": " + str(error))
        return
    if exclusive:
        child = process
    process.wait_check_async(None, finished, label)
    message(label + " en curso. Registro: " + directory.name)


def launch(mode):
    start([sys.executable, str(LAB / "launch.py"), mode], mode, profile=True)


def label(text):
    widget = Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)
    widget.set_max_width_chars(36)
    return widget


def action(box, title, description, callback, color="blue"):
    row = Gtk.Box(spacing=8)
    button = Gtk.Button(label=title)
    button.set_size_request(100, -1)
    button.set_valign(Gtk.Align.CENTER)
    button.add_css_class("lab-" + color)
    button.connect("clicked", lambda *_: callback())
    row.append(button)
    text = label(description)
    text.set_hexpand(True)
    row.append(text)
    box.append(row)


def activate(application):
    global window, status
    if window is not None:
        window.present()
        return
    OUTPUT.mkdir(parents=True, exist_ok=True)
    window = Gtk.ApplicationWindow(application=application, title=TITLE)
    window.set_default_size(480, -1)
    window.add_css_class("termia-testing-lab")
    window.connect("close-request", closed)
    window.set_titlebar(Gtk.HeaderBar())
    css = Gtk.CssProvider()
    css.load_from_string("""
        .termia-testing-lab {
            font-size: 9pt;
        }
        .termia-testing-lab button {
            padding: 2px 8px;
            min-height: 22px;
        }
        .termia-testing-lab button.lab-blue {
            border: 1px solid #62a0ea;
            box-shadow: 0 0 3px alpha(#62a0ea, 0.45);
        }
        .termia-testing-lab button.lab-green {
            border: 1px solid #57e389;
            box-shadow: 0 0 3px alpha(#57e389, 0.40);
        }
    """)
    Gtk.StyleContext.add_provider_for_display(
        window.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    configure_dialog_content(body)
    body.set_margin_bottom(DIALOG_ACTION_INSET_BOTTOM)
    window.set_child(body)
    body.append(label("Ubuntu 26 · GNOME · Wayland\nPruebas de actualización · beta.3 → beta.4"))
    action(body, "Original", "Actualizador publicado sin la corrección; permite comparar.",
           lambda: launch("original"))
    action(body, "Propuesto", "Git beta.3 con revisión de dependencias.",
           lambda: launch("proposed"), "green")
    action(body, "Paquete .deb", "Prueba la actualización del paquete instalado.",
           lambda: launch("debian"), "green")
    body.append(Gtk.Separator())
    action(body, "Reiniciar", "Abre el código resultante de la actualización.",
           lambda: launch("restart"), "green")
    action(body, "Restaurar", "Restaura Termia beta.3 y el repositorio de pruebas.",
           lambda: start(["/usr/bin/ptyxis", "--standalone", "--",
                          sys.executable, str(LAB / "reset.py")], "restauración"))
    action(body, "Terminal", "Ejecuta los comandos manuales dentro del laboratorio.",
           lambda: start(["/usr/bin/ptyxis", "--standalone"],
                         "terminal", exclusive=False))
    details = Gtk.Expander(label="Información del escenario")
    password = (Path.home() / ".lab-password").read_text().strip()
    details.set_child(label(
        "Solo datos sintéticos. Usuario: lab. Contraseña de prueba: " + password
        + "\nLos modos propuestos cargan el nuevo actualizador sobre beta.3."
        + " El destino beta.4 usa archivos oficiales locales."
        + "\nEn Termia: menú → Acerca de → Buscar actualizaciones."
        + "\nCierra Termia antes de restaurar o cambiar de escenario."
    ))
    body.append(details)
    body.append(Gtk.Separator())
    status = label("Listo. Elige un escenario de prueba.")
    body.append(status)
    window.present()


def closed(*_args):
    global window
    if child is not None:
        message("Cierra Termia o termina la prueba activa antes de cerrar el laboratorio.")
        return True
    window = None
    return False


def command_line(application, command):
    application.activate()
    arguments = command.get_arguments()
    if (len(arguments) == 3 and arguments[1] == "--scenario"
            and arguments[2] in ("original", "proposed", "debian", "restart")):
        launch(arguments[2])
    return 0


app.connect("activate", activate)
app.connect("command-line", command_line)
if __name__ == "__main__":
    app.run(sys.argv)
