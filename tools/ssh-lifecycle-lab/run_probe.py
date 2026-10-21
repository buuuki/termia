import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sandbox_runner', 'scripts/run_sandbox_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
original = subprocess.call
def launch(command, **kwargs):
    kwargs['env']['PYTHONFAULTHANDLER'] = '1'
    script = ('launch_probe.py' if os.environ.get('TERMIA_LAB_LAUNCH') == '1' else
              'focus_probe.py' if os.environ.get('TERMIA_LAB_FOCUS') == '1' else
              'retention_probe.py' if os.environ.get('TERMIA_LAB_RETENTION') == '1' else
              'memory_probe.py' if os.environ.get('TERMIA_LAB_MEMORY') == '1' else 'probe.py')
    command = [sys.executable, str(root/script), *sys.argv[1:]]
    if os.environ.get('TERMIA_LAB_VALGRIND') == '1':
        command = ['valgrind', '--tool=memcheck', '--num-callers=30',
                   '--leak-check=no', '--track-origins=yes', *command]
    return original(command, **kwargs)
with patch.object(runner.subprocess, 'call', side_effect=launch):
    raise SystemExit(runner.run_tests())
