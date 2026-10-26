"""Reset only this container's disposable source fixture."""
import argparse
import shutil
import subprocess
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--source-only', action='store_true')
a=p.parse_args()
root=Path('/home/lab/source')
if not a.source_only:
    print('REINICIO DEL LABORATORIO: elimina GtkSourceView y restaura beta.3. Solo este contenedor.',flush=True)
    subprocess.run(['sudo','apt-get','purge','-y','gir1.2-gtksource-5','libgtksourceview-5-0','libgtksourceview-5-common'],check=True)
    subprocess.run(['sudo','apt-get','install','-y','--allow-downgrades','--no-remove','/opt/fixtures/beta3.deb'],check=True)
if root.exists():
    shutil.rmtree(root)
subprocess.run(['git','clone','--no-checkout','/opt/fixtures/releases.bundle',str(root)],check=True)
subprocess.run(['git','-C',str(root),'switch','-c','main','v0.6.0-beta.3'],check=True)
print('Baseline preparada: Git main en beta.3. Los perfiles de cada ejecución son sintéticos y separados.',flush=True)
if not a.source_only:
    input('Pulsa Enter para cerrar.')
