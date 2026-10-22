import os
import signal
import subprocess
import sys
import time
from pathlib import Path

token = sys.argv[1]
root = Path('/tmp') / ('termia-job-' + token)
root.mkdir()
child = subprocess.Popen(['sleep', '300'])
(root / 'pids').write_text(f'{os.getpid()} {child.pid}')

def finish(_signum, _frame):
    child.terminate()
    child.wait(timeout=3)
    raise SystemExit(0)

for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, finish)
try:
    while True:
        time.sleep(.1)
finally:
    if child.poll() is None:
        child.terminate()
        child.wait(timeout=3)
