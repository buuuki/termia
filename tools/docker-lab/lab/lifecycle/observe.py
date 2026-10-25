import json
import time
from pathlib import Path

processes = []
for path in Path('/proc').iterdir():
    if not path.name.isdigit():
        continue
    try:
        fields = (path/'stat').read_text().rpartition(')')[2].split()
        args = (path/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        uid = (path/'status').read_text().split('Uid:')[1].split()[0]
        if uid == '1001' or 'remote_job.py' in args or fields[0] == 'Z':
            processes.append(dict(pid=int(path.name), ppid=int(fields[1]), state=fields[0], birth=fields[19], args=args))
    except (OSError, IndexError):
        pass
jobs = {}
for path in Path('/tmp').glob('termia-job-*/pids'):
    try:
        jobs[path.parent.name.removeprefix('termia-job-')] = [int(p) for p in path.read_text().split()]
    except OSError:
        pass
sockets = []
for name in ('tcp', 'tcp6'):
    for row in (Path('/proc/net')/name).read_text().splitlines()[1:]:
        fields = row.split()
        if fields[1].endswith(':0016') and fields[3] == '01':
            sockets.append(fields[1:4])
print(json.dumps(dict(time=time.time(), processes=processes, jobs=jobs, established=len(sockets))))
