"""Visible VM-only trials. Uses installed Termia and real sudo/pkexec."""
import hashlib
import io
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT=Path.home()/'termia-lab-evidence'
ROOT.mkdir(exist_ok=True)
STATE=ROOT/'state.json'
FIXTURES=Path('/mnt/termia-fixtures')
OLD='0.6.0~beta.3-1'
NEW='0.6.0~beta.4-1'


def version():
    return subprocess.check_output(['dpkg-query','-W','-f=${Version}','termia'],text=True).strip()


def write_state(**fields):
    value=json.loads(STATE.read_text()) if STATE.exists() else {}
    value.update(fields,updated_at=time.time(),installed=version())
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(STATE)
    if fields.get('running') is False:
        (ROOT/(value['phase']+'.json')).write_text(json.dumps(value,indent=2)+'\n')


def profile_hashes():
    folder=Path.home()/'.config/termia'
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.json')}


def prepare_debian():
    from termia.update_service import ReleaseClient,select_release
    from termia.update_installers import DebianInstaller
    metadata=json.loads((FIXTURES/'candidate.json').read_text())
    url='https://github.com/buuuki/termia/releases/download/'+metadata['tag']+'/'+metadata['filename']
    class LocalFixture:
        def open(self,request,timeout):
            if request.full_url!=url:
                raise RuntimeError('Unexpected download URL')
            return io.BytesIO((FIXTURES/'termia-beta4-candidate.deb').read_bytes())
    client=ReleaseClient(opener=LocalFixture())
    release=select_release([{'tag_name':metadata['tag'],'prerelease':True,'draft':False,'assets':[
        {'name':metadata['filename'],'digest':'sha256:'+metadata['sha256'],
         'size':metadata['size'],'browser_download_url':url}]}],'0.6.0-beta.3')
    assert release is not None and release.asset is not None
    installer=DebianInstaller(client)
    assert not installer.availability('0.6.0-beta.3',threading.Event())
    prepared=Path('/tmp/termia-visible-prepared')
    prepared.mkdir(exist_ok=True)
    package=prepared/'termia.deb'
    if package.exists(): package.unlink()
    package=installer.prepare(release,prepared,threading.Event())
    (ROOT/'prepared.json').write_text(json.dumps({'path':str(package),'sha256':metadata['sha256']}))
    return installer,release,package


def run(stage):
    before=version()
    hashes=profile_hashes()
    print('LABORATORIO VISIBLE — '+stage,flush=True)
    print('Paquete instalado antes:',before,flush=True)
    print('Esta VM y sus datos son sintéticos. No es una publicación oficial.',flush=True)
    write_state(running=True,passed=False,phase=stage,message='Ejecutando '+stage)
    if stage.startswith('source-'):
        assert before==OLD
        subprocess.run(['sudo','-k'],check=True)
        print('Ejecutando el setup real del código candidato. Esperando sudo...',flush=True)
        cancelled=False
        result=None
        try:
            result=subprocess.run(['bash',str(Path.home()/'candidate-source/scripts/termia-setup.sh'),'install'])
            cancelled=result.returncode in (-2,130)
        except KeyboardInterrupt:
            cancelled=True
            print('\nCancelación de terminal recibida.',flush=True)
        assert profile_hashes()==hashes,'Setup modified profile data'
        assert version()==OLD,'Source setup changed installed Debian package'
        available=subprocess.run([sys.executable,'-c',
            'import gi; gi.require_version("GtkSource","5"); from gi.repository import GtkSource'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
        if stage=='source-cancel':
            assert cancelled and not available,'Cancellation did not preserve missing-dependency baseline'
            message='PASS: sudo cancelado; beta.3 y datos intactos; GtkSource sigue ausente.'
        else:
            assert not cancelled and result.returncode==0 and available,'Setup did not install the required dependency'
            message='PASS: setup autorizado e instalado GtkSource; beta.3 y datos conservados.'
    elif stage=='debian-prepare':
        assert before==OLD
        prepare_debian()
        assert profile_hashes()==hashes
        message='PASS: instalador beta.3 verificó digest, tamaño, identidad, versión y arquitectura del candidato.'
    elif stage in ('debian-cancel','debian-accept'):
        assert before==OLD
        installer,release,package=prepare_debian()
        subprocess.run(['pkcheck','--revoke-temp'],check=False)
        print('Invocando DebianInstaller.apply() real: pkexec → apt-get.',flush=True)
        print('Debe aparecer la ventana del agente de autenticación del escritorio.',flush=True)
        from termia.update_service import UpdateError
        denied=False
        try:
            installer.apply(package,release)
        except UpdateError:
            denied=True
        if stage=='debian-cancel':
            assert denied and version()==OLD
            assert profile_hashes()==hashes
            message='PASS: polkit cancelado; paquete beta.3 y datos intactos.'
        else:
            assert not denied and version()==NEW
            assert profile_hashes()==hashes
            message='PASS: polkit autorizado; paquete beta.4 instalado; datos conservados.'
    elif stage=='verify':
        assert before==NEW
        code='''from pathlib import Path
import termia
from termia.constants import DATA_FILE
from termia.stores import ConnectionStore
assert termia.__version__=="0.6.0-beta.4"
s=ConnectionStore(DATA_FILE)
try:
 assert any(x.name=="Servidor sintético" for x in s.data.servers)
 assert any(x.name=="Grupo sintético" for x in s.data.groups)
 assert any(x.name=="Snippet sintético" for x in s.data.snippets)
 assert any(x.content=="Nota sintética conservada durante la actualización." for x in s.data.notes)
 s.save_notes()
 assert list(DATA_FILE.parent.glob("notes.json.backup-*"))
 print("PASS: beta.4 real importa, conserva conexiones/snippets/notas y respalda Notes antiguo.")
finally:
 s.close()
'''
        subprocess.run([sys.executable,'-c',code],check=True)
        message='PASS: beta.4 arrancable y datos sintéticos preservados; copia de Notes creada.'
    else:
        raise ValueError('Unknown trial')
    write_state(running=False,phase=stage,passed=True,message=message)
    print(message,flush=True)


if __name__=='__main__':
    with (ROOT/'worker.lock').open('a') as lock:
        # A second process must not overwrite the active worker's result.
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if not (ROOT/'observer-ready').exists():
                raise RuntimeError('Observer has not enabled trials')
            run(sys.argv[1])
        except BaseException as error:
            write_state(running=False,passed=False,phase=sys.argv[1],
                        message='FALLO: '+type(error).__name__+': '+str(error))
            raise
