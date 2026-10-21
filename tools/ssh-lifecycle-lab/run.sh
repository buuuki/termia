#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
lab="$PWD/tools/ssh-lifecycle-lab"
docker_local() { docker --host=unix:///var/run/docker.sock "$@"; }
docker_local info >/dev/null
if [[ ! -f "$lab/synthetic" ]]; then
    ssh-keygen -q -t ed25519 -N '' -C termia-synthetic-lab -f "$lab/synthetic"
fi
docker_local build -q -t termia-ssh-lifecycle-lab:local "$lab"
python3 "$lab/prepare_client_context.py"
docker_local build -q -t termia-lifecycle-client:local "$lab/client-context"
if ! docker_local network inspect termia-lifecycle-internal >/dev/null 2>&1; then
    docker_local network create --internal --label termia.purpose=lifecycle-tests termia-lifecycle-internal >/dev/null
fi
if docker_local inspect termia-ssh-lifecycle-lab >/dev/null 2>&1; then
    [[ "$(docker_local inspect -f '{{index .Config.Labels "termia.purpose"}}' termia-ssh-lifecycle-lab)" == lifecycle-tests ]]
    docker_local start termia-ssh-lifecycle-lab >/dev/null
else
    docker_local run -d --init --name termia-ssh-lifecycle-lab --label termia.purpose=lifecycle-tests --network termia-lifecycle-internal termia-ssh-lifecycle-lab:local >/dev/null
fi
if [[ "$(docker_local inspect -f '{{with index .NetworkSettings.Networks "termia-lifecycle-internal"}}yes{{end}}' termia-ssh-lifecycle-lab)" != yes ]]; then
    docker_local network connect termia-lifecycle-internal termia-ssh-lifecycle-lab
fi
docker_local cp "$lab/observe.py" termia-ssh-lifecycle-lab:/opt/observe.py
mkdir -p "$lab/observations"
rm -f "$lab/monitor.stop"
python3 "$lab/monitor.py" &
monitor_pid=$!
cleanup() {
    touch "$lab/monitor.stop"
    wait "$monitor_pid" || true
    docker_local stop termia-ssh-lifecycle-lab >/dev/null
}
trap cleanup EXIT
for attempt in {1..50}; do
    if python3 -c 'import json,time,sys; d=json.load(open(sys.argv[1])); assert time.time()-d["time"]<2' "$lab/observations/status.json" 2>/dev/null; then
        break
    fi
    sleep .1
done
client_command=(python3 tools/ssh-lifecycle-lab/run_probe.py "$@")
if [[ "${1:-}" == --memory ]]; then
    shift
    client_command=(env TERMIA_LAB_MEMORY=1 python3 tools/ssh-lifecycle-lab/run_probe.py "$@")
elif [[ "${1:-}" == --investigate ]]; then
    shift
    client_command=(env TERMIA_LAB_RETENTION=1 python3 tools/ssh-lifecycle-lab/run_probe.py "$@")
elif [[ "${1:-}" == --diagnose-focus ]]; then
    shift
    client_command=(env TERMIA_LAB_FOCUS=1 TERMIA_LAB_VALGRIND=1 python3 tools/ssh-lifecycle-lab/run_probe.py "$@")
elif [[ "${1:-}" == --valgrind ]]; then
    shift
    client_command=(env TERMIA_LAB_VALGRIND=1 python3 tools/ssh-lifecycle-lab/run_probe.py "$@")
elif [[ "${1:-}" == --launch ]]; then
    shift
    client_command=(env TERMIA_LAB_LAUNCH=1 python3 tools/ssh-lifecycle-lab/run_probe.py "$@")
fi
docker_local run --rm --init --network termia-lifecycle-internal --read-only \
    --tmpfs /tmp:rw,nosuid,size=512m --cap-drop ALL --security-opt no-new-privileges \
    --mount "type=bind,src=$lab/observations,dst=/observations,readonly" \
    termia-lifecycle-client:local "${client_command[@]}"
