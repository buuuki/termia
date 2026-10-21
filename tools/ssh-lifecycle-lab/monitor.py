import json
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent
observations = root/'observations'
observations.mkdir(exist_ok=True)
stop = root/'monitor.stop'
while not stop.exists():
    result = subprocess.run(['sg', 'docker', '-c', 'docker --host=unix:///var/run/docker.sock exec termia-ssh-lifecycle-lab python3 /opt/observe.py'], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    json.loads(result.stdout)
    temporary = observations/'status.tmp'
    temporary.write_text(result.stdout)
    temporary.replace(observations/'status.json')
    time.sleep(.2)
