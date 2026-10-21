#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Get the highest Python version available and export it
PYTHON_BIN=$(get_python_bin)
export PYTHON_BIN

# Set the PYTHONPATH
BW_PYTHONPATH=$(get_bunkerweb_pythonpath)
export PYTHONPATH="$BW_PYTHONPATH"

NGINX_BIN=$(get_nginx_bin)
NGINX_CONF_DIR=$(get_nginx_conf_dir)
# Display usage information
function display_help() {
    echo "Usage: $(basename "$0") [start|stop|reload|restart]"
    echo "Options:"
    echo "  start:   Create configurations and start the bunkerweb service."
    echo "  stop:    Stop the bunkerweb service."
    echo "  reload:  Reload the bunkerweb service."
    echo "  restart: Stop and then start the bunkerweb service."
}

function generate_tmp_env_content() {
    cat <<EOF
IS_LOADING=yes
USE_BUNKERNET=no
SEND_ANONYMOUS_REPORT=no
SERVER_NAME=
DNS_RESOLVERS=${DNS_RESOLVERS}
API_LISTEN_HTTP=${API_LISTEN_HTTP}
API_HTTP_PORT=${API_HTTP_PORT}
API_LISTEN_HTTPS=${API_LISTEN_HTTPS}
API_HTTPS_PORT=${API_HTTPS_PORT}
API_LISTEN_IP=${API_LISTEN_IP}
API_SERVER_NAME=${API_SERVER_NAME}
API_WHITELIST_IP=${API_WHITELIST_IP}
API_TOKEN=${API_TOKEN}
USE_REAL_IP=${USE_REAL_IP}
USE_PROXY_PROTOCOL=${USE_PROXY_PROTOCOL}
REAL_IP_FROM=${REAL_IP_FROM}
REAL_IP_HEADER=${REAL_IP_HEADER}
HTTP_PORT=${HTTP_PORT}
HTTPS_PORT=${HTTPS_PORT}
KEEP_CONFIG_ON_RESTART=${KEEP_CONFIG_ON_RESTART}
EOF
}

function write_tmp_env_file() {
    local tmp_env_path="$1"
    local tmp_env_content="$2"
    printf "%s\n" "$tmp_env_content" > "$tmp_env_path"
    chown root:nginx "$tmp_env_path"
    chmod 660 "$tmp_env_path"
}

