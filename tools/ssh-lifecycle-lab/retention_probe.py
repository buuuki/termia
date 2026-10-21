import argparse
import gc
import json
import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
import weakref
from pathlib import Path
from unittest.mock import patch

from probe import DockerLifecycleTests, drain
from memory_probe import rollup
from termia.app import TermiaWindow
from termia.terminal_processes import process_session_members, process_start_time
from termia.ui_state import TerminalSession
from gi.repository import GObject


def settle():
    deadline = time.monotonic()+1.3
    while time.monotonic() < deadline:
        drain()
        time.sleep(.01)
    gc.collect()
    drain()


def worker(mode, cycles):
    DockerLifecycleTests.setUpClass()
    host = DockerLifecycleTests(methodName='test_ssh_lifecycle')
    original = TermiaWindow.rebuild_tab_overflow_popover
    popovers, sessions, terminals = [], [], []
    calls = [0]
    signal_records = {}
    widget_signal_records = {}
    original_connect = GObject.Object.connect

    def connect(widget, signal, callback, *data, **kwargs):
        handler = original_connect(widget, signal, callback, *data, **kwargs)
        if getattr(callback, '__module__', '').startswith('termia.'):
            widget_signal_records.setdefault(hash(widget), []).append((widget.weak_ref(), handler, signal))
        for value in data:
            if isinstance(value, TerminalSession):
                signal_records.setdefault(id(value), []).append((widget.weak_ref(), handler, signal))
        return handler

    def rebuild(window):
        calls[0] += 1
        if mode == 'local-without-overflow':
            return
        if mode in ('overflow-release-old', 'local-release-both', 'local-release-all') and hasattr(window, 'tab_overflow_button'):
            old = window.tab_overflow_button.get_popover()
            if old is not None:
                old.insert_action_group('tab-overflow', None)
        original(window)
        if hasattr(window, 'tab_overflow_button'):
            popover = window.tab_overflow_button.get_popover()
            if popover is not None:
                popovers.append(weakref.ref(popover))

    tracemalloc.start(5)
    samples = []
    with patch.object(TermiaWindow, 'rebuild_tab_overflow_popover', rebuild), patch.object(GObject.Object, 'connect', connect):
        with tempfile.TemporaryDirectory(prefix='termia-retention-') as temporary:
            window, store = host.window(Path(temporary), False)
            try:
                settle()
                before = tracemalloc.take_snapshot()
                def sample(cycle):
                    memory = rollup(os.getpid())
                    item = dict(mode=mode, cycle=cycle, rss_kib=memory['Rss'], private_kib=memory['Private_Clean']+memory['Private_Dirty'],
                                python_bytes=tracemalloc.get_traced_memory()[0], trace_metadata_bytes=tracemalloc.get_tracemalloc_memory(),
                                popovers_created=len(popovers), popovers_alive=sum(ref() is not None for ref in popovers),
                                sessions_alive=sum(ref() is not None for ref in sessions), terminals_alive=sum(ref() is not None for ref in terminals),
                                rebuild_calls=calls[0], fds=len(list(Path('/proc/self/fd').iterdir())))
                    samples.append(item)
                    print('RETENTION_SAMPLE '+json.dumps(item), flush=True)
                sample(0)

                def local_cycle():
                    opened = [window.open_process_terminal_tab('Synthetic local', ['/bin/sh'], None) for _ in range(2)]
                    owned = {}
                    for session in opened:
                        sessions.append(weakref.ref(session))
                        terminals.append(session.terminal.weak_ref())
                        for member in process_session_members(session.child_process.session_id):
                            owned[member.pid] = member.start_time
                    drain()
                    for session in opened:
                        window.close_tab(session.id, session.page, disconnect=True)
                    host.wait(lambda: all(process_start_time(pid) != birth for pid,birth in owned.items()), 'Local diagnostic processes remain')
                    if mode in ('local-release-signals', 'local-release-both'):
                        settle()
                        for session in opened:
                            for ref, handler, _signal in signal_records.get(id(session), []):
                                widget = ref()
                                if widget is not None and widget.handler_is_connected(handler):
                                    widget.disconnect(handler)
                    if mode in ('local-release-widget-signals', 'local-release-all'):
                        settle()
                        def disconnect_tree(widget):
                            if hasattr(widget, 'get_first_child'):
                                child = widget.get_first_child()
                                while child is not None:
                                    sibling = child.get_next_sibling()
                                    disconnect_tree(child)
                                    child = sibling
                                controllers = widget.observe_controllers()
                                for index in range(controllers.get_n_items()):
                                    disconnect_tree(controllers.get_item(index))
                            for ref, handler, _signal in widget_signal_records.get(hash(widget), []):
                                target = ref()
                                if target is not None and target.handler_is_connected(handler):
                                    target.disconnect(handler)
                        for session in opened:
                            disconnect_tree(session.page)
                            disconnect_tree(session.tab_label)

                for cycle in range(1, cycles+1):
                    if mode.startswith('local'):
                        local_cycle()
                    else:
                        for _ in range(25):
                            window.rebuild_tab_overflow_popover()
                    settle()
                    sample(cycle)
                after = tracemalloc.take_snapshot()
                growth = []
                for difference in after.compare_to(before, 'lineno'):
                    if difference.size_diff <= 0:
                        continue
                    filename = str(difference.traceback[0].filename)
                    if 'retention_probe.py' in filename or 'tracemalloc.py' in filename:
                        continue
                    growth.append(dict(file=filename, line=difference.traceback[0].lineno, bytes=difference.size_diff, count=difference.count_diff))
                    if len(growth) == 20:
                        break
                referrers = []
                survivor = next((r() for r in sessions if r() is not None), None)
                if survivor is not None:
                    for referrer in gc.get_referrers(survivor):
                        if isinstance(referrer, tuple):
                            referrers.append(dict(type='tuple', contents=[type(x).__name__ for x in referrer]))
                        else:
                            referrers.append(dict(type=type(referrer).__name__))
                result = dict(mode=mode, samples=samples, allocation_growth=growth, retained_session_referrers=referrers,
                              recorded_signals=sorted({name for records in signal_records.values() for _,_,name in records}))
                print('RETENTION_WORKER_RESULT '+json.dumps(result), flush=True)
            finally:
                host.cleanup(window, store)


def controller():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycles', type=int, default=8)
    parser.add_argument('--modes', nargs='+', default=['local', 'local-without-overflow', 'overflow-only', 'overflow-release-old'])
    args = parser.parse_args()
    results = []
    for mode in args.modes:
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', mode, str(args.cycles)], capture_output=True, text=True, timeout=240)
        print(p.stdout, end='', flush=True)
        print(p.stderr, end='', file=sys.stderr, flush=True)
        assert p.returncode == 0, (mode, p.returncode)
        results.append(next(json.loads(row.removeprefix('RETENTION_WORKER_RESULT ')) for row in p.stdout.splitlines() if row.startswith('RETENTION_WORKER_RESULT ')))
    print('RETENTION_RESULT '+json.dumps(results), flush=True)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1] == '--worker':
        worker(sys.argv[2], int(sys.argv[3]))
    else:
        controller()
