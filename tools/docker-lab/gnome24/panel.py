"""Native GTK panel: persistent Termia profile and private regression runs."""
from __future__ import annotations

import json
import locale
import os
import tempfile
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk

TEXT = {
    'en': ('Termia laboratory — Ubuntu 24', 'Open Termia', 'New isolated trial',
           'Run automated tests', 'Open terminal', 'Ready', 'Running; close Termia before another action.',
           'Finished', 'Failed; inspect the local log'),
    'es': ('Laboratorio Termia — Ubuntu 24', 'Abrir Termia', 'Nueva prueba aislada',
           'Ejecutar tests automáticos', 'Abrir terminal', 'Preparado', 'En curso; cierra Termia antes de otra acción.',
           'Finalizado', 'Error; consulta el registro local'),
    'ca': ('Laboratori Termia — Ubuntu 24', 'Obrir Termia', 'Nova prova aïllada',
           'Executar tests automàtics', 'Obrir terminal', 'Preparat', 'En curs; tanca Termia abans d’una altra acció.',
           'Finalitzat', 'Error; consulta el registre local'),
}


class LabPanel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.termia.Lab24')
        language = (locale.getlocale()[0] or 'en').split('_')[0]
        self.text = TEXT.get(language, TEXT['en'])
        self.window = None
        self.child = None
        self.output = Path.home() / 'termia-lab-evidence'
        self.output.mkdir(mode=0o700, exist_ok=True)
        self.temporary = self.output / 'tmp'
        self.temporary.mkdir(mode=0o700, exist_ok=True)

    def do_activate(self):
        if self.window is None:
            self.window = Gtk.ApplicationWindow(application=self, title=self.text[0])
            self.window.set_default_size(460, -1)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            for method in ('set_margin_top', 'set_margin_bottom', 'set_margin_start', 'set_margin_end'):
                getattr(box, method)(16)
            self.window.set_child(box)
            snapshot = json.loads(Path('/opt/termia/SNAPSHOT.json').read_text())
            identity = Gtk.Label(label='Snapshot: ' + snapshot['source_sha256'][:16], selectable=True)
            box.append(identity)
            for index, action in ((1, 'persistent'), (2, 'isolated'), (3, 'tests'), (4, 'terminal')):
                button = Gtk.Button(label=self.text[index])
                button.connect('clicked', self.launch, action)
                box.append(button)
            self.status = Gtk.Label(label=self.text[5], wrap=True, selectable=True)
            box.append(self.status)
            self.window.connect('close-request', self.hide_panel)
        self.window.present()

    def hide_panel(self, window):
        if self.child is not None:
            window.set_visible(False)
            return True
        self.window = None
        return False

    def launch(self, _button, action):
        if action == 'terminal':
            Gio.Subprocess.new(['/usr/bin/gnome-terminal'], Gio.SubprocessFlags.NONE)
            return
        if self.child is not None:
            self.status.set_label(self.text[6])
            return
        directory = Path(tempfile.mkdtemp(prefix='run-', dir=self.output))
        profile = self.output / 'persistent' if action == 'persistent' else directory
        command = ['/usr/bin/python3', '/opt/termia/run_termia.py']
        if action == 'tests':
            command = ['/opt/lab-tools/bin/python3', 'scripts/run_sandbox_tests.py']
        launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDERR_MERGE)
        launcher.set_cwd('/opt/termia')
        launcher.set_stdout_file_path(str(directory / 'console.log'))
        for key, value in {
            'TERMIA_CONFIG_DIR': str(profile / 'config'),
            'TERMIA_STATE_DIR': str(profile / 'state'),
            'TMPDIR': str(self.temporary), 'PYTHONUNBUFFERED': '1',
            'PYTHONDONTWRITEBYTECODE': '1',
            'PATH': '/opt/lab-tools/bin:' + os.environ.get('PATH', '/usr/bin:/bin'),
        }.items():
            launcher.setenv(key, value, True)
        try:
            self.child = launcher.spawnv(command)
        except GLib.Error:
            self.status.set_label(self.text[8] + ': ' + directory.name)
            return
        self.hold()
        self.child.wait_check_async(None, self.finished, directory)
        self.status.set_label(self.text[6])

    def finished(self, process, result, directory):
        try:
            process.wait_check_finish(result)
            message = self.text[7]
        except GLib.Error:
            message = self.text[8]
        self.child = None
        self.status.set_label(message + ': ' + directory.name)
        self.release()


if __name__ == '__main__':
    LabPanel().run(None)
