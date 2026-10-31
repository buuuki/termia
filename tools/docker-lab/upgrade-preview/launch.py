"""Local fixture transports; production updater logic is otherwise unchanged."""
import argparse
import hashlib
import importlib
import io
import json
import os
import subprocess
import sys
import types
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('mode',choices=['original','proposed','debian','restart'])
args=parser.parse_args()
source=Path('/home/lab/source')
if args.mode=='restart':
    os.execv(sys.executable,[sys.executable,str(source/'run_termia.py')])
if args.mode=='debian':
    # Use the actual distribution-owned package to exercise installation detection.
    sys.path.insert(0,'/usr/lib/python3/dist-packages')
else:
    sys.path.insert(0,str(source/'src'))
import termia
from termia import app as old_app

old_version=termia.__version__
old_module=Path(old_app.__file__)
if args.mode=='original':
    package='termia'
else:
    package='reviewtermia'
    review=types.ModuleType(package)
    review.__path__=['/opt/review/src/termia']
    review.__version__=old_version
    sys.modules[package]=review
service=importlib.import_module(package+'.update_service')
installers=importlib.import_module(package+'.update_installers')
controller_module=importlib.import_module(package+'.update_controller')
view=importlib.import_module(package+'.update_view')
translations=importlib.import_module(package+'.i18n')
package_path=Path('/opt/fixtures/termia_0.6.0.beta.4-1_all.deb')
asset_name=package_path.name
url=service.REPOSITORY+'/releases/download/v0.6.0-beta.4/'+asset_name
items=[{'tag_name':'v0.6.0-beta.4','draft':False,'prerelease':True,'assets':[
    {'name':asset_name,'size':package_path.stat().st_size,
     'digest':'sha256:'+hashlib.sha256(package_path.read_bytes()).hexdigest(),
     'browser_download_url':url}]}]
class FixtureOpener:
    def open(self,request,timeout):
        if request.full_url.startswith(service.API+'/releases?'):
            return io.BytesIO(json.dumps(items).encode())
        if request.full_url==url:
            return package_path.open('rb')
        raise RuntimeError('Unexpected fixture URL')
client=service.ReleaseClient(opener=FixtureOpener())
real_command=installers.command

def fixture_command(command,cancel,**kwargs):
    command=list(command)
    if command[0]=='/usr/bin/git' and 'fetch' in command:
        command=[('/opt/fixtures/releases.bundle' if c==service.REPOSITORY+'.git' else
                  'protocol.file.allow=always' if c=='protocol.file.allow=never' else c) for c in command]
    return real_command(command,cancel,**kwargs)

def detect(current,client,cancel):
    if args.mode=='debian':
        return installers.detect_installation(current,client,cancel,module=old_module,run=fixture_command)
    adapter=installers.GitInstaller(source,current,run=fixture_command)
    return installers.Installation(adapter,adapter.availability(current,cancel))

def factory(current,dispatch,notify):
    return controller_module.UpdateController(old_version,dispatch,notify,client=client,detect=detect)
view.UpdateDialog.__init__.__defaults__=(factory,)
if args.mode=='original':
    # Presentation-only adjustment: preserve the historical update behavior.
    original_init=view.UpdateDialog.__init__

    def selectable_init(self,*arguments,**keywords):
        original_init(self,*arguments,**keywords)
        self.status.set_selectable(True)
        self.set_focus(self.check_button)
        content=self.get_child()
        for side in ('top','bottom','start','end'):
            getattr(content,'set_margin_'+side)(16)

    view.UpdateDialog.__init__=selectable_init
attach=view.attach_updates

def attach_fixture(about,translate):
    attach(about,lambda key:translations.translate_key(key,'es'))
view.attach_updates=attach_fixture
sys.modules['termia.update_view']=view
# Register an actual polkit terminal agent for this app process and its descendants.
# The terminal is part of the isolated Docker desktop, never the host session.
agent=subprocess.Popen(['/usr/bin/xterm','-T','Autorización polkit del laboratorio — escribe la contraseña del panel',
                         '-geometry','90x12+380+740','-e','/usr/bin/pkttyagent','--process',str(os.getpid())])
print(json.dumps({'mode':args.mode,'version':old_version,'updater':package,
                  'transport':'local fixture: official beta.4 bytes and official Git tags',
                  'root':str(source) if args.mode!='debian' else str(old_module)},ensure_ascii=False),flush=True)
try:
    old_app.main([])
finally:
    agent.terminate()
    try: agent.wait(timeout=3)
    except subprocess.TimeoutExpired: agent.kill()
