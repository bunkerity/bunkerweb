#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"

if redis_cli ping | grep -q "PONG" ; then
    log "WAIT" "ℹ️ " "💽 Redis server is healthy ✅"
else
    log "WAIT" "❌" "💽 Redis server is not healthy"
    exit 1
fi

timeout=$(redis_cli get timeout)
# shellcheck disable=SC2181
if [ $? -ne 0 ] || [ -z "$timeout" ] ; then
    log "WAIT" "❌" "💽 Failed to get timeout from redis server"
    exit 1
fi

log "WAIT" "ℹ️ " "⏳ Waiting for stack to be healthy ..."
i=0
if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Docker" ] ; then
    # A Docker example names its containers however its documentation reads best, so wait
    # on what the compose project actually started rather than on a fixed list: every
    # container running, and every container that declares a healthcheck healthy.
    example_stack="$(cat /tmp/example_stack.txt)"
    while [ $i -lt "$timeout" ] ; do
        healthy="true"
        for container in $(docker compose -f "$example_stack" ps -q 2>/dev/null) ; do
            state="$(docker inspect --format '{{.State.Status}}' "$container" 2>/dev/null)"
            health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null)"
            if [ "$state" != "running" ] || { [ "$health" != "none" ] && [ "$health" != "healthy" ] ; } ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            log "WAIT" "ℹ️ " "📕 Example stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge "$timeout" ] ; then
        log "WAIT" "❌" "📕 Example stack is not healthy after $timeout seconds"
        docker compose -f "$example_stack" ps
        exit 1
    fi

    # Healthy containers are not a configured BunkerWeb: the scheduler still has to push,
    # and an example brings its own database, so the push-configs count is out of reach
    # here. Wait for the instance to say it is serving instead.
    while [ $i -lt "$timeout" ] ; do
        if docker compose -f "$example_stack" logs bunkerweb 2>/dev/null | grep -q "BunkerWeb is ready" ; then
            log "WAIT" "ℹ️ " "📕 Example stack is serving its configuration ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge "$timeout" ] ; then
        log "WAIT" "❌" "📕 Example stack never reported BunkerWeb ready after $timeout seconds"
        exit 1
    fi
elif [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
    while [ $i -lt "$timeout" ] ; do
        containers=("bunkerweb" "bw-scheduler")
        if [ "$integration" == "Autoconf" ] ; then
            containers+=("bw-autoconf")
        fi
        if [ "$type" == "ui" ] ; then
            containers+=("bw-ui")
        elif [ "$type" == "api" ] ; then
            containers+=("bw-api")
        fi

        running_containers=$(docker ps -a --format "{{.Names}}")
        if echo "$running_containers" | grep -q "crowdsec" ; then
            containers+=("crowdsec")
        fi

        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep -w "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            if [ "$integration" == "Autoconf" ] ; then
                log "WAIT" "ℹ️ " "🔩 Autoconf stack is healthy ✅"
            else
                log "WAIT" "ℹ️ " "🐳 Docker stack is healthy ✅"
            fi
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge "$timeout" ] ; then
        if [ "$integration" == "Autoconf" ] ; then
            log "WAIT" "❌" "🔩 Autoconf stack is not healthy after $timeout seconds"
        else
            log "WAIT" "❌" "🐳 Docker stack is not healthy after $timeout seconds"
        fi
        exit 1
    fi
elif [ "$integration" == "All-in-one" ] ; then
    while [ $i -lt "$timeout" ] ; do
        healthy="true"
        check="$(docker inspect --format "{{json .State.Health }}" "bunkerweb-all-in-one" | grep -w "healthy")"
        if [ "$check" = "" ] ; then
            healthy="false"
        fi
        if [ "$healthy" = "true" ] ; then
            log "WAIT" "ℹ️ " "🍱 All-in-one stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge "$timeout" ] ; then
        log "WAIT" "❌" "🍱 All-in-one stack is not healthy after $timeout seconds"
        exit 1
    fi
elif [ "$integration" == "Kubernetes" ] ; then
    # Wait for stack to all be ready
    while [ $i -lt "$timeout" ] ; do
        output=$(kubectl get pods -n bunkerweb -o jsonpath="{.items[*].status.containerStatuses[*].ready}" 2>&1)
        if echo "$output" | grep -q "etcdserver: request timed out" ; then
            log "WAIT" "⚠️" "☸️ etcdserver timeout detected. Retrying..."
        elif echo "$output" | grep -vq "false" ; then
            log "WAIT" "ℹ️ " "☸️ Kubernetes stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge "$timeout" ] ; then
        log "WAIT" "❌" "☸️ Kubernetes stack is not healthy after $timeout seconds"
        exit 1
    fi
