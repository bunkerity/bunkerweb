#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"

if redis-cli ping | grep -q "PONG" ; then
    log "WAIT" "ℹ️ " "💽 Redis server is healthy ✅"
else
    log "WAIT" "❌" "💽 Redis server is not healthy"
    exit 1
fi

timeout=$(redis-cli get timeout)
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
