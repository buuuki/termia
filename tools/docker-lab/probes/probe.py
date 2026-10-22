import collections
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import traceback
import weakref
from unittest.mock import patch

MODE = sys.argv[1]
BACKEND = sys.argv[2] if len(sys.argv) > 2 else 'x11'
OUT = Path(os.environ.get('TERMIA_PROBE_OUTPUT', str(Path(__file__).resolve().parent))) / (MODE + '-' + BACKEND)
OUT.mkdir(parents=True, exist_ok=True)
profile = Path(tempfile.mkdtemp(prefix='termia-tab-qa-'))
runtime = profile / 'runtime'
runtime.mkdir(mode=0o700)
os.environ.update(TERMIA_CONFIG_DIR=str(profile / 'config'), TERMIA_STATE_DIR=str(profile / 'state'),
                  XDG_RUNTIME_DIR=str(runtime), GDK_BACKEND=BACKEND, GSETTINGS_BACKEND='memory',
                  GTK_A11Y='none', NO_AT_BRIDGE='1', GSK_RENDERER='cairo', LIBGL_ALWAYS_SOFTWARE='1')
os.environ.pop('SSH_AUTH_SOCK', None)
weston = None
openbox = None
if BACKEND == 'x11':
    openbox = subprocess.Popen(['openbox'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(.2)
if BACKEND == 'wayland':
    os.environ['WAYLAND_DISPLAY'] = 'qa-tabs'
    weston = subprocess.Popen(['weston', '--backend=x11-backend.so', '--renderer=pixman',
                               '--socket=qa-tabs', '--width=1280', '--height=800', '--idle-time=0',
                               '--no-config', '--log=' + str(OUT / 'weston.log')],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 8
    while not (runtime / 'qa-tabs').exists():
        if time.monotonic() > deadline or weston.poll() is not None:
            raise RuntimeError('Private Weston did not start')
        time.sleep(.05)

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Gtk, Gdk, GLib, Graphene
from termia.app import TermiaApp, TermiaWindow
from termia.stores import ConnectionStore
from termia.terminal_processes import terminal_process_is_active

ROOT = Path('/opt/termia/src/termia')
def source_hash():
    h = hashlib.sha256()
    for p in sorted(ROOT.rglob('*.py')):
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()

def drain(seconds=.1):
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        for _ in range(100):
            if not context.pending():
                break
            context.iteration(False)
        time.sleep(.002)

refs = collections.defaultdict(list)
counts = collections.Counter()
processes = []
samples = []
result = dict(mode=MODE, backend=BACKEND, source_sha256=source_hash(), checks=[], samples=samples)
app = None
window = None

def check(condition, label):
    if not condition:
        raise AssertionError(label)
    result['checks'].append(label)

def memory(label, settle=.12):
    drain(settle)
    gc.collect()
    drain(.03)
    metrics = {}
    for line in Path('/proc/self/smaps_rollup').read_text().splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            if key in ('Rss', 'Pss', 'Private_Clean', 'Private_Dirty'):
                metrics[key + '_KiB'] = int(value.split()[0])
    metrics['private_KiB'] = metrics.pop('Private_Clean_KiB') + metrics.pop('Private_Dirty_KiB')
    metrics.update(label=label, live={key: sum(ref() is not None for ref in group) for key, group in refs.items()},
                   created={key: len(group) for key, group in refs.items()},
                   fds=len(list(Path('/proc/self/fd').iterdir())), threads=len(list(Path('/proc/self/task').iterdir())),
                   registry=len(window.session_registry.sessions()),
                   running_children=sum(terminal_process_is_active(p) for p in processes))
    samples.append(metrics)
    print(json.dumps(dict(sample=metrics)), flush=True)
    return metrics

def add_terminal(title):
    session = window.open_process_terminal_tab(title, ['/bin/sh'], None)
    if session is None:
        raise RuntimeError('Terminal creation failed')
    session.title_locked = True
    session.title = title
    window.update_session_tab_title(session, title)
    processes.append(session.child_process)
    refs['sessions'].append(weakref.ref(session))
    for key, widget in (('vte', session.terminal), ('pages', session.page), ('labels', session.tab_label)):
        refs[key].append(widget.weak_ref())
    for controller in session.tab_label.observe_controllers():
        if isinstance(controller, Gtk.DragSource):
            def begun(_controller, drag):
                counts['drag_begin'] += 1
                refs['drags'].append(drag.weak_ref())
                refs['drag_icons'].append(Gtk.DragIcon.get_for_drag(drag).weak_ref())
            def ended(*_args):
                counts['drag_end'] += 1
            controller.connect('drag-begin', begun)
            controller.connect('drag-end', ended)
    return session

def pointer(*args):
    subprocess.run(['xdotool', *map(str, args)], check=True, stdout=subprocess.DEVNULL)
    drain(.025)

def point_in_window(widget, x, y):
    valid, point = widget.compute_point(window, Graphene.Point().init(x, y))
    if not valid:
        raise RuntimeError('Unmapped drag coordinates')
    if BACKEND == 'x11':
        surface = window.get_surface()
        return (int(point.x + (surface.get_width() - window.get_width()) / 2),
                int(point.y + (surface.get_height() - window.get_height()) / 2))
    return int(point.x + wayland_origin[0]), int(point.y + wayland_origin[1])

def move_to(point):
    if BACKEND == 'x11':
        pointer('mousemove', '--window', xid, *point)
    else:
        pointer('mousemove', *point)

def drag_to_edge(session, left, cancel=False):
    window.set_active_session(session.id)
    drain(.15)
    adjustment = window.session_tab_scroller.get_hadjustment()
    start = point_in_window(session.tab_label, 24, session.tab_label.get_height() / 2)
    print(json.dumps(dict(drag_start=dict(point=start, label_size=[session.tab_label.get_width(), session.tab_label.get_height()],
        offset=adjustment.get_value(), viewport=adjustment.get_page_size(), maximum=adjustment.get_upper()-adjustment.get_page_size(),
        controllers=[type(c).__name__ for c in session.tab_label.observe_controllers()]))), flush=True)
    before = counts['drag_begin']
    move_to(start)
    pointer('mousedown', 1)
    drain(.15)
    move_to((start[0] + 24, start[1]))
    drain(.15)
    check(counts['drag_begin'] == before + 1, 'pointer started drag ' + str(before + 1))
    x = 9 if left else adjustment.get_page_size() - 9
    edge = point_in_window(window.session_tab_scroller, x, 18)
    move_to(edge)
    drain(.1)
    move_to((edge[0] + (1 if left else -1), edge[1]))
    drain(.1)
    move_to(edge)
    if cancel:
        drain(.18)
        outside = point_in_window(window.session_tab_scroller, x, 150)
        move_to(outside)
        pointer('key', 'Escape')
        pointer('mouseup', 1)
        drain(.8)
    else:
        deadline = time.monotonic() + 9
        while time.monotonic() < deadline:
            order = window.visible_sessions_in_tab_order()
            at_edge = adjustment.get_value() <= .1 if left else (
                adjustment.get_value() >= adjustment.get_upper() - adjustment.get_page_size() - .1)
            if at_edge and order[0 if left else -1] is session:
                break
            check(window.visible_terminal_page() is session.page, 'active page held during drag ' + str(before + 1))
            drain(.035)
        else:
            raise AssertionError('Edge drag did not reach destination: ' + json.dumps(
                dict(left=left, offset=adjustment.get_value(), maximum=adjustment.get_upper()-adjustment.get_page_size(),
                     order=[s.title for s in window.visible_sessions_in_tab_order()])))
        pointer('mouseup', 1)
        drain(.4)
        check(window.visible_sessions_in_tab_order()[0 if left else -1] is session,
              'edge reorder completed ' + str(before + 1))
    check(getattr(window, 'tab_drag_scroll_id', None) is None and
          getattr(window, 'tab_drag_scroll_context', None) is None,
          'scroll timer and drag references released ' + str(before + 1))
    offset = adjustment.get_value()
    active = window.visible_terminal_page()
    drain(.3)
    check(abs(offset-adjustment.get_value()) < .1 and window.visible_terminal_page() is active,
          'selection and scroll stable after release ' + str(before + 1))

try:
    app = TermiaApp()
    app.register(None)
    store = ConnectionStore(profile / 'connections.json', profile / 'settings.json',
                            profile / 'statistics.json', profile / 'instance.lock', profile / 'history')
    store.data.app.open_local_terminal_on_startup = False
    store.data.app.confirm_disconnect = False
    store.data.app.confirm_close_app = False
    store.data.app.restore_sessions_on_startup = False
    store.data.app.statistics_enabled = MODE.endswith('enabled')
    store.data.app.sftp_enabled = MODE.endswith('enabled')
    with patch('termia.app.ConnectionStore', return_value=store):
        window = TermiaWindow(app)
    for method_name in ('on_tab_left_press', 'on_tab_drag_prepare', 'on_tab_drag_begin', 'on_tab_drag_end'):
        def trace_call(name, original):
            def call(*args, **kwargs):
                counts[name] += 1
                print(json.dumps(dict(callback=name)), flush=True)
                return original(*args, **kwargs)
            return call
        setattr(window, method_name, trace_call(method_name, getattr(window, method_name)))
    menu = window.tab_overflow_button.get_popover()
    refs['menus'].append(menu.weak_ref())
    original_refresh = window.refresh_tab_overflow_menu
    def tracked_refresh():
        counts['menu_open_refreshes'] += 1
        return original_refresh()
    window.refresh_tab_overflow_menu = tracked_refresh
    original_reorder = window.reorder_dragged_tab_at_bar_x
    def tracked_reorder(*args, **kwargs):
        before = tuple(s.id for s in window.visible_sessions_in_tab_order())
        original_reorder(*args, **kwargs)
        if before != tuple(s.id for s in window.visible_sessions_in_tab_order()):
            counts['effective_reorders'] += 1
    window.reorder_dragged_tab_at_bar_x = tracked_reorder
    window.set_default_size(1000, 650)
    window.present()
    if BACKEND == 'wayland':
        window.maximize()
    drain(.35)
    result['runtime'] = dict(gtk=[Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()],
                             display=Gdk.Display.get_default().__class__.__name__)
    if BACKEND == 'x11':
        gi.require_version('GdkX11', '4.0')
        from gi.repository import GdkX11
        xid = GdkX11.X11Surface.get_xid(window.get_surface())
        print(json.dumps(dict(geometry=dict(window=[window.get_width(), window.get_height()],
                                           surface=[window.get_surface().get_width(), window.get_surface().get_height()]))), flush=True)
        pointer('windowfocus', xid)
    else:
        outer = subprocess.check_output(['xdotool', 'search', '--class', 'Weston'], text=True).splitlines()[0]
        geometry = subprocess.check_output(['xwininfo', '-id', outer], text=True)
        wayland_origin = (int(re.search(r'Absolute upper-left X:\s+(-?\d+)', geometry)[1]),
                          int(re.search(r'Absolute upper-left Y:\s+(-?\d+)', geometry)[1]) + 32)
        pointer('windowfocus', outer)
    memory('initial')
    if MODE == 'smoke':
        first = add_terminal('Smoke first')
        second = add_terminal('Smoke second')
        drain(.2)
        check(window.get_mapped(), 'application window mapped')
        check(window.visible_terminal_page() is second.page, 'second terminal selected')
        window.set_active_session(first.id)
        check(window.visible_terminal_page() is first.page, 'first terminal selectable')
        window.close_tab(second.id, second.page, disconnect=True)
        window.close_tab(first.id, first.page, disconnect=True)
        drain(1.2)
        check(not any(terminal_process_is_active(p) for p in processes), 'smoke child processes stopped')
    elif MODE == 'menus':
        sessions = [add_terminal('Menu tab ' + str(i)) for i in range(6)]
        window.set_default_size(600, 650)
        drain(.3)
        for batch in range(6):
            for _ in range(50):
                window.tab_overflow_button.popup()
                drain(.02)
                window.tab_overflow_button.popdown()
                drain(.02)
            memory('menu openings ' + str((batch + 1) * 50))
        result['menu_openings'] = 300
        check(counts['menu_open_refreshes'] == 300, 'menu refreshed once per opening')
        check(window.tab_overflow_button.get_popover() is menu, 'single popover reused')
        for session in sessions:
            window.close_tab(session.id, session.page, disconnect=True)
    elif MODE.startswith('churn'):
        for cycle in range(20):
            def churn():
                sessions = [add_terminal('cycle ' + str(cycle) + ' tab ' + str(i)) for i in range(2)]
                drain(.12)
                for session in sessions:
                    window.close_tab(session.id, session.page, disconnect=True)
            churn()
            sample = memory('terminal cycle ' + str(cycle + 1), settle=1.15)
            check(sample['registry'] == 0 and sample['running_children'] == 0,
                  'cycle resources stopped ' + str(cycle + 1))
    elif MODE in ('behavior', 'continuous'):
        sessions = [add_terminal('LAB ' + str(i + 1).zfill(2)) for i in range(16)]
        drain(.5)
        memory('16 tabs before drag')
        moving = sessions[-1]
        if MODE == 'behavior':
            for iteration in range(40):
                drag_to_edge(moving, iteration % 2 == 0)
                if iteration % 10 == 9:
                    memory('completed drags ' + str(iteration + 1))
            for left in (True, False, True, False):
                drag_to_edge(moving, left, cancel=True)
            check(counts['drag_begin'] == counts['drag_end'] == 44, '44 native drags began and ended')
        else:
            window.set_active_session(moving.id)
            drain(.2)
            start = point_in_window(moving.tab_label, 24, moving.tab_label.get_height() / 2)
            move_to(start)
            pointer('mousedown', 1)
            drain(.15)
            move_to((start[0] + 24, start[1]))
            drain(.15)
            check(counts['drag_begin'] == 1, 'one continuous native drag began')
            width = window.session_tab_scroller.get_hadjustment().get_page_size()
            for sweep in range(100):
                points = (.02, .2, .4, .6, .8, .98)
                if sweep % 2:
                    points = tuple(reversed(points))
                for fraction in points:
                    move_to(point_in_window(window.session_tab_scroller, width * fraction, 18))
                    check(window.visible_terminal_page() is moving.page, 'continuous drag keeps active page')
                if sweep % 10 == 9:
                    drain(.35)
                if sweep in (49, 99):
                    memory('continuous sweeps ' + str(sweep + 1))
            pointer('mouseup', 1)
            drain(.5)
            check(counts['drag_begin'] == counts['drag_end'] == 1,
                  '100 sweeps used one uninterrupted press and release')
            check(getattr(window, 'tab_drag_scroll_id', None) is None and
                  getattr(window, 'tab_drag_scroll_context', None) is None,
                  'continuous drag released scroll timer and drop references')
        check(len(window.visible_sessions_in_tab_order()) == 16, 'all sixteen tabs preserved')
        memory('after drags and cancellations')
        result['behavior_passed'] = True
    else:
        raise ValueError(MODE)
    result['counts'] = dict(counts)
    result['source_unchanged'] = source_hash() == result['source_sha256']
    result['completed'] = True
except BaseException:
    result.update(completed=False, error=traceback.format_exc(), counts=dict(counts))
    print(result['error'], flush=True)
finally:
    if samples and MODE != 'smoke':
        last_live = samples[-1].get('live', {})
        result['retention_detected'] = (last_live.get('menus', 0) > 1 or
                                        (MODE.startswith('churn') and last_live.get('vte', 0) > 0))
    if window is not None:
        subprocess.run(['xdotool', 'mouseup', '1', 'key', 'Escape'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        window.begin_main_window_shutdown()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            drain(.1)
            if not any(terminal_process_is_active(p) for p in processes):
                break
        window.destroy()
        result['cleanup'] = dict(window_closed=not window.get_visible(),
                                 running_children=sum(terminal_process_is_active(p) for p in processes))
    if weston is not None:
        weston.terminate()
        weston.wait(timeout=5)
    if openbox is not None:
        openbox.terminate()
        openbox.wait(timeout=5)
    (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks', 'samples')}), flush=True)
raise SystemExit(0 if result.get('completed') else 1)
