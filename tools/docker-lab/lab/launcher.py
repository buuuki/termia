"""Trace only synthetic laboratory tabs; leave production source untouched."""
import functools
import hashlib
import json
import os
from pathlib import Path
import time
import weakref

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk
from termia import __version__
from termia.app import TermiaApp, main
from termia.tabs import TabsMixin

OUT = Path(os.environ['LAB_RUN_DIR'])
TRACE = (OUT / 'interactions.jsonl').open('a', buffering=1)
HOST = None
COUNTS = {}


def emit(event, **fields):
    TRACE.write(json.dumps(dict(time_ns=time.time_ns(), event=event, **fields)) + '\n')


def fingerprint():
    root = Path('/opt/termia')
    digest = hashlib.sha256()
    files = [root / 'run_termia.py', *sorted(
        path for path in (root / 'src/termia').rglob('*')
        if path.is_file() and path.suffix in ('.py', '.mo')
    )]
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def install(name):
    original = getattr(TabsMixin, name)
    @functools.wraps(original)
    def traced(host, *args, **kwargs):
        global HOST
        HOST = weakref.ref(host)
        COUNTS[name] = COUNTS.get(name, 0) + 1
        if os.environ.get('LAB_TRACE') == 'detailed':
            emit('tab.callback', name=name, count=COUNTS[name])
        return original(host, *args, **kwargs)
    setattr(TabsMixin, name, traced)


for name in ('on_tab_drag_prepare', 'on_tab_drag_begin', 'on_tab_drag_end',
             'on_tab_bar_drop_motion', 'on_tab_bar_drop_leave', 'on_tab_bar_drop',
             'apply_pending_tab_reorder', 'reorder_dragged_tab_at_bar_x', 'set_active_session'):
    if hasattr(TabsMixin, name):
        install(name)


def sample():
    host = HOST() if HOST else None
    if host is not None and (OUT / 'stop.request').exists():
        (OUT / 'stop.request').unlink()
        host.close()
        return GLib.SOURCE_REMOVE
    return GLib.SOURCE_CONTINUE


def activated(app):
    window = app.props.active_window
    if window is None or getattr(window, '_lab_initialized', False):
        return GLib.SOURCE_REMOVE
    window._lab_initialized = True
    window.set_default_size(1000, 650)
    emit('runtime', version=__version__, source_sha256=fingerprint(),
         commit=Path('/opt/termia/BASE_COMMIT').read_text().strip(),
         backend=Gdk.Display.get_default().__class__.__name__,
         gtk=[Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()])
    target = int(os.environ.get('LAB_TABS', '16'))
    def add_tab():
        current = len(window.visible_sessions_in_tab_order())
        if current >= target:
            emit('fixture.ready', tabs=current)
            return GLib.SOURCE_REMOVE
        session = window.open_local_terminal_profile(None)
        if session is None:
            raise RuntimeError('Could not create laboratory terminal')
        session.title_locked = True
        session.title = f'LAB {current + 1:02d}'
        window.update_session_tab_title(session, session.title)
        return GLib.SOURCE_CONTINUE
    GLib.timeout_add(150, add_tab)
    GLib.timeout_add(250, sample)
    return GLib.SOURCE_REMOVE


original_init = TermiaApp.__init__
def initialize(app):
    original_init(app)
    app.connect('activate', lambda current: GLib.timeout_add(500, activated, current))
TermiaApp.__init__ = initialize

emit('launcher.start', pid=os.getpid())
try:
    code = main(['--debug'])
    emit('launcher.exit', code=code, counts=COUNTS)
    raise SystemExit(code)
finally:
    TRACE.close()