# Start the bunkerweb service
function start() {

    # Set the PYTHONPATH
    export PYTHONPATH="$BW_PYTHONPATH"

    log "SYSTEMCTL" "ℹ️" "Starting BunkerWeb service ..."

    if command -v setcap >/dev/null 2>&1 && [ -x "$NGINX_BIN" ]; then
        setcap 'CAP_NET_BIND_SERVICE=+eip' "$NGINX_BIN" || true
    fi
    if [ -d "$NGINX_CONF_DIR" ]; then
        chown -R nginx:nginx "$NGINX_CONF_DIR"
    fi

    # Create dummy variables.env
    if [ ! -f /etc/bunkerweb/variables.env ]; then
        {
            echo "# remove IS_LOADING=yes when your config is ready"
            echo "IS_LOADING=yes"
            echo "SERVER_NAME="
            echo "DNS_RESOLVERS=9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4" # Quad9, Google
            echo "HTTP_PORT=80"
            echo "HTTPS_PORT=443"
            echo "API_LISTEN_IP=127.0.0.1"
            echo "API_TOKEN="
            echo "KEEP_CONFIG_ON_RESTART=no"
        } > /etc/bunkerweb/variables.env
        chown root:nginx /etc/bunkerweb/variables.env
        chmod 660 /etc/bunkerweb/variables.env
        log "SYSTEMCTL" "ℹ️" "Created dummy variables.env file"
    fi

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

    # Stop nginx if it's running
    stop

    # Generate temp conf for nginx
    # Default values
    declare -A defaults=(
        [DNS_RESOLVERS]="9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4" # Quad9, Google
        [API_LISTEN_HTTP]="yes"
        [API_LISTEN_HTTPS]="no"
        [API_HTTP_PORT]="5000"
        [API_HTTPS_PORT]="5443"
        [API_LISTEN_IP]="127.0.0.1"
        [API_SERVER_NAME]="bwapi"
        [API_WHITELIST_IP]="127.0.0.0/8"
        [API_TOKEN]=""
        [USE_REAL_IP]="no"
        [USE_PROXY_PROTOCOL]="no"
        [REAL_IP_FROM]="192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
        [REAL_IP_HEADER]="X-Forwarded-For"
        [HTTP_PORT]="80"
        [HTTPS_PORT]="443"
        [KEEP_CONFIG_ON_RESTART]="no"
    )

    # File containing the environment variables
    env_file="/etc/bunkerweb/variables.env"

    # Load variables safely
    if [ -f "$env_file" ]; then
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            [[ -z "$key" || "$key" =~ ^# ]] && continue
            # Trim whitespace from key
            key=$(echo "$key" | xargs)
            # Only process recognized keys. Test the key, not its default : API_TOKEN
            # defaults to the empty string, so testing the value skipped it entirely and
            # the temp config was generated with no token at all.
            if [[ -v "defaults[$key]" ]]; then
                # Set variable if defined and non-empty in the file. printf -v assigns without
                # evaluating: /etc/bunkerweb is owned by nginx:nginx and every unit runs as root,
                # so eval here ran a value's command substitution as root.
                [[ -n "$value" ]] && printf -v "$key" '%s' "$value"
            fi
        done < "$env_file"
    fi

    # Assign default values for unset variables
    for key in "${!defaults[@]}"; do
        value="${!key:-}"
        if [ -z "$value" ]; then
            printf -v "$key" '%s' "${defaults[$key]}"
        fi
    done

    tmp_env_path="/var/tmp/bunkerweb/tmp.env"
    tmp_env_content="$(generate_tmp_env_content)"
    regenerate_temp_config=false

    tmp_env_path="/var/tmp/bunkerweb/tmp.env"

    # Present when an install into /etc/nginx was cut short. Each file lands atomically but the tree does
    # not, so what is there is a mix of two generations. Keep the name in step with sync_tree.INSTALL_SENTINEL.
    install_sentinel="/etc/nginx/.bw-install-incomplete"

    if [[ "$KEEP_CONFIG_ON_RESTART" == "no" ]] || [[ ! -f "$tmp_env_path" ]] ; then
        regenerate_temp_config=true
    elif [ -e "$install_sentinel" ] ; then
        log "SYSTEMCTL" "⚠️" "The previous configuration install was interrupted, so the preserved config may mix two generations: regenerating the temporary config instead of keeping it"
        regenerate_temp_config=true
    else
        log "SYSTEMCTL" "ℹ️" "Preserving current config on restart, keeping it enforced and asking the scheduler for the latest one ..."
        # Every access control keeps running on the preserved configuration. The scheduler sees this
        # file through /health and pushes the latest configuration, which removes it. It is created
        # as nginx: this script runs as root and /var/tmp is sticky, so a root-owned file could never
        # be removed by the worker.
        if ! run_as_nginx touch /var/tmp/bunkerweb_needs_config ; then
            log "SYSTEMCTL" "⚠️" "Couldn't create /var/tmp/bunkerweb_needs_config, the preserved config stays in use until the next configuration change"
        fi
    fi

    write_tmp_env_file "$tmp_env_path" "$tmp_env_content"

    # A marker left by the previous run stands for no reload: no nginx runs yet. The generator waits for
    # it, and refuses to install while it exists, so it has to go first. This also lets the health
    # endpoint report "loading" and not a stale "reloading".
    if [ -f /var/tmp/bunkerweb/reloading ] ; then
        rm -f /var/tmp/bunkerweb/reloading
    fi
    # Remove the previous marker location on upgraded hosts; /var/tmp may be read-only.
    rm -f /var/tmp/bunkerweb_reloading 2>/dev/null || true

    if [[ "$regenerate_temp_config" == "true" ]] ; then
        rm -f /var/tmp/bunkerweb_needs_config
        if ! run_as_nginx env PYTHONPATH="$BW_PYTHONPATH" "$PYTHON_BIN" /usr/share/bunkerweb/gen/main.py \
            --variables "$tmp_env_path"; then
            log "SYSTEMCTL" "❌" "Error while generating config from $tmp_env_path"
            exit 1
        fi
        rm -f "$install_sentinel"
    fi

    # Clean orphaned NGINX temp files from previous runs
    for dir in client_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp; do
        target="/var/tmp/bunkerweb/$dir"
        if [ -d "$target" ] && [ ! -L "$target" ]; then
            if [ -n "$(find "$target" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
                log "SYSTEMCTL" "ℹ️" "Cleaning orphaned temp files from $dir"
            fi
            find "$target" -mindepth 1 -delete 2>/dev/null || true
        fi
    done

    # Start nginx
    if ! run_as_nginx env PYTHONPATH="$BW_PYTHONPATH" "$PYTHON_BIN" /usr/share/bunkerweb/utils/modsecurity_audit.py /etc/nginx/variables.env; then
        log "SYSTEMCTL" "❌" "Invalid ModSecurity audit storage, refusing to start nginx"
        exit 1
    fi
    log "SYSTEMCTL" "ℹ️" "Starting nginx ..."
    if [ "$(uname)" = "FreeBSD" ]; then
        "$NGINX_BIN" -e /var/log/bunkerweb/error.log
        nginx_rc=$?
    else
        run_as_nginx "$NGINX_BIN" -e /var/log/bunkerweb/error.log
        nginx_rc=$?
    fi
    if [ "$nginx_rc" -ne 0 ]; then
        log "SYSTEMCTL" "❌" "Error while executing temp nginx"
        exit 1
    fi
    count=0
    while [ $count -lt 10 ] ; do
        check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:6000/healthz 2>&1)"
        # shellcheck disable=SC2181
        # The temp config carries IS_LOADING=yes, so the endpoint answers "loading" here :
        # either state means nginx is up and answering.
        if [ $? -eq 0 ] && [[ "$check" =~ ^(ok|loading)$ ]] ; then
            break
        fi
        count=$((count + 1))
        sleep 1
        log "SYSTEMCTL" "ℹ️" "Waiting for nginx to start ..."
    done
    if [ $count -ge 10 ] ; then
        log "SYSTEMCTL" "❌" "nginx is not started"
        exit 1
    fi
    log "SYSTEMCTL" "ℹ️" "nginx started ..."

    log "SYSTEMCTL" "ℹ️" "BunkerWeb service started ..."

    while [ -f /var/run/bunkerweb/nginx.pid ] ; do
        # Break if the process is no longer alive (e.g. killed by OOM without cleaning up the PID file)
        nginx_pid=$(cat /var/run/bunkerweb/nginx.pid 2>/dev/null)
        if [ -n "$nginx_pid" ] && ! kill -0 "$nginx_pid" 2>/dev/null ; then
            rm -f /var/run/bunkerweb/nginx.pid
            break
        fi
        sleep 1
    done
}

function stop() {
    log "SYSTEMCTL" "ℹ️" "Stopping BunkerWeb service ..."

    pid_file="/var/run/bunkerweb/nginx.pid"

    if [ -f "$pid_file" ] ; then
        pid="$(cat "$pid_file" 2>/dev/null)"
        if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1 ; then
            log "SYSTEMCTL" "ℹ️ " "Stopping nginx (PID $pid)..."
            # Try graceful quit first
            kill -QUIT "$pid" >/dev/null 2>&1
            # Fallback to TERM if needed later
        else
            # PID file exists but process not running
            log "SYSTEMCTL" "⚠️ " "PID file exists but nginx not running; cleaning up"
            rm -f "$pid_file"
        fi
    else
        log "SYSTEMCTL" "ℹ️ " "nginx is not running"
    fi

    # Wait for nginx to stop based on our own PID
    count=0
    if [ -n "$pid" ] ; then
        while kill -0 "$pid" >/dev/null 2>&1 ; do
            log "SYSTEMCTL" "ℹ️ " "Waiting for nginx to stop..."
            sleep 1
            count=$((count + 1))
            if [ $count -ge 20 ] ; then
                break
            fi
        done

        if kill -0 "$pid" >/dev/null 2>&1 ; then
            # Graceful stop timed out, try TERM
            log "SYSTEMCTL" "ℹ️ " "Stopping nginx (TERM)..."
            kill -TERM "$pid" >/dev/null 2>&1 || true
            # Wait a bit more
            extra=0
            while kill -0 "$pid" >/dev/null 2>&1 ; do
                sleep 1
                extra=$((extra + 1))
                if [ $extra -ge 5 ] ; then
                    break
                fi
            done
        fi

        if kill -0 "$pid" >/dev/null 2>&1 ; then
            log "SYSTEMCTL" "❌" "Timeout while waiting nginx to stop"
            exit 1
        fi
    fi

    # Ensure PID file is removed
    [ -f "$pid_file" ] && rm -f "$pid_file"

    log "SYSTEMCTL" "ℹ️ " "nginx is stopped"

    log "SYSTEMCTL" "ℹ️" "BunkerWeb service stopped"
}

# The generator installs a rendered configuration into /etc/nginx file by file, and nginx reads the
# routing and the variables at different moments of a reload. The API reload handler and the generator
# take turns through two files (see api.lua and gen/sync_tree.py): the generator locks
# /var/tmp/bunkerweb/generating and then looks for the reloading marker, the reload writes the marker
# and then probes the lock, so whoever comes second sees the other and backs off. This does the same.
# Succeeds while a generator holds its lock, and also when that cannot be told: the reload then does
# not go on.
function generator_installing() {
    local rc
    [ -e /var/tmp/bunkerweb/generating ] || return 1
    if command -v flock >/dev/null 2>&1 ; then
        # Opened for reading only, so this never creates the file. The shared lock is taken without
        # waiting and given back when the subshell exits; 99 says the generator holds it.
        ( exec 9< /var/tmp/bunkerweb/generating && flock -n -s -E 99 9 ) 2>/dev/null
        rc=$?
    elif command -v lockf >/dev/null 2>&1 ; then
        # FreeBSD has no flock(1). lockf(1) takes the same flock(2) lock, but only an exclusive one:
        # -n never creates the file, -k never removes it, -t 0 never waits, and the lock is given back
        # when the command ends. Anything but success, 75 (held) included, says a generator installs.
        lockf -k -n -s -t 0 /var/tmp/bunkerweb/generating true 2>/dev/null
        rc=$?
    else
        return 0
    fi
    [ "$rc" -ne 0 ]
}

# Integer seconds since boot, shared with the API and generator and unaffected by wall-clock steps.
function read_reload_uptime() {
    local uptime
    IFS=' ' read -r uptime _ 2>/dev/null < /proc/uptime || return 1
    [[ "$uptime" =~ ^([0-9]+)\.[0-9]+$ ]] || return 1
    printf '%s' "${BASH_REMATCH[1]}"
}

# Removes a rejected reload's orphan only when its monotonic stamp proves it is over five minutes old.
function clear_stale_reload_marker() {
    local -r RELOAD_MARKER_MAX_AGE=300
    local token current created now
    [ -f /var/tmp/bunkerweb/reloading ] || return 1
    # The suffix preserves trailing newlines so the second read compares the complete content.
    token="$(cat /var/tmp/bunkerweb/reloading && printf '.')" || return 1
    token="${token%.}"
    [[ "$token" =~ ^[0-9]+\.[0-9]+\.([0-9]+)$ ]] || return 1
    created="${BASH_REMATCH[1]}"
    now="$(read_reload_uptime)" || return 1
    awk -v now="$now" -v created="$created" -v age="$RELOAD_MARKER_MAX_AGE" 'BEGIN { exit !(now - created > age) }' || return 1
    current="$(cat /var/tmp/bunkerweb/reloading && printf '.')" || return 1
    # ponytail: two removers and a fresh publisher can still race between this comparison and unlink.
    [ "${current%.}" = "$token" ] || return 1
    rm -f /var/tmp/bunkerweb/reloading || return 1
    log "$1" "⚠️" "Removing orphaned reload marker /var/tmp/bunkerweb/reloading older than 5 minutes"
}

# One reload is in flight at a time, from its signal to the moment its new workers are up: they remove
# the marker, and only while it holds the token of the reload they belong to (see api.lua and
# init-lua.conf). The token is written to a file of its own and hard linked to the marker, which fails
# while the marker exists, so the marker is either absent or complete. It is done as nginx, since the
# workers remove it and /var/tmp is sticky, and a reload that finds one waits for it to go. A marker that never goes
# belongs to a reload the master rejected after it parsed the configuration and is cleared after five minutes when its monotonic stamp proves its age.
# Returns 1 while a generator installs, 2 when the marker cannot be published, 3 while another reload
# is in flight: in each case the reload must not go on. Waits reload_wait_ticks tenths of a second.
function begin_reload() {
    local rc=1 publish_misses=0 uptime
    reload_token="$(date +%s).$RANDOM"
    if uptime="$(read_reload_uptime)" ; then
        reload_token="$reload_token.$uptime"
    fi
    for _ in $(seq 1 "${reload_wait_ticks:-200}") ; do
        clear_stale_reload_marker "SYSTEMCTL"
        # Something that is not a file in the marker's place is no marker, and nothing can take its place
        if [ -e /var/tmp/bunkerweb/reloading ] && [ ! -f /var/tmp/bunkerweb/reloading ] ; then
            return 2
        fi
        # The script is for the shell run as nginx: $1 is its argument, not ours. Exit 2 says the token could
        # not be written (the write runs in a subshell because a file size limit kills the writer), 1 that
        # the marker exists.
        # shellcheck disable=SC2016
        run_as_nginx sh -c 'tmp="/var/tmp/bunkerweb/reloading.$$"; ( printf "%s" "$1" > "$tmp" ) || { rm -f "$tmp"; exit 2; }; ln "$tmp" /var/tmp/bunkerweb/reloading; rc=$?; rm -f "$tmp"; exit $rc' sh "$reload_token" 2>/dev/null
        case $? in
            0)
                publish_misses=0
                generator_installing || return 0
                rm -f /var/tmp/bunkerweb/reloading
                rc=1
                ;;
            1)
                if [ -e /var/tmp/bunkerweb/reloading ] ; then
                    publish_misses=0
                else
                    publish_misses=$((publish_misses + 1))
                    [ "$publish_misses" -lt 2 ] || return 2
                fi
                rc=3
                ;;
            *) return 2 ;;
        esac
        sleep 0.1
    done
    return $rc
}

