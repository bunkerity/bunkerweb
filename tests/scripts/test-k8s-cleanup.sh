#!/bin/bash
# Removing the delete deadline must hang this check; skipping recovery must leave the PVC behind.
set -euo pipefail

repo="$(cd "$(dirname "$0")/../.." && pwd)"
utils="${1:-$repo/tests/scripts/utils.sh}"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

# Load only lifecycle functions: sourcing utils.sh would install its host-cleanup EXIT trap.
awk '/^function / {copy = ($2 ~ /^(k8s_|cleanup_stack|log\()/)} copy {print}' "$utils" > "$tmp_dir/functions.sh"
cat > "$tmp_dir/kubectl" <<'PY'
#!/usr/bin/env python3
import os
import pathlib
import sys
import time

args = [arg for arg in sys.argv[1:] if not arg.startswith('--request-timeout=')]
state = pathlib.Path(os.environ['K8S_STATE'])
mode = os.environ['K8S_MODE']
with (state / 'calls').open('a') as calls:
    calls.write(' '.join(args) + '\n')

if args[:2] == ['delete', '-f']:
    if mode in ('vanished', 'vanished-before-discovery') and (state / 'delete-requested').exists():
        sys.exit(0)
    (state / 'delete-requested').touch()
    if mode == 'normal' or ((state / 'pvc-gone').exists() and mode != 'retry-failure'):
        sys.exit(0)
    print('service "svc-bunkerweb-db-nodeport" deleted', flush=True)
    if mode == 'wedged' or not any(arg.startswith('--timeout=') for arg in args):
        time.sleep(20)
    sys.exit(1)
if args[:2] == ['get', '-f']:
    if mode not in ('no-namespace', 'vanished-before-discovery', 'vanished-before-discovery-failure'):
        print('bunkerweb-db')
elif args[:2] == ['get', 'namespace']:
    if args[2] != 'bunkerweb-db':
        pass
    elif '-o' in args and args[args.index('-o') + 1] == 'name':
        print('namespace/bunkerweb-db')
    elif mode == 'active':
        if any(arg.startswith('go-template=') for arg in args):
            print('active')
    elif mode != 'vanished':
        print('terminating')
elif args[:2] == ['delete', 'pod']:
    if mode == 'pod-failure':
        sys.exit(1)
    (state / 'pods-gone').touch()
elif args[:2] == ['get', 'pvc']:
    print('pvc-bunkerweb-db')
elif args[:2] == ['patch', 'pvc']:
    if not (state / 'pods-gone').exists() or mode == 'patch-failure':
        sys.exit(1)
    (state / 'pvc-gone').touch()
elif args[:2] == ['get', 'pods']:
    if 'bunkerweb-db' in args and mode != 'orphan' and not (state / 'pods-gone').exists():
        print('bunkerweb-db-held')
elif args[0] == 'get':
    if mode == 'api-failure':
        sys.exit(1)
else:
    print(f'Unexpected kubectl call: {args}', file=sys.stderr)
    sys.exit(2)
PY
chmod +x "$tmp_dir/kubectl"
# Exercise the real watchdog without spending its production 150 seconds per check.
timeout_bin="$(command -v timeout)"
export K8S_TIMEOUT_BIN="$timeout_bin"
cat > "$tmp_dir/timeout" <<'SH'
#!/bin/bash
if [ "$1" == --kill-after=5s ] && [ "$2" == 150s ]; then
    shift 2
    exec "$K8S_TIMEOUT_BIN" --kill-after=0.2s 0.5s "$@"
fi
exec "$K8S_TIMEOUT_BIN" "$@"
SH
chmod +x "$tmp_dir/timeout"
cat > "$tmp_dir/run.sh" <<'SH'
#!/bin/bash
set -u
source "$1/functions.sh"
integration=Kubernetes
type=core
trapped=false
redis_cli() { if [ "$2" == database ]; then echo mysql; else echo 0; fi; }
docker() { return 0; }
cd "$1" || exit 1
cleanup_stack 0
SH

export PATH="$tmp_dir:$PATH"
for mode in normal stuck active pod-failure patch-failure no-namespace api-failure retry-failure wedged orphan vanished vanished-before-discovery vanished-before-discovery-failure ; do
    export K8S_MODE="$mode" K8S_STATE="$tmp_dir/$mode"
    mkdir "$K8S_STATE"
    result=0
    timeout --kill-after=1s 3s bash "$tmp_dir/run.sh" "$tmp_dir" || result=$?
    case "$mode" in
        normal|vanished|vanished-before-discovery)
            [ "$result" -eq 0 ] && [ ! -f "$K8S_STATE/pods-gone" ] || {
                echo "FAIL: ordinary cleanup changed or forced recovery"; exit 1;
            }
            ;;
        stuck|wedged|orphan)
            [ "$result" -eq 0 ] && [ -f "$K8S_STATE/pvc-gone" ] || {
                echo "FAIL: stuck cleanup returned $result (124 means unbounded delete)"; exit 1;
            }
            ;;
        retry-failure)
            [ "$result" -eq 1 ] && [ -f "$K8S_STATE/pvc-gone" ] || {
                echo "FAIL: incomplete namespace cleanup must fail even after PVC recovery ($result)"; exit 1;
            }
            ;;
        *)
            [ "$result" -eq 1 ] && [ ! -f "$K8S_STATE/pvc-gone" ] || {
                echo "FAIL: $mode must fail cleanup without clearing PVC finalizers ($result)"; exit 1;
            }
            ;;
    esac
    if [[ "$mode" == vanished-before-discovery* ]] ; then
        grep -q -- ' --ignore-not-found --wait=true --timeout=60s$' "$K8S_STATE/calls" && [ ! -f "$K8S_STATE/pods-gone" ] || {
            echo "FAIL: $mode must retry bounded manifest deletion without forcing recovery"; exit 1;
        }
    fi
    echo "PASS: $mode cleanup"
done
