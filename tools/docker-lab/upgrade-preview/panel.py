import os
import subprocess
import time
import tkinter as tk
from pathlib import Path

root=tk.Tk()
root.title('Laboratorio #428 — beta.3 → beta.4, sin GtkSourceView 5')
root.geometry('1420x235+20+745')
child=None
status=tk.StringVar(value='Preparado: beta.3 instalada. Usa datos sintéticos.')
password=Path('/home/lab/.lab-password').read_text().strip()

def launch(mode):
    global child
    if child and child.poll() is None:
        status.set('Cierra Termia y espera antes de iniciar otra prueba.')
        return
    stamp=str(time.time_ns())
    directory=Path('/tmp/upgrade-evidence')/stamp
    directory.mkdir()
    env=os.environ.copy()
    env.update(TERMIA_CONFIG_DIR=str(directory/'config'),TERMIA_STATE_DIR=str(directory/'state'),
               PYTHONUNBUFFERED='1')
    log=(directory/'console.log').open('w')
    child=subprocess.Popen(['python3','/opt/upgrade-lab/launch.py',mode],env=env,stdout=log,stderr=subprocess.STDOUT)
    log.close()
    status.set('Modo '+mode+' — abre menú → Acerca de → Buscar actualizaciones. Registro: '+stamp)

def reset():
    if child and child.poll() is None:
        status.set('Cierra Termia antes de restaurar la baseline.')
        return
    subprocess.Popen(['xterm','-T','Restaurar beta.3 sin GtkSourceView','-e','python3','/opt/upgrade-lab/reset.py'])
    status.set('Restauración en terminal: escribe la contraseña del panel y espera a que termine.')

def terminal():
    subprocess.Popen(['xterm','-T','Terminal del contenedor — dependencias manuales'])

row=tk.Frame(root)
row.pack(fill='x')
for label,mode in [('1. Git beta.3 original','original'),('2. Git beta.3 + actualizador propuesto','proposed'),
                   ('3. Paquete .deb + actualizador propuesto','debian'),('Reiniciar desde código actualizado','restart')]:
    tk.Button(row,text=label,command=lambda value=mode:launch(value)).pack(side='left',padx=4,pady=5)
row=tk.Frame(root)
row.pack(fill='x')
tk.Button(row,text='Restaurar beta.3 y quitar GtkSourceView',command=reset).pack(side='left',padx=4)
tk.Button(row,text='Abrir terminal para comandos manuales',command=terminal).pack(side='left',padx=4)
tk.Label(root,text='Contraseña SINTÉTICA del usuario lab (sudo/polkit): '+password,anchor='w').pack(fill='x')
tk.Label(root,text='El modo 2/3 carga SOLO el actualizador propuesto sobre beta.3; no es una beta.3 oficial modificada. El destino beta.4 usa fixtures locales verificadas.',anchor='w').pack(fill='x')
tk.Label(root,text='En el modo original, actualizar Git no instala GtkSource: reiniciar debe reproducir el fallo. Restaura la baseline antes de probar la corrección.',anchor='w').pack(fill='x')
tk.Label(root,textvariable=status,anchor='w',wraplength=1350).pack(fill='x')
root.mainloop()
