"""Arranque real aislado, nueva pestaña por teclado y cierre gestionado."""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from termia.terminal_processes import process_start_time


def wait(predicate, message):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.05)
    raise AssertionError(message)


with tempfile.TemporaryFile(mode='w+') as log:
    app = subprocess.Popen(['bash', 'scripts/run_test_instance.sh', '--fresh'],
                           stdout=log, stderr=subprocess.STDOUT)
    owned = {}
    try:
        def visible_window():
            result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(app.pid)],
                                    capture_output=True, text=True)
            return result.stdout.splitlines()[0] if result.returncode == 0 else None

        xid = wait(visible_window, 'Source launcher did not show its window')
        children_file = Path(f'/proc/{app.pid}/task/{app.pid}/children')

        def children():
            return [int(pid) for pid in children_file.read_text().split()]

        wait(lambda: children(), 'Startup local terminal was not spawned')
        subprocess.run(['xdotool', 'windowfocus', xid, 'key', '--clearmodifiers',
                        'ctrl+shift+t'], check=True)
        wait(lambda: len(children()) >= 2, 'Keyboard shortcut did not open a second terminal')
        owned = {pid: process_start_time(pid) for pid in children()}
        app.send_signal(signal.SIGTERM)
        assert app.wait(timeout=35) == 0, 'Source-launched application failed during shutdown'
        wait(lambda: all(process_start_time(pid) != birth for pid, birth in owned.items()),
             'Source launcher retained managed child processes')
        assert not Path(f'/proc/{app.pid}').exists()
        print('PASS source launcher --fresh: visible window, keyboard-created tab, managed SIGTERM shutdown, no surviving children', flush=True)
    finally:
        if app.poll() is None:
            app.kill()
            app.wait()
        for pid, birth in owned.items():
            if birth is not None and process_start_time(pid) == birth:
                os.kill(pid, signal.SIGKILL)
        log.seek(0)
        if app.returncode != 0:
            print(log.read())
