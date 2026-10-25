"""VM desktop control panel. Trials are gated until the observer is ready."""
import json
from pathlib import Path
import subprocess
import tkinter as tk

ROOT=Path.home()/'termia-lab-evidence'
ROOT.mkdir(exist_ok=True)
COMMAND=ROOT/'command.json'
ALLOW=ROOT/'observer-ready'
app=tk.Tk()
app.title('Termia — pruebas observables')
app.geometry('950x850+900+80')
status=tk.StringVar(value='Preparado. Pruebas en pausa hasta que confirmes que ves este escritorio.')
installed=tk.StringVar(value='Consultando paquete instalado...')
buttons=[]
STAGES=('source-cancel','source-accept','debian-prepare','debian-cancel','debian-accept','verify')
PASSWORD=Path('/opt/termia-lab/password').read_text().strip()


def show_termia():
    with (ROOT/'termia-console.log').open('a') as output:
        subprocess.Popen(['/usr/bin/termia'],stdout=output,stderr=subprocess.STDOUT)


def start(stage):
    if stage not in STAGES:
        raise ValueError('Unknown trial')
    if not ALLOW.exists():
        status.set('En espera: abre el visor y ejecuta vm.py ready desde el anfitrión.')
        return
    pending=ROOT/'state.json'
    if pending.exists() and json.loads(pending.read_text()).get('running'):
        return
    pending.write_text(json.dumps({'running':True,'passed':False,'phase':stage,'message':'Iniciando '+stage}))
    with (ROOT/(stage+'.log')).open('a') as output:
        # Keep the actual sudo prompt and setup output visible in a real PTY.
        subprocess.Popen(['xterm','-T','Prueba visible: '+stage,'-geometry','110x26+180+160',
            '-hold','-e','script','--quiet','--return','--flush','--command',
            'python3 /opt/termia-lab/worker.py '+stage,str(ROOT/(stage+'.typescript'))],
            stdout=output,stderr=subprocess.STDOUT)
    status.set('Iniciando '+stage)


def poll():
    active=False
    state=ROOT/'state.json'
    if state.exists():
        try:
            data=json.loads(state.read_text())
            status.set(data.get('message',''))
            installed.set('Paquete instalado: '+data.get('installed',''))
            active=data.get('running',False)
        except (OSError,ValueError):
            pass
    else:
        installed.set('Paquete instalado: '+subprocess.check_output(
            ['dpkg-query','-W','-f=${Version}','termia'],text=True).strip())
    for button in buttons:
        button.configure(state='normal' if ALLOW.exists() and not active else 'disabled')
    if COMMAND.exists() and not active:
        try:
            action=json.loads(COMMAND.read_text())['action']
            COMMAND.unlink()
            if action=='show': show_termia()
            else: start(action)
        except (OSError,ValueError,KeyError):
            pass
    app.after(400,poll)


tk.Label(app,text='Laboratorio de actualización — Ubuntu 24.04',font=('Sans',14,'bold')).pack(padx=16,pady=12)
tk.Label(app,textvariable=installed,font=('Sans',12)).pack(pady=6)
tk.Label(app,text='Usuario de pruebas: lab\nClave sintética de esta VM: '+PASSWORD,justify='left').pack(pady=6)
tk.Label(app,text='La beta.4 es un candidato local de ensayo. No se publica ninguna release.',wraplength=570).pack(pady=6)
tk.Button(app,text='Ver Termia instalada',command=show_termia).pack(fill='x',padx=22,pady=4)
for text,stage in (
    ('1. Setup por código: cancelar sudo','source-cancel'),
    ('2. Setup por código: aceptar sudo','source-accept'),
    ('3. Verificar paquete candidato con el actualizador','debian-prepare'),
    ('4. Actualización Debian: cancelar polkit','debian-cancel'),
    ('5. Actualización Debian: autorizar polkit','debian-accept'),
    ('6. Verificar beta.4 y conservación de datos','verify'),
):
    button=tk.Button(app,text=text,command=lambda value=stage:start(value))
    button.pack(fill='x',padx=22,pady=3)
    buttons.append(button)
tk.Label(app,textvariable=status,wraplength=570,justify='left',anchor='w').pack(fill='x',padx=22,pady=12)
app.after(400,poll)
app.mainloop()