else
    healthy="false"
    retries=0
    while [[ $healthy = "false" && $retries -lt 5 ]] ; do
        while [ $i -lt "$timeout" ] ; do
            if $IS_FREEBSD ; then
                if grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    log "WAIT" "ℹ️ " "🐚 FreeBSD stack is healthy ✅"
                    break
                fi
            else
                if docker exec -u 0 bunkerweb-linux grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    # If a crowdsec container exists, ensure it is healthy before declaring success
                    if docker ps -a --format "{{.Names}}" | grep -q "^crowdsec$" ; then
                        cs_health=$(docker inspect --format "{{json .State.Health }}" crowdsec | grep -w "healthy")
                        if [ -z "$cs_health" ] ; then
                            # Crowdsec not healthy yet, keep waiting
                            sleep 1
                            i=$((i+1))
                            continue
                        fi
                    fi
                    log "WAIT" "ℹ️ " "🐧 Linux stack is healthy ✅"
                    break
                fi
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge "$timeout" ] ; then
            if $IS_FREEBSD ; then
                log "WAIT" "❌" "🐚 FreeBSD stack is not healthy after $timeout seconds"
            else
                log "WAIT" "❌" "🐧 Linux stack is not healthy after $timeout seconds"

                # A stack can go unhealthy from bunkerweb-api/bunkerweb-scheduler being cleanly
                # stopped and restarted by systemd mid-wait, in lockstep, every ~30s -- not a
                # Restart=always crash-loop (that only respawns after a process has already
                # exited) but an externally requested stop the units' own journals never name.
                # log_stack()'s per-unit `journalctl -u ...` dump (run next, via the EXIT trap)
                # shows the child's side only. systemd's PID-1 journal does NOT name a stop's
                # requester at default log level (only debug level logs the enqueuing job), but
                # it DOES print "Scheduled restart job, restart counter is at N" on every
                # automatic Restart= respawn — so together with NRestarts below it discriminates
                # an auto-respawn loop from an externally requested stop, the exact fork left
                # open in .cache/results-2026-08-28/postround2-triage.md §4. `|| true` on every
                # command: this is a diagnostic-only dump on a path that is about to exit 1 for
                # its own reason, so a missing systemd/docker container here must never change
                # that exit code or abort the rest of the dump.
                log "WAIT" "ℹ️ " "📜 Showing systemd PID 1 journal (auto-respawn vs externally requested stop) ..."
                docker exec -u 0 bunkerweb-linux journalctl _PID=1 --no-pager || true

                log "WAIT" "ℹ️ " "📜 Showing bunkerweb-api/bunkerweb-scheduler unit status ..."
                docker exec -u 0 bunkerweb-linux systemctl status bunkerweb-api bunkerweb-scheduler --no-pager -l -n 30 || true

                log "WAIT" "ℹ️ " "📜 Showing systemd job queue ..."
                docker exec -u 0 bunkerweb-linux systemctl list-jobs --no-pager || true

                log "WAIT" "ℹ️ " "📜 Showing bunkerweb-api/bunkerweb-scheduler unit relationships ..."
                docker exec -u 0 bunkerweb-linux systemctl show bunkerweb-api bunkerweb-scheduler -p NRestarts,Result,TriggeredBy,PartOf,BoundBy,ConflictedBy,InvocationID || true

                log "WAIT" "ℹ️ " "📜 Showing process snapshot (newest-started last) ..."
                docker exec -u 0 bunkerweb-linux ps -eo pid,ppid,etime,cmd --sort=start_time 2>&1 | tail -40 || true
            fi
            exit 1
        fi

        if $IS_FREEBSD ; then
            healthy="true"
        else
            if docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                log "WAIT" "⚠" "🐧 Linux stack got an issue, restarting ..."
                cleanup_stack
                ./tests/scripts/start.sh "$integration" "$type"
                retries=$((retries+1))
            else
                healthy="true"
            fi

            if docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb-scheduler --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                log "WAIT" "⚠" "🐧 Linux stack got an issue, restarting ..."
                cleanup_stack
                ./tests/scripts/start.sh "$integration" "$type"
                retries=$((retries+1))
            else
                healthy="true"
            fi

            if [ "$type" == "ui" ] ; then
                if docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb-ui --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                    log "WAIT" "⚠" "🐧 Linux stack got an issue, restarting ..."
                    cleanup_stack
                    ./tests/scripts/start.sh "$integration" "$type"
                    retries=$((retries+1))
                else
                    healthy="true"
                fi
            elif [ "$type" == "api" ] ; then
                if docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb-api --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                    log "WAIT" "⚠" "🐧 Linux stack got an issue, restarting ..."
                    cleanup_stack
                    ./tests/scripts/start.sh "$integration" "$type"
                    retries=$((retries+1))
                else
                    healthy="true"
                fi
            fi
        fi
    done
    if [ "$retries" -ge 5 ] ; then
        if $IS_FREEBSD ; then
            log "WAIT" "❌" "🐚 FreeBSD stack could not be healthy after $retries retries"
        else
            log "WAIT" "❌" "🐧 Linux stack could not be healthy after $retries retries"
        fi
        exit 1
    fi
fi

# Since 1.7 the scheduler does not push the configuration itself: it queues push-configs on
# the broker and returns, so a stack whose containers are healthy can still be serving the
# configuration of the previous action. wait.sh only runs after a start or a restart, which
# always dispatches one, so wait for the worker to record the run.
# run.sh marks the count of runs before restarting, so this waits for one that belongs to
# the restart rather than one the previous action left behind.
if config_wait_applies ; then
    log "WAIT" "ℹ️ " "⏳ Waiting for the configuration to be pushed ..."
    if ! python3 tests/wait_config.py "$integration" --timeout "$timeout" ; then
        exit 1
    fi
fi
