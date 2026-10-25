import argparse
import gc
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
import uuid
import weakref
from pathlib import Path
from unittest.mock import Mock, patch

import gi
from probe import DockerLifecycleTests, drain, isolated_command, status

from termia.terminal_processes import process_session_members, process_start_time

gi.require_version('GdkX11', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import GdkX11, Graphene, Gtk


def rollup(pid):
    values = {}
    try:
        for row in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
            fields = row.split()
            if len(fields) >= 3 and fields[2] == 'kB':
                values[fields[0].rstrip(':')] = int(fields[1])
    except FileNotFoundError:
        pass
    return values


def cgroup_memory():
    result = {}
    for name in ('memory.current', 'memory.peak'):
        path = Path('/sys/fs/cgroup')/name
        if path.exists():
            result[name] = int(path.read_text())
    return result


def settle():
    deadline = time.monotonic()+.6
    while time.monotonic() < deadline:
        drain()
        time.sleep(.01)
    gc.collect()
    drain()


def worker(run):
    DockerLifecycleTests.setUpClass()
    host = DockerLifecycleTests(methodName='test_ssh_lifecycle')
    cycles = int(os.environ.get('TERMIA_MEMORY_CYCLES', '5'))
    tracing = os.environ.get('TERMIA_MEMORY_TRACE', '1') == '1'
    close_live = os.environ.get('TERMIA_MEMORY_CLOSE_LIVE') == '1'
    if tracing:
        tracemalloc.start(10)
    samples = []
    retired_sessions, retired_vtes, retired_sftp = [], [], []

    def sample(phase, cycle):
        m = rollup(os.getpid())
        current, peak = tracemalloc.get_traced_memory() if tracing else (None, None)
        trace_overhead = tracemalloc.get_tracemalloc_memory() if tracing else 0
        item = dict(run=run, cycle=cycle, phase=phase, pid=os.getpid(), birth=process_start_time(os.getpid()),
                    rss_kib=m.get('Rss'), pss_kib=m.get('Pss'),
                    private_kib=m.get('Private_Clean', 0)+m.get('Private_Dirty', 0),
                    python_current_bytes=current, python_peak_bytes=peak,
                    trace_overhead_bytes=trace_overhead,
                    fds=len(list(Path('/proc/self/fd').iterdir())), threads=len(threading.enumerate()),
                    native_threads=int(Path('/proc/self/status').read_text().split('Threads:')[1].split()[0]),
                    cgroup=cgroup_memory(),
                    retired_sessions_alive=sum(ref() is not None for ref in retired_sessions),
                    retired_vtes_alive=sum(ref() is not None for ref in retired_vtes),
                    retired_sftp_alive=sum(ref() is not None for ref in retired_sftp))
        samples.append(item)
        print('MEMORY_SAMPLE '+json.dumps(item), flush=True)

    with tempfile.TemporaryDirectory(prefix='termia-memory-') as temporary:
        root = Path(temporary)
        window, store = host.window(root, True)
        completed_shutdown = False
        try:
            settle()
            sample('window-idle', 0)
            source = root/'synthetic-source.bin'
            with source.open('wb') as stream:
                stream.truncate(16*1024*1024)
            with source.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()

            def cycle(number):
                host.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Previous cycle left remote resources')
                servers = [host.server('password' if number%2 else 'key', uuid.uuid4().hex) for _ in range(3)]
                store.data.servers[:] = servers
                first, second = [window.open_terminal_tab(server) for server in servers[:2]]
                host.wait(lambda: all(s.id in status()['jobs'] for s in servers[:2]), 'Memory test SSH connections did not open')
                terminal = window.split_terminal_pane(first, first.terminal, 'horizontal')
                window.start_ssh_split_terminal(first, terminal, servers[2], announce=False)
                host.wait(lambda: servers[2].id in status()['jobs'], 'Memory test split did not open')
                owned = {}
                for process in (first.child_process, second.child_process, window.pane_state(first, terminal).child_process):
                    for member in process_session_members(process.session_id):
                        owned[member.pid] = member.start_time
                window.sftp_tool.browse(Mock(), first, servers[0])
                host.wait(lambda: bool(window.file_transfer_controllers), 'Memory test SFTP not registered')
                sftp = next(iter(window.file_transfer_controllers))
                retired_sessions.extend(weakref.ref(session) for session in (first, second))
                retired_vtes.extend(widget.weak_ref() for widget in (first.terminal, second.terminal, terminal))
                retired_sftp.append(sftp.weak_ref())
                host.wait(lambda: sftp.connection_ready and not sftp.service.busy, 'Memory test SFTP not ready')
                settle()
                sample('connected', number)
                remote = '/home/lab/memory-'+servers[0].id
                done = []
                sftp.run(lambda backend, report: backend.upload(source, remote, report), lambda value: done.append(value), transfer=True)
                host.wait(lambda: bool(done), 'Memory test upload failed', timeout=60)
                sample('after-upload', number)
                target = root/'synthetic-download.bin'
                done.clear()
                sftp.run(lambda backend, report: backend.download(remote, target, report), lambda value: done.append(value), transfer=True)
                host.wait(lambda: bool(done), 'Memory test download failed', timeout=60)
                with target.open('rb') as stream:
                    host.assertEqual(hashlib.file_digest(stream, 'sha256').hexdigest(), digest)
                sample('after-download', number)
                done.clear()
                sftp.run(lambda backend, report: backend.delete(remote), lambda value: done.append(value))
                host.wait(lambda: bool(done), 'Memory test remote fixture removal failed')
                target.unlink()
                window.close_tab(first.id, first.page, disconnect=True)
                window.close_tab(second.id, second.page, disconnect=True)
                host.wait(lambda: sftp.service.stopped and not window.file_transfer_controllers, 'Memory test SFTP workers or window ownership remain')
                host.wait(lambda: all(process_start_time(pid) != birth for pid,birth in owned.items()), 'Memory test local children remain')
                host.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Memory test remote resources remain')
                host.assertEqual(len(window.session_registry.sessions()), 0)
                store.data.servers.clear()

            live_owned = {}
            live_sftp = None
            live_transport = None
            click_details = None
            with patch('termia.terminal_sessions.build_ssh_command', side_effect=isolated_command):
                if close_live:
                    servers = [host.server('password' if run%2 else 'key', uuid.uuid4().hex) for _ in range(3)]
                    store.data.servers[:] = servers
                    first, second = [window.open_terminal_tab(server) for server in servers[:2]]
                    host.wait(lambda: all(s.id in status()['jobs'] for s in servers[:2]), 'Cross test SSH sessions did not connect')
                    terminal = window.split_terminal_pane(first, first.terminal, 'horizontal')
                    window.start_ssh_split_terminal(first, terminal, servers[2], announce=False)
                    host.wait(lambda: servers[2].id in status()['jobs'], 'Cross test SSH split did not connect')
                    for process in (first.child_process, second.child_process, window.pane_state(first, terminal).child_process):
                        for member in process_session_members(process.session_id):
                            live_owned[member.pid] = member.start_time
                    window.sftp_tool.browse(Mock(), first, servers[0])
                    host.wait(lambda: bool(window.file_transfer_controllers), 'Cross test SFTP not registered')
                    live_sftp = next(iter(window.file_transfer_controllers))
                    host.wait(lambda: live_sftp.connection_ready and not live_sftp.service.busy, 'Cross test SFTP not ready')
                    live_transport = live_sftp.service.backend.client.get_transport()
                    started = threading.Event()
                    def upload_live(backend, report):
                        def progress(*args, **kwargs):
                            started.set()
                            time.sleep(.03)
                            report(*args, **kwargs)
                        return backend.upload(source, '/home/lab/cross-'+servers[0].id, progress)
                    live_sftp.run(upload_live, transfer=True)
                    host.wait(started.is_set, 'Cross test upload did not start')
                    host.assertTrue(live_sftp.service.busy)
                    host.wait(lambda: status()['established'] == 4, 'Cross test must have 3 SSH and 1 SFTP connections')
                    sample('live-upload-before-cross', 0)
                else:
                    for number in range(1, cycles+1):
                        cycle(number)
                        settle()
                        sample('cycle-clean', number)
                    if os.environ.get('TERMIA_MEMORY_DIAGNOSTIC_TRIM') == '1':
                        import ctypes
                        ctypes.CDLL(None).malloc_trim(0)
                        settle()
                        sample('diagnostic-malloc-trim', cycles)
            with patch('termia.app.log_event') as events:
                if close_live:
                    def close_button(widget):
                        if isinstance(widget, Gtk.Button) and widget.has_css_class('close') and widget.get_mapped():
                            return widget
                        child = widget.get_first_child()
                        while child is not None:
                            found = close_button(child)
                            if found is not None:
                                return found
                            child = child.get_next_sibling()
                        return None
                    window.present()
                    settle()
                    button = close_button(window.get_titlebar())
                    host.assertIsNotNone(button, 'Native titlebar close button is unavailable')
                    valid, point = button.compute_point(window, Graphene.Point().init(button.get_width()/2, button.get_height()/2))
                    host.assertTrue(valid)
                    xid = GdkX11.X11Surface.get_xid(window.get_surface())
                    click_details = dict(xid=xid, x=round(point.x), y=round(point.y), button_classes=list(button.get_css_classes()), manual_disconnects=0, active_connections=4)
                    subprocess.run(['xdotool', 'windowraise', str(xid), 'mousemove', '--window', str(xid), str(round(point.x)), str(round(point.y)), 'click', '1'], check=True)
                else:
                    window.close()
                host.wait(lambda: any(c.args == ('application.shutdown_finished',) for c in events.call_args_list), 'Memory test application shutdown did not finish')
                events.assert_any_call('application.shutdown_finished', cleanup='stopped')
            if close_live:
                host.wait(lambda: live_sftp.service.stopped and not live_transport.is_alive(), 'Cross test left SFTP threads')
                host.wait(lambda: all(process_start_time(pid) != birth for pid,birth in live_owned.items()), 'Cross test left local SSH/VTE processes')
                host.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Cross test left remote resources')
                print('MEMORY_CROSS_VERIFIED '+json.dumps(click_details), flush=True)
            completed_shutdown = True
            settle()
            sample('shutdown-callback-finished', cycles)
        finally:
            host.cleanup(window, store)
    assert completed_shutdown
    print('MEMORY_WORKER_RESULT '+json.dumps(dict(run=run, samples=samples, successful_shutdown=True)), flush=True)


def controller():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--cycles', type=int, default=5)
    parser.add_argument('--no-tracemalloc', action='store_true')
    parser.add_argument('--close-live', action='store_true')
    parser.add_argument('--trim-diagnostic', action='store_true')
    args = parser.parse_args()
    assert args.runs > 0 and args.cycles > 0
    results = []
    for run in range(1, args.runs+1):
        before = cgroup_memory()
        env = os.environ.copy()
        env['TERMIA_MEMORY_CYCLES'] = str(args.cycles)
        env['TERMIA_MEMORY_TRACE'] = '0' if args.no_tracemalloc else '1'
        env['TERMIA_MEMORY_CLOSE_LIVE'] = '1' if args.close_live else '0'
        env['TERMIA_MEMORY_DIAGNOSTIC_TRIM'] = '1' if args.trim_diagnostic else '0'
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(run)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        birth = process_start_time(process.pid)
        try:
            out, err = process.communicate(timeout=max(240, args.cycles*30))
        except subprocess.TimeoutExpired:
            process.kill()
            out, err = process.communicate()
            raise AssertionError('Memory worker exceeded its deadline\n'+out+'\n'+err)
        print(out, end='', flush=True)
        print(err, end='', file=sys.stderr, flush=True)
        assert process.returncode == 0, f'Memory worker failed: {process.returncode}'
        assert not Path(f'/proc/{process.pid}').exists(), 'Worker remains in /proc after wait'
        assert process_start_time(process.pid) != birth, 'Worker birth identity remains'
        time.sleep(.8)
        assert status()['established'] == 0 and not status()['processes']
        item = next(json.loads(row.removeprefix('MEMORY_WORKER_RESULT ')) for row in out.splitlines() if row.startswith('MEMORY_WORKER_RESULT '))
        if args.close_live:
            item['cross_click'] = next(json.loads(row.removeprefix('MEMORY_CROSS_VERIFIED ')) for row in out.splitlines() if row.startswith('MEMORY_CROSS_VERIFIED '))
        item.update(cgroup_before=before, cgroup_after=cgroup_memory(), worker_reaped=True, worker_smaps_after=rollup(process.pid))
        assert item['worker_smaps_after'] == {}
        results.append(item)
        print(f'MEMORY_EXIT run={run}: process reaped, /proc and smaps gone, 0 remote processes/connections', flush=True)
    print('MEMORY_RESULT '+json.dumps(dict(runs=results, cycles_per_run=0 if args.close_live else args.cycles, payload_bytes=16*1024*1024, python_tracing=not args.no_tracemalloc, close_with_live_connections=args.close_live)), flush=True)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1] == '--worker':
        worker(int(sys.argv[2]))
    else:
        controller()
