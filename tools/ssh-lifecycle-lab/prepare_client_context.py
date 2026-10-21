import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
context = root/'client-context'
if context.exists():
    shutil.rmtree(context)
context.mkdir()
for name in subprocess.check_output(['git', 'ls-files', 'run_termia.py', 'src', 'tests', 'scripts'], text=True).splitlines():
    target = context/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(name, target)
(context/'lab').mkdir(exist_ok=True)
for name in ('probe.py', 'memory_probe.py', 'retention_probe.py', 'focus_probe.py', 'launch_probe.py', 'run_probe.py', 'synthetic', 'synthetic.pub'):
    shutil.copy2(root/name, context/'lab'/name)
shutil.copy2(root/'Dockerfile.client', context/'Dockerfile')
