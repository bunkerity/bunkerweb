#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Get the highest Python version available and export it
PYTHON_BIN=$(get_python_bin)
export PYTHON_BIN

# Set the PYTHONPATH so `worker.app` / `worker.tasks` import alongside the shared
# code. Mirrors the AIO worker supervisor (src/all-in-one/supervisor.d/worker.ini):
# bunkerweb root (for the `worker` package) + deps/python + db + utils + api.
BW_PYTHONPATH=$(get_bunkerweb_pythonpath)
export PYTHONPATH="/usr/share/bunkerweb:${BW_PYTHONPATH}:/usr/share/bunkerweb/db:/usr/share/bunkerweb/utils:/usr/share/bunkerweb/api"

WORKER_PID_FILE=/var/run/bunkerweb/worker.pid

# Display usage information
function display_help() {
    echo "Usage: $(basename "$0") [start|stop|reload|restart]"
    echo "Options:"
    echo "  start:   Start the bunkerweb worker (Celery) service."
    echo "  stop:    Stop the bunkerweb worker service."
    echo "  reload:  Reload the bunkerweb worker service."
    echo "  restart: Stop and then start the bunkerweb worker service."
}

# Start the bunkerweb worker service
function start() {
    log "SYSTEMCTL" "ℹ️" "Starting BunkerWeb Worker service ..."

    # Check if the worker is already running
    stop

    # Create PID folder
    if [ ! -f /var/run/bunkerweb ] ; then
        mkdir -p /var/run/bunkerweb
        chown nginx:nginx /var/run/bunkerweb
    fi

    # Create TMP folder
    if [ ! -f /var/tmp/bunkerweb ] ; then
        mkdir -p /var/tmp/bunkerweb
        chown nginx:nginx /var/tmp/bunkerweb
        chmod 2770 /var/tmp/bunkerweb
    fi

    # Create LOG folder
    if [ ! -f /var/log/bunkerweb ] ; then
        mkdir -p /var/log/bunkerweb
        chown nginx:nginx /var/log/bunkerweb
    fi

    # Export variables from env files (worker overrides variables.env)
    export_env_file /etc/bunkerweb/variables.env
    export_env_file /etc/bunkerweb/worker.env

    # Broker URL (also used for the reload-debounce lock). Defaults to the local broker.
    : "${CELERY_BROKER_URL:=redis://127.0.0.1:6379/0}"

    # The worker pushes cache + POSTs /reload to the local BunkerWeb instance after a
    # reload-flagged job. On Linux the local NGINX does not self-register a routable
    # hostname in the DB, so target 127.0.0.1 explicitly (each token becomes
    # http://<host>:5000 in worker/tasks.py:_get_apis). Empty would silently disable reloads.
    : "${BUNKERWEB_INSTANCES:=127.0.0.1}"

    : "${DATABASE_URI:=sqlite:////var/lib/bunkerweb/db.sqlite3}"

    : "${LOG_LEVEL:=info}"
    : "${WORKER_CONCURRENCY:=2}"
    : "${WORKER_MAX_MEMORY_KB:=300000}"
    : "${WORKER_QUEUES:=default,heavy}"
    : "${WORKER_HOSTNAME:=worker@%h}"
    : "${LOG_SYSLOG_TAG:=bw-worker}"

    export CELERY_BROKER_URL BUNKERWEB_INSTANCES DATABASE_URI
    export LOG_LEVEL WORKER_CONCURRENCY WORKER_MAX_MEMORY_KB WORKER_QUEUES WORKER_HOSTNAME LOG_SYSLOG_TAG

    # Execute the Celery worker. We exec under run_as_nginx and let Celery own the
    # pidfile (--pidfile): backgrounding with `&` and capturing $! would record the
    # privilege-drop wrapper PID, not the Celery master. Type=simple in the unit, so
    # this stays in the foreground as the service's main process.
    log "SYSTEMCTL" "ℹ️ " "Executing worker ..."
    if ! run_as_nginx env PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m celery -A worker.app worker \
        --loglevel="${LOG_LEVEL}" \
        --concurrency="${WORKER_CONCURRENCY}" \
        --pool=prefork \
        --max-tasks-per-child=1 \
        --max-memory-per-child="${WORKER_MAX_MEMORY_KB}" \
        --hostname="${WORKER_HOSTNAME}" \
        --pidfile="${WORKER_PID_FILE}" \
        --without-heartbeat \
        --without-mingle \
        --without-gossip \
        -Ofair \
        -Q "${WORKER_QUEUES}"; then
        log "SYSTEMCTL" "❌" "Worker execution failed (nginx user execution error)"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️ " "Worker stopped"
}

function stop() {
    log "SYSTEMCTL" "ℹ️" "Stopping BunkerWeb Worker service ..."

    if [ -f "$WORKER_PID_FILE" ] ; then
        worker_pid=$(cat "$WORKER_PID_FILE")
        if ! kill -0 "$worker_pid" >/dev/null 2>&1; then
            log "SYSTEMCTL" "ℹ️ " "Worker PID file is stale, cleaning up"
            rm -f "$WORKER_PID_FILE"
            return 0
        fi
        log "SYSTEMCTL" "ℹ️ " "Stopping worker..."
        # Celery treats TERM as warm shutdown (finish in-flight task, then exit).
        kill -s TERM "$worker_pid"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            if ! kill -0 "$worker_pid" >/dev/null 2>&1; then
                rm -f "$WORKER_PID_FILE"
                return 0
            fi
            log "SYSTEMCTL" "❌" "Error while sending stop signal to worker"
            exit 1
        fi
    else
        log "SYSTEMCTL" "ℹ️ " "Worker already stopped"
        return 0
    fi
    count=0
    while [ -f "$WORKER_PID_FILE" ] ; do
        if ! kill -0 "$worker_pid" >/dev/null 2>&1; then
            rm -f "$WORKER_PID_FILE"
            break
        fi
        sleep 1
        count=$((count + 1))
        if [ $count -ge 10 ] ; then
            break
        fi
    done
    if [ $count -ge 10 ] ; then
        log "SYSTEMCTL" "❌" "Timeout while waiting worker to stop"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️ " "BunkerWeb Worker service is stopped"
}

function reload() {
    log "SYSTEMCTL" "ℹ️" "Reloading BunkerWeb Worker service ..."
    stop
    sleep 2
    start
}

function restart() {
    log "SYSTEMCTL" "ℹ️" "Restarting BunkerWeb Worker service ..."
    stop
    sleep 2
    start
}

# List of different args
case $1 in
    "start")
    start
    ;;
    "stop")
    stop
    ;;
    "reload")
    reload
    ;;
    "restart")
    restart
    ;;
    *)
    echo "Invalid option!"
    echo "List of options availables:"
    display_help
esac
