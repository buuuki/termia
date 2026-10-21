"""Diagnóstico local sintético de etiquetas y CSS, sin conexiones."""
import gc
import importlib.util
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch


def worker():
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, GLib, Gdk
    from termia.styles import build_application_css
    from termia.ui_state import SignalConnections

    def drain():
        for _ in range(10):
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(.005)

    for cycle in range(100):
        Gtk.Settings.get_default().reset_property('gtk-application-prefer-dark-theme')
        provider = Gtk.CssProvider()
        provider.load_from_data(build_application_css('#202020', '#ffffff', 1))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window, notebook = Gtk.Window(), Gtk.Notebook()
        notebook.add_css_class('termia-terminal-notebook')
        notebook.set_scrollable(True)
        notebook.set_show_tabs(False)
        window.set_child(notebook)
        window.present()
        drain()
        refs = []
        for i in range(3):
            page, label = Gtk.Box(), Gtk.Box()
            refs.append(label.weak_ref())
            label.add_css_class('termia-tab-label')
            text = Gtk.Label(label='Synthetic')
            text.add_css_class('termia-tab-title')
            label.append(text)
            button = Gtk.Button(label='x')
            button.add_css_class('termia-tab-close')
            label.append(button)
            label._signals = SignalConnections()
            label._signals.connect(button, 'clicked', lambda b: None, label, page)
            notebook.append_page(page, None)
            notebook.set_tab_label(page, label)
            notebook.get_page(page).set_property('tab-expand', True)
            notebook.set_show_tabs(notebook.get_n_pages() > 1)
            drain()
        while notebook.get_n_pages():
            current = notebook.get_tab_label(notebook.get_nth_page(0))
            current._signals.disconnect()
            notebook.remove_page(0)
            notebook.set_show_tabs(notebook.get_n_pages() > 1)
            drain()
        del page, label, current, text, button
        window.destroy()
        drain()
        gc.collect()
        assert all(ref() is None for ref in refs), cycle
    print('PASS 100 rendered GTK notebook/CSS/window lifetimes', flush=True)


if '--worker' in sys.argv:
    worker()
else:
    spec = importlib.util.spec_from_file_location('runner', 'scripts/run_sandbox_tests.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    original = subprocess.call

    def launch(command, **kwargs):
        kwargs['env']['PYTHONFAULTHANDLER'] = '1'
        return original([sys.executable, str(Path(__file__).resolve()), '--worker'], **kwargs)

    with patch.object(runner.subprocess, 'call', side_effect=launch):
        raise SystemExit(runner.run_tests())
