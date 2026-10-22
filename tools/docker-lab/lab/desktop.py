"""Small X11 control panel outside the nested Wayland desktop."""
import hashlib
import json
import os
import signal
import subprocess
import time
import tkinter as tk
from pathlib import Path

ROOT = Path('/evidence')
child = None
stream = None
run_dir = None
finished = False
app = tk.Tk()
app.title('Termia — laboratorio local')
app.geometry('1400x125+10+850')
backend = tk.StringVar(value='wayland')
trace = tk.StringVar(value='minimal')
debugger = tk.BooleanVar(value=False)
tabs = tk.StringVar(value='16')
status = tk.StringVar(value='Preparado')


def source_fingerprint():
    root = Path('/opt/termia')
    files = [root / 'run_termia.py', *sorted(
        path for path in (root / 'src/termia').rglob('*')
        if path.is_file() and path.suffix in ('.py', '.mo')
    )]
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def launch():
    global child, stream, run_dir, finished
    if child is not None and child.poll() is None:
        status.set('Termia sigue activo. Ciérralo desde su ventana antes de reiniciar.')
        return
    if stream:
        stream.close()
    count = int(tabs.get())
    if not 1 <= count <= 40:
        raise ValueError('Tabs must be between 1 and 40')
    run_dir = ROOT / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns() % 1000000))
    run_dir.mkdir()
    env = os.environ.copy()
    env.update(GDK_BACKEND=backend.get(), WAYLAND_DISPLAY='wayland-lab',
               XDG_SESSION_TYPE=backend.get(), TERMIA_CONFIG_DIR=str(run_dir/'config'),
               TERMIA_STATE_DIR=str(run_dir/'state'), LAB_RUN_DIR=str(run_dir),
               LAB_TRACE=trace.get(), LAB_TABS=str(count), PYTHONFAULTHANDLER='1',
               G_ENABLE_DIAGNOSTIC='1', G_MESSAGES_DEBUG='all')
    if trace.get() == 'detailed':
        env['WAYLAND_DEBUG'] = 'client' if backend.get() == 'wayland' else ''
    if env.get('LAB_SSH_HOST'):
        seed_env = env.copy()
        seed_env.pop('WAYLAND_DEBUG', None)
        seed_env.pop('G_MESSAGES_DEBUG', None)
        seeded = subprocess.run(['python3', '/opt/lab/seed_profile.py'], env=seed_env,
                                capture_output=True, text=True, timeout=15)
        (run_dir/'profile.log').write_text(seeded.stdout + seeded.stderr)
        if seeded.returncode:
            status.set('No se pudo preparar el perfil SSH. Consulta profile.log en '+run_dir.name)
            return
    command = ['python3', '-X', 'faulthandler', '/opt/lab/launcher.py']
    if debugger.get():
        command = ['gdb', '-q', '-batch', '-ex', 'set pagination off', '-ex', 'set confirm off',
                   '-ex', 'set disable-randomization off',
                   '-ex', 'set print thread-events off', '-ex', 'run', '-ex', 'thread apply all bt full',
                   '-ex', 'info sharedlibrary', '--args', *command]
    metadata = dict(backend=backend.get(), trace=trace.get(), gdb=debugger.get(), tabs=count,
                    commit=Path('/opt/termia/BASE_COMMIT').read_text().strip(),
                    source_sha256=source_fingerprint(), source_mode='live-bind',
                    ssh_fixture=bool(env.get('LAB_SSH_HOST')))
    (run_dir/'run.json').write_text(json.dumps(metadata, indent=2)+'\n')
    stream = (run_dir/'console.log').open('w')
    child = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    finished = False
    (ROOT/'latest.txt').write_text(run_dir.name+'\n')
    status.set('Activo: '+run_dir.name)


def mark():
    if run_dir:
        with (run_dir/'markers.jsonl').open('a') as out:
            out.write(json.dumps(dict(time_ns=time.time_ns(), label='Marca manual'))+'\n')
        status.set('Marca registrada: '+run_dir.name)


def poll():
    global finished
    if child is not None and child.poll() is not None and not finished:
        finished = True
        with (run_dir/'console.log').open(errors='replace') as log:
            fatal = next((line.strip() for line in log
                          if 'received signal SIG' in line or 'Fatal Python error:' in line), None)
        if fatal:
            status.set('Fallo capturado: '+fatal+' — '+run_dir.name)
        else:
            status.set('Terminado (código '+str(child.returncode)+'). Logs: '+run_dir.name)
    app.after(500, poll)


row = tk.Frame(app)
row.pack(fill='x')
tk.Label(row, text='Backend:').pack(side='left')
tk.OptionMenu(row, backend, 'wayland', 'x11').pack(side='left')
tk.Label(row, text='Trazas:').pack(side='left')
tk.OptionMenu(row, trace, 'detailed', 'minimal').pack(side='left')
tk.Checkbutton(row, text='GDB', variable=debugger).pack(side='left')
tk.Label(row, text='Pestañas:').pack(side='left')
tk.Spinbox(row, from_=1, to=40, width=4, textvariable=tabs).pack(side='left')
tk.Button(row, text='Iniciar / nueva prueba', command=launch).pack(side='left', padx=12)
tk.Button(row, text='Marcar momento', command=mark).pack(side='left')
tk.Label(app, textvariable=status, anchor='w').pack(fill='x')
tk.Label(app, text='Arrastra pestañas en la ventana Weston. Al abortar, pulsa Iniciar para repetir. Cierra Termia normalmente entre pruebas.', anchor='w').pack(fill='x')
app.after(1500, launch)
app.after(500, poll)
app.mainloop()