# The marker is ours until the signal went out: nothing else removes it before then
function abort_reload() {
    rm -f /var/tmp/bunkerweb/reloading
    return 1
}

function reload()
{
    log "SYSTEMCTL" "ℹ️" "Reloading BunkerWeb service ..."

    pid_file="/var/run/bunkerweb/nginx.pid"
    if [ -f "$pid_file" ] ; then
        pid="$(cat "$pid_file" 2>/dev/null)"
        if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1 ; then
            begin_reload
            case $? in
                0) ;;
                2)
                    log "SYSTEMCTL" "❌" "Couldn't create /var/tmp/bunkerweb/reloading, keeping running configuration"
                    return 1
                    ;;
                3)
                    log "SYSTEMCTL" "❌" "A reload is in progress (/var/tmp/bunkerweb/reloading exists), keeping running configuration. If none is running, the last one was rejected after its configuration was parsed: a marker with a monotonic stamp is cleared automatically once it is older than 5 minutes; restart BunkerWeb or remove that file to clear it sooner"
                    return 1
                    ;;
                *)
                    log "SYSTEMCTL" "❌" "A configuration generation is in progress, keeping running configuration"
                    return 1
                    ;;
            esac
            if ! run_as_nginx env PYTHONPATH="$BW_PYTHONPATH" "$PYTHON_BIN" /usr/share/bunkerweb/utils/modsecurity_audit.py /etc/nginx/variables.env; then
                log "SYSTEMCTL" "❌" "Invalid ModSecurity audit storage, keeping running configuration"
                abort_reload
                return 1
            fi
            log "SYSTEMCTL" "ℹ️" "Reloading nginx ..."
            "$NGINX_BIN" -s reload
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "SYSTEMCTL" "❌" "Error while sending reload signal to nginx"
                log "SYSTEMCTL" "ℹ️" "Reloading nginx (force) ..."
                kill -HUP "$pid" >/dev/null 2>&1
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "SYSTEMCTL" "❌" "Error while sending hup signal to nginx"
                    abort_reload
                fi
            fi
        else
            log "SYSTEMCTL" "❌" "nginx is not running"
            exit 1
        fi
    else
        log "SYSTEMCTL" "❌" "nginx is not running"
        exit 1
    fi

    log "SYSTEMCTL" "ℹ️" "BunkerWeb service reloaded ..."
}

function restart() {
    log "SYSTEMCTL" "ℹ️" "Restarting BunkerWeb service ..."
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
