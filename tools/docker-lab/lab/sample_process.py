"""Read metrics for the active laboratory process, without attaching a debugger."""
import json
import time
from pathlib import Path

root = Path('/evidence')
run = (root / 'latest.txt').read_text().strip()
events = root / run / 'interactions.jsonl'
with events.open() as stream:
    first = json.loads(next(stream))
pid = first['pid']
proc = Path('/proc') / str(pid)
before = (proc / 'stat').read_text().rpartition(')')[2].split()[19]
metrics = {}
for row in (proc / 'smaps_rollup').read_text().splitlines():
    fields = row.split()
    if len(fields) == 3 and fields[2] == 'kB':
        metrics[fields[0].rstrip(':')] = int(fields[1])
after = (proc / 'stat').read_text().rpartition(')')[2].split()[19]
args = (proc / 'cmdline').read_bytes().split(b'\0')
if before != after or b'/opt/lab/launcher.py' not in args:
    raise RuntimeError('La identidad del proceso ha cambiado')
result = dict(time=time.time(), run=run, pid=pid, birth=before,
              rss_kib=metrics.get('Rss'), pss_kib=metrics.get('Pss'),
              private_kib=metrics.get('Private_Clean', 0) + metrics.get('Private_Dirty', 0),
              fds=len(list((proc / 'fd').iterdir())),
              threads=len(list((proc / 'task').iterdir())))
print(json.dumps(result))
