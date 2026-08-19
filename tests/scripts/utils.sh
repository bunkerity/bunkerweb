#!/bin/bash

integration="${1^}"
type="${2:-}"
release="${3:-}"
trapped=false
HOST_OS="$(uname -s)"
IS_FREEBSD=false

if [ "$HOST_OS" == "FreeBSD" ] ; then
    IS_FREEBSD=true
fi

# start.sh sets this for itself and two functions below re-export it, but wait.sh only sources
# this file: without it here, stack_has_worker sees no version, assumes the current stack, and
# the upgrade spec waits 300s for a push-configs row a 1.6 stack never writes.
if [ -f /tmp/bw_version.txt ] ; then
    BW_VERSION="$(cat /tmp/bw_version.txt)"
    export BW_VERSION
fi

function log() {
	log_when="$(date '+[%Y-%m-%d %H:%M:%S %z]')"
	log_category="${1:-}"
	log_severity="${2:-}"
	log_message="${3:-}"
	echo "$log_when [$log_category] [$log_severity] - $log_message"
}

function sed_in_place() {
    local expression="$1"
    local target="$2"

    if $IS_FREEBSD ; then
        sed -i '' "$expression" "$target"
    else
        sed -i "$expression" "$target"
    fi
}

# Robust docker pull function with exponential backoff
function robust_docker_pull() {
    local compose_file="${1:-}"
    local component="${2:-}"
    local max_attempts=${3:-5}
    local attempt=1
    local wait_time=5

    log "PULL" "ℹ️ " "🐳 Pulling $component images..."

    while [ "$attempt" -le "$max_attempts" ]; do
        if docker compose -f "$compose_file" pull; then
            log "PULL" "ℹ️ " "🐳 Successfully pulled $component images ✅"
            return 0
        fi

        # If this was our last attempt, report failure
        if [ "$attempt" -eq "$max_attempts" ]; then
            log "PULL" "❌" "🐳 Failed to pull $component images after $max_attempts attempts"
            return 1
        fi

        # Log retry message and wait
        log "PULL" "⚠️" "🐳 Failed to pull $component images, retrying in $wait_time seconds... (Attempt $attempt/$max_attempts)"
        sleep $wait_time

        # Exponential backoff with a cap of 60 seconds
        wait_time=$((wait_time * 2))
        [ $wait_time -gt 60 ] && wait_time=60

        attempt=$((attempt + 1))
    done
}

# Run an example's own setup-<integration>.sh or cleanup-<integration>.sh, the way a
# reader of the documentation would: from inside the stack directory, as root. Examples
# use them to fix web-root ownership or install a Helm chart, so skipping them deploys a
# stack that boots and then serves nothing.
# The framework's state store. It does NOT live on 6379: the Linux package owns that port on
# the host for the Celery broker (see tests/misc/docker/redis.yml). Every script talks to it
# through this wrapper so the port is stated once.
export TESTS_REDIS_PORT="${TESTS_REDIS_PORT:-6390}"

function redis_cli() {
    redis-cli -p "$TESTS_REDIS_PORT" "$@"
}

function apply_example_variables_env() {
    # A Linux example configures the packaged instance through its own variables.env, and that
    # has to be in place before anything starts: the services read /etc/bunkerweb once at boot,
    # and this same directory is what the container mounts there. Applied after generate.py so
    # the example wins, and on every restart too -- generate.py rewrites the file from scratch
    # for each action, so an example that is only applied at the first start silently stops
    # being the configuration under test from the second action on.
    [ -f /tmp/example_stack.txt ] || return 0

    local etc="${BW_TESTS_ETC:-/etc/bunkerweb}"
    local example_env
    example_env="$(dirname "$(cat /tmp/example_stack.txt)")/variables.env"
    if [ ! -f "$example_env" ] ; then
        log "UTILS" "❌" "📕 $example_env is missing; a Linux example needs one"
        return 1
    fi

    # The example is the configuration, with one exception: the API_TOKEN the framework
    # generated. It is not part of what a reader copies -- the package generates its own at
    # install time -- and both the scheduler and the API read it from this file. Dropping it
    # leaves the scheduler unauthenticated: its `/system/readonly` call 401s, the client reports
    # a read-only database, and the stack loops on "Database is not initialized" until the wait
    # times out, with nothing naming authentication anywhere.
    local api_token
    api_token="$(grep "^API_TOKEN=" "$etc/variables.env" 2>/dev/null | head -n1)"

    log "UTILS" "ℹ️ " "📕 Applying the example's variables.env ..."
    if ! cp "$example_env" "$etc/variables.env" ; then
        log "UTILS" "❌" "📕 Could not install the example's variables.env"
        return 1
    fi

    if [ -n "$api_token" ] && ! grep -q "^API_TOKEN=" "$etc/variables.env" ; then
        echo "$api_token" >> "$etc/variables.env"
    fi
}


# Kubernetes: materialise the host fixtures inside the minikube node.
#
# This replaces `minikube mount` (9p over TCP), which the arm used to depend on, for two independent
# reasons:
#
#   - The node dials the host's 9p server across the docker bridge, so any host firewall drops it by
#     default. That is a known upstream problem with no fix (kubernetes/minikube#8054, #4726,
#     #18128); the accepted workaround is a per-run inbound rule naming a port minikube picks at
#     random. A test arm that cannot run without the operator editing their firewall is not a test
#     arm anyone will run.
#   - minikube's own handbook calls 9p unreliable above ~600 files. `/var/www/html` carries ~4000
#     once an example has left WordPress there, so the mount was already on the wrong side of
#     upstream's guidance even where the firewall allows it.
#
# A copy is sufficient because the traffic is one-way: every one of these directories is written by
# the host (fixtures, before-scripts, generated certificates) and only read by the pods, and
# `hostPath` asks for nothing more than the files existing on the node.
#
# Transport is `minikube cp` of a tarball, NOT a tar stream piped into `minikube ssh`: ssh allocates
# a TTY, which mangles binary on stdin -- verified, the stream comes back echoed and corrupted, and
# tar exits 130. `minikube cp` is binary-safe (md5 verified) and driver-agnostic.
function sync_to_minikube() {
    local host_dir="${1:-}"
    local node_dir="${2:-}"
    local owner="${3:-}"
    shift 3
    local members=("$@")
    if [ "${#members[@]}" -eq 0 ] ; then
        members=(".")
    fi

    local archive="/tmp/bw-minikube-sync${node_dir//\//_}.tgz"
    rm -f "$archive"

    if ! tar -C "$host_dir" -czf "$archive" "${members[@]}" 2> /dev/null ; then
        log "UTILS" "❌" "📂 Failed to archive $host_dir for Minikube"
        return 1
    fi

    if ! minikube cp "$archive" "minikube:$archive" > /dev/null 2>&1 ; then
        log "UTILS" "❌" "📂 Failed to copy the $host_dir archive into the Minikube node"
        rm -f "$archive"
        return 1
    fi

    local remote="sudo rm -rf '$node_dir' && sudo mkdir -p '$node_dir' && sudo tar -C '$node_dir' -xzf '$archive' && sudo rm -f '$archive'"
    if [ -n "$owner" ] ; then
        remote="$remote && sudo chown -R $owner '$node_dir'"
    fi

    if ! minikube ssh -- "$remote" > /dev/null 2>&1 ; then
        log "UTILS" "❌" "📂 Failed to unpack $node_dir inside the Minikube node"
        rm -f "$archive"
        return 1
    fi

    rm -f "$archive"
    log "UTILS" "ℹ️ " "📂 $host_dir synced into the Minikube node at $node_dir ✅"
}

# Every fixture the Kubernetes manifests mount as a hostPath. Called from build.sh once the stack is
# up, and again from start.sh before each apply -- a before-script runs after the build phase and
# writes certificates into /tmp/output, which a build-time-only sync would miss. Idempotent.
#
# The optional directories are keyed on existence rather than on the spec's category: build.sh
# creates them only for the specs that need them, so presence is the condition, and start.sh does
# not have to be told which category is running.
function sync_minikube_fixtures() {
    local hosts
    hosts="$(awk '/^127\.0\.0\.1 .*\.example\.com/ {print $2}' tests/misc/conf/dnsmasq.hosts | sort -u | tr '\n' ' ')"

    # Named members, never the whole tree: an example leaves its own application (WordPress and
    # friends, ~94 MB) in /var/www/html, and no Kubernetes spec serves any of it.
    # shellcheck disable=SC2086
    sync_to_minikube "/var/www/html" "/mnt/www" "33:101" index.php logo.png $hosts || return 1
    sync_to_minikube "/tmp/output" "/mnt/output" "" || return 1

    local optional
    for optional in redis-acl redis-tls redis-scripts valkey-acl valkey-tls valkey-sentinel ; do
        if [ -d "/tmp/$optional" ] ; then
            sync_to_minikube "/tmp/$optional" "/mnt/$optional" "" || return 1
        fi
    done
}

function provision_www_root() {
    # Same fixture CI copies in, for the hosts dnsmasq answers for. Additive: it never deletes
    # what is already there, so a stack left behind by an example keeps its own web root.
    local www="/var/www/html"
    local hosts
    hosts="$(awk '/^127\.0\.0\.1 .*\.example\.com/ {print $2}' tests/misc/conf/dnsmasq.hosts | sort -u | tr '\n' ' ')"

    local script="set -e
mkdir -p '$www'
cp tests/misc/index.php tests/misc/logo.png '$www/'
for host in $hosts ; do
    mkdir -p '$www'/\$host
    cp tests/misc/index.php tests/misc/logo.png '$www'/\$host/
done
chown -R 33:101 '$www'
chmod 755 '$www'
find '$www' -type d -exec chmod 755 {} +
find '$www' -type f -exec chmod 644 {} +"

    log "UTILS" "ℹ️ " "🐘 Provisioning $www for php-fpm ..."
    if [ "$(id -u)" -eq 0 ] ; then
        bash -c "$script"
    elif sudo -n true 2>/dev/null ; then
        sudo -E bash -c "$script"
    else
        # No passwordless sudo on a workstation: do it as root in a throwaway container, with
        # the repository and the web root both mounted at the paths the script expects.
        docker run --rm -v "$(pwd)":/repo -v "$www":"$www" -w /repo bash:5 bash -c "$script"
    fi
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "UTILS" "❌" "🐘 Failed to provision $www"
        return 1
    fi
}


function example_hook() {
    local phase="${1:-}"
    local integration="${2:-}"

    # Called from the teardown too, where the spec that just ran may not have been an example.
    [ -f /tmp/example_stack.txt ] || return 0

    local stack_dir
    stack_dir="$(dirname "$(cat /tmp/example_stack.txt)")"

    local script
    script="${stack_dir}/${phase}-$(echo "$integration" | tr '[:upper:]' '[:lower:]').sh"
    if [ ! -f "$script" ] ; then
        return 0
    fi

    log "UTILS" "ℹ️ " "📕 Running $(basename "$script") ..."
    chmod +x "$script"

    # Linux runs the packaged BunkerWeb inside a systemd container, and these scripts belong in
    # there: they call systemctl, install packages, and resolve the PHP user (www-data vs apache)
    # against the distro they are provisioning. Running them on the runner would configure the
    # runner. /var/www/html is bind-mounted either way, so only the web-root half would have
    # appeared to work -- the half that is silent when it fails.
    if [ "$integration" == "Linux" ] ; then
        # Not /tmp: the compose file mounts a tmpfs there, and `docker cp` writes to the image
        # layer underneath it, so the copy lands somewhere the running container cannot see.
        # The script then dies on "No such file or directory" with the copy reported as fine.
        # Removed first: `docker cp` into an existing directory nests the copy inside it, so the
        # second spec of a run would look for the script one level down.
        docker exec -u 0 bunkerweb-linux rm -rf /opt/example > /dev/null 2>&1
        if ! docker cp "$(realpath "$stack_dir")" bunkerweb-linux:/opt/example ; then
            log "UTILS" "❌" "📕 Could not copy the example into the Linux container"
            return 1
        fi
        if ! docker exec -u 0 -w /opt/example bunkerweb-linux bash "./$(basename "$script")" ; then
            log "UTILS" "❌" "📕 $(basename "$script") failed"
            return 1
        fi
        return 0
    fi

    # Several of these chown a web root, so they need root. CI has passwordless sudo; a
    # workstation usually does not, and the scripts refuse to run as anyone else ("Run me as
    # root"), which would fail every example locally. Fall back to a throwaway container that
    # runs the script as root against the bind-mounted stack directory -- the ownership it
    # sets lands on the host files just the same. `bash`, not `sh`: one of these scripts uses
    # brace expansion.
    local runner=()
    if [ "$(id -u)" -eq 0 ] ; then
        runner=()
    elif sudo -n true 2>/dev/null ; then
        runner=(sudo -E)
    else
        log "UTILS" "⚠️" "📕 sudo needs a password here, running $(basename "$script") as root in a container"
        if ! docker run --rm -v "$(realpath "$stack_dir")":/stack -w /stack bash:5 bash "./$(basename "$script")" ; then
            log "UTILS" "❌" "📕 $(basename "$script") failed"
            return 1
        fi
        return 0
    fi

    if ! (cd "$stack_dir" && "${runner[@]}" "./$(basename "$script")") ; then
        log "UTILS" "❌" "📕 $(basename "$script") failed"
        return 1
    fi
}

# Whether the push-configs wait applies to this stack. Linux has no worker container to
# query, and a Docker example brings its own database on its own terms rather than the one
# the framework generated; both fall back to the action's own delay.
# The standalone API, the worker and the job broker arrived in 1.7. The upgrade spec boots a
# previous release first, and those images simply do not exist for it: docker fails the pull with
# "repository does not exist". Anything that assumes the 1.7 topology has to ask this first.
function stack_has_worker() {
    local version major minor
    version="${BW_VERSION:-tests}"
    if [ "$version" == "tests" ] ; then
        return 0
    fi
    major="$(echo "$version" | cut -d. -f1 | tr -cd '0-9')"
    minor="$(echo "$version" | cut -d. -f2 | tr -cd '0-9')"
    # An unparseable version is treated as current rather than ancient: a stack missing its
    # worker fails loudly, while one that starts an extra container does not.
    [ -z "$major" ] && return 0
    [ -z "$minor" ] && minor=0
    if [ "$major" -gt 1 ] || { [ "$major" -eq 1 ] && [ "$minor" -ge 7 ] ; } ; then
        return 0
    fi
    return 1
}

function config_wait_applies() {
    # Linux used to sit out this wait because its stack ran no worker. It does now — the units
    # are started for every type — so it races the same way: the instance reports ready while
    # the push that carries the new configuration is still queued.
    if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Docker" ] ; then
        return 1
    fi
    # A pre-1.7 stack has no worker to record a push-configs run, so the wait could only ever
    # time out.
    if ! stack_has_worker ; then
        return 1
    fi
    # generate.py clears this for an action that shuts the instance's API listener: the worker
    # then has no way to push at all, which is the very thing the action asserts.
    local wait_flag
    wait_flag="$(redis_cli get config_wait 2>/dev/null)"
    if [ "$wait_flag" == "0" ] ; then
        return 1
    fi
    return 0
}

# Bring a compose file up, retrying once through a full "down -v" — the recovery the
# stack-up steps have always open-coded.
function compose_up() {
    local compose_file="${1:-}"
    local component="${2:-}"
    local emoji="${3:-🐳}"

    if docker compose -f "$compose_file" up -d ; then
        return 0
    fi

    log "START" "⚠️" "$emoji Up failed for $component, retrying ..."
    if ! docker compose -f "$compose_file" down -v ; then
        log "START" "❌" "$emoji Down failed for $component"
        return 1
    fi

    if ! docker compose -f "$compose_file" up -d ; then
        log "START" "❌" "$emoji Up failed for $component"
        return 1
    fi
}

if [ -z "$integration" ] ; then
    log "UTILS" "❌" "Please provide an integration name as argument"
    exit 1
elif [ "$integration" != "Docker" ] && [ "$integration" != "Linux" ] && [ "$integration" != "Autoconf" ] && [ "$integration" != "Swarm" ] && [ "$integration" != "Kubernetes" ] && [ "$integration" != "All-in-one" ] ; then
    log "UTILS" "❌" "Integration \"$integration\" is not supported"
    exit 1
elif [ -z "$type" ] ; then
    log "UTILS" "❌" "Please provide an test type as argument"
    exit 1
elif [ "$type" != "core" ] && [ "$type" != "ui" ] && [ "$type" != "api" ] ; then
    log "TEST" "❌" "Type \"$type\" is not supported"
    exit 1
fi

function cleanup_stack () {
    exit_code=$?
    if [ -n "${1:-}" ] ; then
        exit_code=$1
    fi

    log "UTILS" "ℹ️ " "🧹 Cleaning up current stack ..."

    if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Kubernetes" ] ; then
        example_stack="$(cat /tmp/example_stack.txt)"
        example_hook cleanup "$integration"
        kubectl delete -f "$example_stack" --ignore-not-found
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "📕 Failed to delete the example services"
            return 1
        fi
    fi

    if [ -f /tmp/services.yml ] ; then
        if [ "$integration" == "Kubernetes" ] ; then
            services_pods=$(kubectl get pods -n services -o jsonpath='{.items[*].metadata.name}')
            if echo "$services_pods" | grep -q "app1" ; then
                kubectl delete -f /tmp/services.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "☸️ Failed to delete services"
                    return 1
                fi
            fi
        else
            docker compose -f /tmp/services.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to stop dockerized services"
                return 1
            fi
        fi
        rm -f /tmp/services.yml
    fi

    if [ -f geckodriver.log ] ; then
        rm -f geckodriver.log
    fi

    database=$(redis_cli get database)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$database" ] ; then
        log "START" "⚠️" "💽 Failed to get database from redis server, clearing all database just in case"
        database="error"
    fi

    need_socket=$(redis_cli get need_socket)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        need_socket=0
    fi

    if [ "$integration" != "Kubernetes" ] ; then
        containers=$(docker ps -a --format "{{.Names}}")
        if echo "$containers" | grep -q "redis-sentinel-1" ; then
            docker compose -f tests/misc/docker/sentinel.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to stop sentinel stack"
                return 1
            fi
        fi

        if echo "$containers" | grep -q "redis-master" ; then
            docker compose -f tests/misc/docker/redis-master.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to stop redis-master"
                return 1
            fi
        fi

        if echo "$containers" | grep -q "valkey" ; then
            docker compose -f tests/misc/docker/valkey.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to stop valkey"
                return 1
            fi
        fi

        if echo "$containers" | grep -q "valkey-sentinel-1" ; then
            docker compose -f tests/misc/docker/valkey-sentinel.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to stop valkey-sentinel stack"
                return 1
            fi
        fi
    else
        redis_secrets=$(kubectl get secrets -n redis -o jsonpath='{.items[*].metadata.name}')
        if echo "$redis_secrets" | grep -q "redis-master-secret" ; then
            kubectl delete -f /tmp/redis-master-secrets.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete redis-master secrets"
                return 1
            fi
        fi

        if echo "$redis_secrets" | grep -q "valkey-slave-secret" ; then
            kubectl delete -f /tmp/valkey-slave-secrets.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete valkey-slave secrets"
                return 1
            fi
        fi

        if echo "$redis_secrets" | grep -q "valkey-sentinel-secret" ; then
            kubectl delete -f /tmp/valkey-sentinel-secrets.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete valkey-sentinel secrets"
                return 1
            fi
        fi

        if echo "$redis_secrets" | grep -q "redis-slave-secret" ; then
            kubectl delete -f /tmp/redis-slave-secrets.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete redis-slave secrets"
                return 1
            fi
        fi

        if echo "$redis_secrets" | grep -q "redis-sentinel-secret" ; then
            kubectl delete -f /tmp/redis-sentinel-secrets.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete redis-sentinel secrets"
                return 1
            fi
        fi

        redis_pods=$(kubectl get pods -n redis -o jsonpath='{.items[*].metadata.name}')
        if echo "$redis_pods" | grep -q "redis-sentinel-" ; then
            kubectl delete -f tests/misc/k8s/redis-sentinel.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to delete redis-sentinel stack"
                return 1
            fi
        fi

        if echo "$redis_pods" | grep -q "redis-master-" ; then
            kubectl delete -f tests/misc/k8s/redis-master.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to delete redis-master"
                return 1
            fi
        fi

        if echo "$redis_pods" | grep -q "valkey-sentinel-" ; then
            kubectl delete -f tests/misc/k8s/valkey-sentinel.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to delete valkey-sentinel"
                return 1
            fi
        elif echo "$redis_pods" | grep -q "valkey-" ; then
            kubectl delete -f tests/misc/k8s/valkey.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🧰 Failed to delete valkey"
                return 1
            fi
        fi

        db_pods=$(kubectl get pods -n bunkerweb-db -o jsonpath='{.items[*].metadata.name}')
        if echo "$db_pods" | grep -q "bunkerweb-db-" ; then
            if [ "$database" == "error" ] ; then
                kubectl delete -f tests/misc/k8s/mariadb.yml
                kubectl delete -f tests/misc/k8s/mysql.yml
                kubectl delete -f tests/misc/k8s/postgresql.yml
                kubectl delete -f tests/misc/k8s/oracle.yml
            elif [ "$database" != "sqlite" ] ; then
                kubectl delete -f tests/misc/k8s/"$database".yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "☸️ Failed to delete $database"
                    return 1
                fi
            fi
        fi
    fi

    if [ "$exit_code" -ne 0 ] || ($trapped && [ "$exit_code" -eq 0 ] && [ "$(basename "$0")" == "run.sh" ]) ; then
        if [ "$integration" == "Kubernetes" ] ; then
            pods=$(kubectl get pods -n misc -o jsonpath='{.items[*].metadata.name}')
            if echo "$pods" | grep -q "custom-api-" ; then
                kubectl delete -f tests/misc/k8s/custom-api.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🔧 Failed to delete custom-api"
                    return 1
                fi
            fi

            minikube_cmd_pids=$(redis_cli lrange minikube_cmd_pids 0 -1)
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "💽 Failed to get Minikube command pids from redis server"
            fi

            if [ -n "$minikube_cmd_pids" ] ; then
                for pid in $minikube_cmd_pids ; do
                    sudo kill -9 "$pid"
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "UTILS" "❌" "🛑 Failed to kill Minikube command with pid: $pid"
                    fi
                done
                redis_cli del minikube_cmd_pids > /dev/null
            fi

            minikube_mount_logs=$(ls /tmp/minikube_mount_*.log)
            if [ -n "$minikube_mount_logs" ] ; then
                for log_file in $minikube_mount_logs ; do
                    rm -f "$log_file"
                done
            fi
        else
            docker compose -f tests/misc/docker/custom-api.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🔧 Failed to stop custom-api"
                return 1
            fi

            docker compose -f tests/misc/docker/php.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐘 Failed to stop php"
                return 1
            fi

            docker compose -f tests/misc/docker/dnsmasq.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🤿 Failed to stop dnsmasq"
                return 1
            fi

            containers=$(docker ps -a --format "{{.Names}}")
            if echo "$containers" | grep -q "syslog" ; then
                docker compose -f tests/misc/docker/syslog.yml down -v
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "💬 Failed to stop syslog"
                    return 1
                fi
            fi

            if echo "$containers" | grep -q "crowdsec" ; then
                docker compose -f tests/misc/docker/crowdsec.yml down -v
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🦙 Failed to stop CrowdSec"
                    return 1
                fi
            fi
        fi

        if [ "$integration" == "Linux" ] ; then
            if ! grep -q "server=127.0.0.11" tests/misc/conf/dnsmasq.conf ; then
                sed_in_place '18i\server=127.0.0.11' tests/misc/conf/dnsmasq.conf
            fi
            sed_in_place 's/127\.0\.0\.1 dnsmasq/10.20.30.20 dnsmasq/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 custom-api/10.20.30.30 custom-api/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 php-fpm/10.20.30.40 php-fpm/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 redis$/10.20.30.50 redis/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 redis-master$/10.20.30.51 redis-master/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 redis-slave-1$/10.20.30.52 redis-slave-1/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 redis-slave-2$/10.20.30.53 redis-slave-2/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 redis-sentinel-1$/10.20.30.54 redis-sentinel-1/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 redis-sentinel-2$/10.20.30.55 redis-sentinel-2/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 redis-sentinel-3$/10.20.30.56 redis-sentinel-3/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 crowdsec$/10.20.30.60 crowdsec/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 valkey$/10.20.30.70 valkey/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 valkey-slave-1$/10.20.30.62 valkey-slave-1/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 valkey-slave-2$/10.20.30.63 valkey-slave-2/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 valkey-sentinel-1$/10.20.30.64 valkey-sentinel-1/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 valkey-sentinel-2$/10.20.30.65 valkey-sentinel-2/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 valkey-sentinel-3$/10.20.30.66 valkey-sentinel-3/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 syslog$/10.20.30.254 syslog/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 bw-ui/10.20.30.25 bw-ui/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 bw-api/10.20.30.26 bw-api/g' tests/misc/conf/dnsmasq.hosts
            sed_in_place 's/127\.0\.0\.1 bw-db/10.10.10.254 bw-db/g' tests/misc/conf/dnsmasq.hosts

            sed_in_place 's@/run/php/php-fpm.sock@9000@g' tests/misc/conf/php-fpm.conf
            sed_in_place 's/^listen.group =.*$/listen.group = nginx/g' tests/misc/conf/php-fpm.conf
            # Undo the numeric ids the Linux run substitutes: every other integration talks to
            # this helper over TCP and lets it keep its own www-data.
            sed_in_place 's/^user =.*$/user = www-data/g' tests/misc/conf/php-fpm.conf
            sed_in_place 's/^group =.*$/group = www-data/g' tests/misc/conf/php-fpm.conf
            sed_in_place 's/^listen.owner =.*$/listen.owner = www-data/g' tests/misc/conf/php-fpm.conf
        fi

        docker compose -f tests/misc/docker/redis.yml down -v --remove-orphans
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "💽 Failed to stop redis"
            return 1
        fi

        docker network prune -f
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to prune networks"
            return 1
        fi

        docker volume prune -f
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to prune volumes"
            return 1
        fi
    fi

    if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Docker" ] ; then
        # Example-backed run on Docker: one compose project holds the whole stack.
        example_stack="$(cat /tmp/example_stack.txt)"
        example_hook cleanup "$integration"
        docker compose -f "$example_stack" down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "📕 Failed to stop the example stack"
            return 1
        fi
    elif [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
        if [ -f /tmp/example_stack.txt ] ; then
            # The example only added its application layer on top of the stack below.
            example_stack="$(cat /tmp/example_stack.txt)"
            example_hook cleanup "$integration"
            docker compose -f "$example_stack" down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "📕 Failed to stop the example services"
                return 1
            fi
        fi

        docker compose -f tests/docker/docker-compose.bunkerweb.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to stop BunkerWeb"
            return 1
        fi

        docker compose -f tests/docker/docker-compose.scheduler.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to stop BunkerWeb Scheduler"
            return 1
        fi

        if [ "$integration" == "Autoconf" ] ; then
            docker compose -f tests/docker/docker-compose.autoconf.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🔩 Failed to stop BunkerWeb Autoconf"
                return 1
            fi

            docker compose -f tests/misc/docker/docker-socket-proxy.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Failed to stop Docker Socket Proxy"
                return 1
            fi
        fi

        if [ "$type" == "ui" ] ; then
            docker compose -f tests/docker/docker-compose.ui.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to stop BunkerWeb UI"
                return 1
            fi
        fi

        # API, worker and broker are in every stack since 1.7, so they come down for
        # every type too.
        docker compose -f tests/docker/docker-compose.worker.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to stop BunkerWeb worker"
            return 1
        fi

        docker compose -f tests/docker/docker-compose.api.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to stop BunkerWeb API"
            return 1
        fi

        containers=$(docker ps -a --format "{{.Names}}")
        if echo "$containers" | grep -q "syslog" ; then
            docker compose -f tests/misc/docker/syslog.yml exec syslog truncate -s 0 /var/log/bunkerweb/bunkerweb.log
        fi

        if echo "$containers" | grep -q "crowdsec" ; then
            docker compose -f tests/misc/docker/crowdsec.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🦙 Failed to stop CrowdSec"
                return 1
            fi

            redis_cli set restart_crowdsec 1
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "💽 Failed to set restart_crowdsec key in redis server"
                return 1
            fi
        fi
    elif [ "$integration" == "All-in-one" ] ; then
        docker compose -f tests/docker/docker-compose.all-in-one.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🍱 Failed to stop BunkerWeb All-in-one"
            return 1
        fi

        if [ "$need_socket" == "1" ] ; then
            docker compose -f tests/misc/docker/docker-socket-proxy.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Failed to stop Docker Socket Proxy"
                exit 1
            fi
        fi
    elif [ "$integration" == "Kubernetes" ] ; then
        bw_pods=$(kubectl get pods -n bunkerweb -o jsonpath='{.items[*].metadata.name}')
        if echo "$bw_pods" | grep -q "bunkerweb-controller-" ; then
            kubectl delete -f tests/k8s/bunkerweb.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete BunkerWeb"
                return 1
            fi
        fi

        services=$(kubectl get svc -n bunkerweb -o jsonpath='{.items[*].metadata.name}')
        if echo "$services" | grep -q "svc-bw-lb" ; then
            kubectl delete -f tests/misc/k8s/lb.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete lb"
                return 1
            fi
        fi

        secrets=$(kubectl get secrets -n bunkerweb -o jsonpath='{.items[*].metadata.name}')
        if echo "$secrets" | grep -q "bw-secret" ; then
            kubectl delete -f /tmp/secrets.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete secrets"
                return 1
            fi
        fi

        if [ "$type" == "ui" ] ; then
            if echo "$secrets" | grep -q "bw-ui-secret" ; then
                kubectl delete -f /tmp/secrets-ui.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "☸️ Failed to delete UI secrets"
                    return 1
                fi
            fi
        elif [ "$type" == "api" ] ; then
            if echo "$secrets" | grep -q "bw-api-secret" ; then
                kubectl delete -f /tmp/secrets-api.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "☸️ Failed to delete API secrets"
                    return 1
                fi
            fi
        fi
    elif [ "$integration" == "Linux" ] && ! $IS_FREEBSD ; then
        # An example that put something in front of BunkerWeb has to take it away again: the
        # container is reused by every spec of the run, so an haproxy still listening on :80
        # answers for the next one, which then tests haproxy. Only two examples ship a
        # cleanup-linux.sh; the hook is a no-op for the rest.
        example_hook cleanup "$integration" || return 1

        docker exec -u 0 bunkerweb-linux systemctl stop bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐧 Failed to stop BunkerWeb service"
            return 1
        fi

        docker exec -u 0 bunkerweb-linux systemctl stop bunkerweb-scheduler
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐧 Failed to stop BunkerWeb Scheduler service"
            return 1
        fi

        # The API and the worker belong to every 1.7 stack, so they are stopped for every type:
        # a survivor keeps serving the previous action's configuration, and the API keeps the
        # token it read at startup — which the next action's variables.env has replaced.
        for unit in bunkerweb-api bunkerweb-worker ; do
            docker exec -u 0 bunkerweb-linux systemctl stop "$unit"
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐧 Failed to stop $unit service"
                return 1
            fi
        done

        if [ "$type" == "ui" ] ; then
            docker exec -u 0 bunkerweb-linux systemctl stop bunkerweb-ui
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐧 Failed to stop BunkerWeb UI service"
                return 1
            fi
        fi

        docker exec -u 0 bunkerweb-linux bash -c "rm -rf /var/tmp/bunkerweb/*"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗄 Failed to remove BunkerWeb tmp dir"
            return 1
        fi

        docker exec -u 0 bunkerweb-linux bash -c "rm -rf /var/lib/bunkerweb/*"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗄 Failed to remove BunkerWeb database"
            return 1
        fi

        docker exec -u 0 bunkerweb-linux bash -c "rm -rf /var/cache/bunkerweb/*"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗑 Failed to remove BunkerWeb cache"
            return 1
        fi

        docker exec -u 0 bunkerweb-linux bash -c "rm -rf /etc/bunkerweb/plugins/*"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗑 Failed to remove BunkerWeb plugins dir"
            return 1
        fi

        docker exec -u 0 bunkerweb-linux bash -c "rm -rf /etc/bunkerweb/pro/plugins/*"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗑 Failed to remove BunkerWeb pro dir"
            return 1
        fi

        docker exec -u 0 bunkerweb-linux journalctl --rotate --vacuum-time=1s
        docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/error.log
        docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/access.log
        docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/scheduler.log
        if [ "$type" == "ui" ] ; then
            docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/ui.log
            docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/ui-access.log
        elif [ "$type" == "api" ] ; then
            docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/api.log
            docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/api-access.log
        fi

        # Remove any temporary kustomize directory
        if [ -d /tmp/kustomize-bunkerweb ] ; then
            rm -rf /tmp/kustomize-bunkerweb
        fi
    elif [ "$integration" == "Linux" ] && $IS_FREEBSD ; then
        service bunkerweb stop
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐚 Failed to stop BunkerWeb service"
            return 1
        fi

        service bunkerweb_scheduler stop
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐚 Failed to stop BunkerWeb Scheduler service"
            return 1
        fi

        if [ "$type" == "ui" ] ; then
            service bunkerweb_ui stop
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐚 Failed to stop BunkerWeb UI service"
                return 1
            fi
        elif [ "$type" == "api" ] ; then
            service bunkerweb_api stop
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐚 Failed to stop BunkerWeb API service"
                return 1
            fi
        fi

        rm -rf /var/tmp/bunkerweb/*
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗄 Failed to remove BunkerWeb tmp dir"
            return 1
        fi

        rm -rf /var/lib/bunkerweb/*
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗄 Failed to remove BunkerWeb database"
            return 1
        fi

        rm -rf /var/cache/bunkerweb/*
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗑 Failed to remove BunkerWeb cache"
            return 1
        fi

        rm -rf /etc/bunkerweb/plugins/*
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗑 Failed to remove BunkerWeb plugins dir"
            return 1
        fi

        rm -rf /etc/bunkerweb/pro/plugins/*
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🗑 Failed to remove BunkerWeb pro dir"
            return 1
        fi

        truncate -s 0 /var/log/bunkerweb/error.log
        truncate -s 0 /var/log/bunkerweb/access.log
        truncate -s 0 /var/log/bunkerweb/scheduler.log
        if [ "$type" == "ui" ] ; then
            truncate -s 0 /var/log/bunkerweb/ui.log
            truncate -s 0 /var/log/bunkerweb/ui-access.log
        elif [ "$type" == "api" ] ; then
            truncate -s 0 /var/log/bunkerweb/api.log
            truncate -s 0 /var/log/bunkerweb/api-access.log
        fi

        # Remove any temporary kustomize directory
        if [ -d /tmp/kustomize-bunkerweb ] ; then
            rm -rf /tmp/kustomize-bunkerweb
        fi

        # bw-storage is created by start.sh outside any compose project, so `down -v` never
        # touches it and `docker volume prune` skips it (named, not anonymous). It holds the
        # SQLite database, so leaving it makes a full clean a lie: the next spec starts on the
        # previous one's global settings. That is how a `valkey` run left REDIS_HOST=valkey
        # behind and the following stack's API answered 500 to every /ping, waiting on a host
        # that no longer existed. CI never saw it -- one runner per spec.
        if [ "$integration" != "Kubernetes" ] && docker volume inspect bw-storage > /dev/null 2>&1 ; then
            docker volume rm -f bw-storage > /dev/null
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to remove the bw-storage volume"
                return 1
            fi
        fi
    fi

    if [ "$integration" != "Kubernetes" ] ; then
        if [ "$database" == "error" ] ; then
            docker compose -f tests/misc/docker/mariadb.yml down -v
            docker compose -f tests/misc/docker/mysql.yml down -v
            docker compose -f tests/misc/docker/postgresql.yml down -v
            docker compose -f tests/misc/docker/oracle.yml down -v
        elif [ "$database" != "sqlite" ] ; then
            docker compose -f tests/misc/docker/"$database".yml down -v
        fi

        networks=$(docker network ls --format "{{.Name}}")
        if echo "$networks" | grep -q "bw-db" ; then
            docker network rm bw-db
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to remove bw-db network"
                return 1
            fi
        fi
    fi

    log "UTILS" "ℹ️ " "🧹 Cleaned up current stack ✅"
}

function restart_stack () {
    # A Docker example ships the whole stack, so the containers to restart are its own --
    # and they carry the same names (bunkerweb, bw-scheduler) in a different compose project.
    # Restarting the framework's composes here made docker refuse with "container name
    # /bw-scheduler is already in use", which is how the second action of every Docker
    # example spec failed.
    if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Docker" ] ; then
        local example_stack
        example_stack="$(cat /tmp/example_stack.txt)"
        log "UTILS" "ℹ️ " "📕 Restarting the example stack from $example_stack ..."
        docker compose -f "$example_stack" down
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "📕 Down failed for the example stack"
            return 1
        fi
        example_hook setup "$integration" || return 1
        compose_up "$example_stack" "example stack" "📕" || return 1
        # The framework path clears these on its way out; an example restart is always a whole
        # one, but leave the flags as the next action expects to find them.
        redis_cli set restart_whole_stack 0 > /dev/null
        redis_cli set restart_services 0 > /dev/null
        return 0
    fi

    restart_whole_stack=$(redis_cli get restart_whole_stack)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$restart_whole_stack" ] ; then
        log "UTILS" "❌" "💽 Failed to get restart_whole_stack from redis server"
        return 1
    fi

    restart_services=$(redis_cli get restart_services)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$restart_services" ] ; then
        log "UTILS" "❌" "💽 Failed to get restart_services from redis server"
        return 1
    fi

    if [ "$restart_whole_stack" -eq 1 ] ; then
        log "UTILS" "ℹ️ " "🔄 Restarting whole stack due to version change ..."
    else
        log "UTILS" "ℹ️ " "🔄 Restarting current stack ..."
    fi

    database=$(redis_cli get database)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$database" ] ; then
        log "UTILS" "⚠️" "💽 Failed to get database from redis server, defaulting to sqlite"
        database="sqlite"
    fi

    if [ "$database" != "sqlite" ] ; then
        if [ "$integration" == "Kubernetes" ] ; then
            log "UTILS" "ℹ️ " "☸️ Ensuring $database database is running ..."
            kubectl apply -f tests/misc/k8s/"$database".yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Apply failed for $database"
                return 1
            fi
        else
            expected_image=""
            case "$database" in
                mariadb) expected_image="mariadb:11" ;;
                mysql) expected_image="mysql:9" ;;
                postgresql) expected_image="postgres:17-alpine" ;;
                oracle) expected_image="gvenzl/oracle-free:23-slim-faststart" ;;
            esac

            existing_image=$(docker inspect -f '{{.Config.Image}}' bw-db 2>/dev/null || true)
            # The compose files pin the engine by digest, so this reports `mariadb:11@sha256:...`
            # while expected_image is the bare tag above. Comparing them raw never matched, and
            # the mismatch branch below destroys the database VOLUME -- so every single restart
            # silently wiped the database. The stack then desynchronized: bw-autoconf is only
            # restarted when restart_whole_stack is set, so on an ordinary action it kept its
            # in-memory "already applied" state, never re-registered the instance into the fresh
            # database, and push-configs had nobody to push to while the instance went on serving
            # its pre-restart configuration. Compare on the tag, which is what this check means.
            existing_image="${existing_image%%@*}"
            if [ -n "$existing_image" ] && [ -n "$expected_image" ] && [ "$existing_image" != "$expected_image" ] ; then
                log "UTILS" "⚠️" "💽 bw-db image is $existing_image, expected $expected_image. Recreating database container ..."
                docker compose -f tests/misc/docker/"$database".yml down -v
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "⚠️" "🐳 Down failed for $database, forcing removal ..."
                    docker rm -f bw-db > /dev/null 2>&1 || true
                fi
                existing_image=""
            fi

            if [ -z "$existing_image" ] ; then
                robust_docker_pull "tests/misc/docker/$database.yml" "$database"
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐳 Pull failed for $database after multiple attempts"
                    return 1
                fi
            fi

            docker compose -f tests/misc/docker/"$database".yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "⚠️" "🐳 Up failed for $database, retrying ..."
                docker compose -f tests/misc/docker/"$database".yml down -v
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐳 Down failed for $database"
                    return 1
                fi
                docker compose -f tests/misc/docker/"$database".yml up -d
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐳 Up failed for $database"
                    return 1
                fi
            fi
        fi
    fi

    BW_VERSION="$(cat /tmp/bw_version.txt)"
    export BW_VERSION

    if [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
        if [ "$restart_whole_stack" -eq 1 ] ; then
            docker compose -f tests/docker/docker-compose.bunkerweb.yml down
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to stop BunkerWeb"
                return 1
            fi

            docker compose -f tests/docker/docker-compose.bunkerweb.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to start BunkerWeb"
                return 1
            fi

            if [ "$integration" == "Autoconf" ] ; then
                docker compose -f tests/docker/docker-compose.autoconf.yml down
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🔩 Failed to stop BunkerWeb Autoconf"
                    return 1
                fi

                docker compose -f tests/docker/docker-compose.autoconf.yml up -d
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🔩 Failed to start BunkerWeb Autoconf"
                    return 1
                fi
            fi
        fi

        docker compose -f tests/docker/docker-compose.scheduler.yml down
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to stop BunkerWeb Scheduler"
            return 1
        fi

        docker compose -f tests/docker/docker-compose.scheduler.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🐳 Failed to start BunkerWeb Scheduler"
            return 1
        fi

        if [ "$type" == "ui" ] ; then
            docker compose -f tests/docker/docker-compose.ui.yml down
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to stop BunkerWeb UI"
                return 1
            fi

            docker compose -f tests/docker/docker-compose.ui.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to start BunkerWeb UI"
                return 1
            fi
        fi

        # The API and the worker restart with the rest of the stack whatever the type:
        # a restarted scheduler dispatches into an API that must have reloaded too.
        for _component in api worker ; do
            docker compose -f "tests/docker/docker-compose.${_component}.yml" down
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to stop BunkerWeb ${_component}"
                return 1
            fi

            docker compose -f "tests/docker/docker-compose.${_component}.yml" up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to start BunkerWeb ${_component}"
                return 1
            fi
        done

        restart_dockerized_services=0
        if [ "$integration" == "Autoconf" ] || [ "$restart_services" -eq 1 ] ; then
            restart_dockerized_services=1
        fi

        if [ -f /tmp/services.yml ] && [ "$restart_dockerized_services" -eq 1 ] ; then
            robust_docker_pull "/tmp/services.yml" "dockerized services"
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Pull failed for dockerized services after multiple attempts"
                return 1
            fi

            docker compose -f /tmp/services.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to stop dockerized services"
                return 1
            fi

            docker compose -f /tmp/services.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to start dockerized services"
                return 1
            fi
        fi

        containers=$(docker ps -a --format "{{.Names}}")
        if echo "$containers" | grep -q "syslog" ; then
            docker compose -f tests/misc/docker/syslog.yml exec syslog truncate -s 0 /var/log/bunkerweb/bunkerweb.log
        fi

        if echo "$containers" | grep -q "crowdsec" ; then
            docker compose -f tests/misc/docker/crowdsec.yml down
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🦙 Failed to stop CrowdSec"
                return 1
            fi

            docker compose -f tests/misc/docker/crowdsec.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🦙 Failed to start CrowdSec"
                return 1
            fi
        fi
    elif [ "$integration" == "All-in-one" ] ; then
        docker compose -f tests/docker/docker-compose.all-in-one.yml down
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🍱 Failed to stop BunkerWeb All-in-one"
            return 1
        fi

        # Through compose_up rather than a bare `up -d`: the `down` above tears the stack's
        # networks down asynchronously while other containers (dnsmasq, php-fpm, the services)
        # still hold them, and the removal can land *after* `up` has recreated them -- the
        # container then fails to start with "could not find a network matching network mode
        # bw-db". One retry through a full `down -v` clears it.
        compose_up "tests/docker/docker-compose.all-in-one.yml" "BunkerWeb All-in-one" "🍱" || return 1
    elif [ "$integration" == "Kubernetes" ] ; then
        secrets=$(kubectl get secrets -n bunkerweb -o jsonpath='{.items[*].metadata.name}')
        if echo "$secrets" | grep -q "bw-secret" ; then
            kubectl delete -f /tmp/secrets.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete secrets"
                return 1
            fi
        fi

        kubectl apply -f /tmp/secrets.yml
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "☸️ Failed to apply secrets"
            return 1
        fi

        # If the whole stack must be restarted due to a version change,
        # re-apply manifests with the correct tag using Kustomize
        if [ "$restart_whole_stack" -eq 1 ] ; then
            BW_VERSION="$(cat /tmp/bw_version.txt)"
            export BW_VERSION

            KZ_DIR="/tmp/kustomize-bunkerweb"
            rm -rf "$KZ_DIR"
            mkdir -p "$KZ_DIR"

            if [ "$BW_VERSION" == "tests" ] ; then
                NEW_PREFIX="localhost:5000/bunkerity"
                NEW_TAG="tests"
            else
                NEW_PREFIX="bunkerity"
                NEW_TAG="$BW_VERSION"
            fi

            # Copy resources locally because kustomize forbids absolute paths from outside the root
            cp tests/k8s/bunkerweb.yml "$KZ_DIR/bunkerweb.yml"
            if [ "$type" == "ui" ] ; then
                cp tests/k8s/bunkerweb-ui.yml "$KZ_DIR/bunkerweb-ui.yml"
            elif [ "$type" == "api" ] ; then
                cp tests/k8s/bunkerweb-api.yml "$KZ_DIR/bunkerweb-api.yml"
            fi

            {
                echo "resources:";
                echo "- bunkerweb.yml";
                if [ "$type" == "ui" ] ; then
                    echo "- bunkerweb-ui.yml";
                elif [ "$type" == "api" ] ; then
                    echo "- bunkerweb-api.yml";
                fi
                echo "images:";
                echo "- name: localhost:5000/bunkerity/bunkerweb";
                echo "  newName: ${NEW_PREFIX}/bunkerweb";
                echo "  newTag: ${NEW_TAG}";
                echo "- name: localhost:5000/bunkerity/bunkerweb-autoconf";
                echo "  newName: ${NEW_PREFIX}/bunkerweb-autoconf";
                echo "  newTag: ${NEW_TAG}";
                echo "- name: localhost:5000/bunkerity/bunkerweb-scheduler";
                echo "  newName: ${NEW_PREFIX}/bunkerweb-scheduler";
                echo "  newTag: ${NEW_TAG}";
                if [ "$type" == "ui" ] ; then
                    echo "- name: localhost:5000/bunkerity/bunkerweb-ui";
                    echo "  newName: ${NEW_PREFIX}/bunkerweb-ui";
                    echo "  newTag: ${NEW_TAG}";
                elif [ "$type" == "api" ] ; then
                    echo "- name: localhost:5000/bunkerity/bunkerweb-api";
                    echo "  newName: ${NEW_PREFIX}/bunkerweb-api";
                    echo "  newTag: ${NEW_TAG}";
                fi
            } > "$KZ_DIR/kustomization.yaml"

            kubectl apply -k "$KZ_DIR"
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to apply kustomized manifests"
                return 1
            fi

            # Cleanup temporary kustomize directory
            rm -rf "$KZ_DIR"
        fi

        kubectl rollout restart -n bunkerweb deployment bunkerweb-scheduler
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "☸️ Failed to restart BunkerWeb Scheduler"
            return 1
        fi

        if [ "$type" == "ui" ] ; then
            if echo "$secrets" | grep -q "bw-ui-secret" ; then
                kubectl delete -f /tmp/secrets-ui.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "☸️ Failed to delete UI secrets"
                    return 1
                fi
            fi

            kubectl apply -f /tmp/secrets-ui.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to apply UI secrets"
                return 1
            fi

            kubectl rollout restart -n bunkerweb deployment bunkerweb-ui
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to restart BunkerWeb UI"
                return 1
            fi
        elif [ "$type" == "api" ] ; then
            if echo "$secrets" | grep -q "bw-api-secret" ; then
                kubectl delete -f /tmp/secrets-api.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "☸️ Failed to delete API secrets"
                    return 1
                fi
            fi

            kubectl apply -f /tmp/secrets-api.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to apply API secrets"
                return 1
            fi

            kubectl rollout restart -n bunkerweb deployment bunkerweb-api
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to restart BunkerWeb API"
                return 1
            fi
        fi

        if [ -f /tmp/services.yml ] ; then
            kubectl delete -f /tmp/services.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to delete services"
                return 1
            fi

            kubectl apply -f /tmp/services.yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "☸️ Failed to apply services"
                return 1
            fi
        fi

        sleep 5
    else
        if $IS_FREEBSD ; then
            truncate -s 0 /var/log/bunkerweb/error.log
            truncate -s 0 /var/log/bunkerweb/access.log
            truncate -s 0 /var/log/bunkerweb/scheduler.log
            if [ "$type" == "ui" ] ; then
                truncate -s 0 /var/log/bunkerweb/ui.log
                truncate -s 0 /var/log/bunkerweb/ui-access.log
            elif [ "$type" == "api" ] ; then
                truncate -s 0 /var/log/bunkerweb/api.log
                truncate -s 0 /var/log/bunkerweb/api-access.log
            fi

            service bunkerweb_scheduler restart
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐚 Failed to restart BunkerWeb Scheduler service"
                return 1
            fi

            if [ "$type" == "ui" ] ; then
                service bunkerweb_ui restart
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐚 Failed to restart BunkerWeb UI service"
                    return 1
                fi
            elif [ "$type" == "api" ] ; then
                service bunkerweb_api restart
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐚 Failed to restart BunkerWeb API service"
                    return 1
                fi
            fi
        else
            docker exec -u 0 bunkerweb-linux journalctl --rotate --vacuum-time=1s
            docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/error.log
            docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/access.log
            docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/scheduler.log
            if [ "$type" == "ui" ] ; then
                docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/ui.log
                docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/ui-access.log
            elif [ "$type" == "api" ] ; then
                docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/api.log
                docker exec -u 0 bunkerweb-linux truncate -s 0 /var/log/bunkerweb/api-access.log
            fi

            # if [ "$restart_whole_stack" -eq 1 ] ; then
            #     # TODO
            # fi

            apply_example_variables_env || return 1

            # API and worker first: they read the shared API_TOKEN out of variables.env at
            # startup, and the scheduler's first authenticated call happens as soon as it comes
            # up. Restarting them after it would leave the scheduler talking to a process still
            # holding the previous action's token, which the client reports as a read-only
            # database rather than as an authentication failure.
            for unit in bunkerweb-api bunkerweb-worker ; do
                docker exec -u 0 bunkerweb-linux systemctl restart "$unit"
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐧 Failed to restart $unit service"
                    return 1
                fi
            done

            docker exec -u 0 bunkerweb-linux systemctl restart bunkerweb-scheduler
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐧 Failed to restart BunkerWeb Scheduler service"
                return 1
            fi

            if [ "$type" == "ui" ] ; then
                docker exec -u 0 bunkerweb-linux systemctl restart bunkerweb-ui
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐧 Failed to restart BunkerWeb UI service"
                    return 1
                fi
            fi
        fi

        if [ -f /tmp/services.yml ] && [ "$restart_services" -eq 1 ] ; then
            robust_docker_pull "/tmp/services.yml" "dockerized services"
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Pull failed for dockerized services after multiple attempts"
                return 1
            fi

            docker compose -f /tmp/services.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to stop dockerized services"
                return 1
            fi

            docker compose -f /tmp/services.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐳 Failed to start dockerized services"
                return 1
            fi
        fi
    fi

    if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Autoconf" ] ; then
        # generate.py re-materialises the example for every action, which deletes and recreates
        # /tmp/example-stack. Containers that keep running hold the old, now-unlinked directory:
        # their bind mount stays valid and stays empty, so php-fpm answers "Primary script
        # unknown" and BunkerWeb returns 404 for an application that is plainly there on disk.
        # Recreate them against the directory that exists now. Docker examples get the same
        # treatment at the top of this function; Kubernetes copies the files into the cluster.
        local example_stack
        example_stack="$(cat /tmp/example_stack.txt)"
        log "UTILS" "ℹ️ " "📕 Restarting the example services from $example_stack ..."
        docker compose -f "$example_stack" down
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "📕 Down failed for the example services"
            return 1
        fi
        example_hook setup "$integration" || return 1
        compose_up "$example_stack" "example services" "📕" || return 1
    fi

    if [ -f geckodriver.log ] ; then
        rm -f geckodriver.log
    fi

    if [ "$restart_whole_stack" -eq 1 ] ; then
        log "UTILS" "ℹ️ " "🔄 Restarted whole stack due to version change ✅"
    else
        log "UTILS" "ℹ️ " "🔄 Restarted current stack ✅"
    fi

    redis_cli set restart_whole_stack 0 > /dev/null
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "UTILS" "❌" "💽 Failed to reset restart_whole_stack in redis server"
        return 1
    fi

    redis_cli set restart_services 0 > /dev/null
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "UTILS" "❌" "💽 Failed to reset restart_services in redis server"
        return 1
    fi
}

# shellcheck disable=SC2120
function log_stack () {
    service="${1:-}"
    if [ -n "$service" ] ; then
        log "UTILS" "ℹ️ " "📜 Showing $service logs ..."
    else
        log "UTILS" "ℹ️ " "📜 Showing stack logs ..."
    fi

    if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
        log "UTILS" "ℹ️ " "🔍 Following logs ..."
    fi

    # A Docker example ships its own compose project, so the framework's compose files hold no
    # container and every "Showing ... logs" heading printed an empty section -- which is how a
    # failed example run reached CI with no diagnosis at all.
    if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Docker" ] ; then
        local example_stack
        example_stack="$(cat /tmp/example_stack.txt)"
        command="logs"
        if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
            command="$command -f"
        fi
        # shellcheck disable=SC2086
        docker compose -f "$example_stack" $command
        return 0
    fi

    if [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] || [ "$integration" == "All-in-one" ] ; then
        command="logs"
        if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
            command="$command -f"
        fi

        if [ -n "$service" ] ; then
            # shellcheck disable=SC2086
            docker compose -f tests/docker/docker-compose."$service".yml $command
        else
            if [ "$command" == "logs -f" ] ; then
                if [ "$integration" == "All-in-one" ] ; then
                    # shellcheck disable=SC2086
                    docker compose -f tests/docker/docker-compose.all-in-one.yml $command
                else
                    # shellcheck disable=SC2086
                    docker compose -f tests/docker/docker-compose.bunkerweb.yml $command
                fi
            elif [ "$integration" == "All-in-one" ] ; then
                docker compose -f tests/docker/docker-compose.all-in-one.yml logs
            else
                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb logs ..."
                # shellcheck disable=SC2086
                docker compose -f tests/docker/docker-compose.bunkerweb.yml logs

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb Scheduler logs ..."
                # shellcheck disable=SC2086
                docker compose -f tests/docker/docker-compose.scheduler.yml logs

                if [ "$integration" == "Autoconf" ] ; then
                    log "UTILS" "ℹ️ " "📜 Showing BunkerWeb Autoconf logs ..."
                    # shellcheck disable=SC2086
                    docker compose -f tests/docker/docker-compose.autoconf.yml logs
                fi

                if [ "$type" == "ui" ] ; then
                    log "UTILS" "ℹ️ " "📜 Showing BunkerWeb UI logs ..."
                    # shellcheck disable=SC2086
                    docker compose -f tests/docker/docker-compose.ui.yml logs
                fi

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb API logs ..."
                # shellcheck disable=SC2086
                docker compose -f tests/docker/docker-compose.api.yml logs

                # A job that never ran is invisible in the scheduler logs since 1.7 —
                # the failure is in the worker or the broker.
                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb worker logs ..."
                # shellcheck disable=SC2086
                docker compose -f tests/docker/docker-compose.worker.yml logs
            fi
        fi

        if [ -n "$service" ] || ! $trapped && [ "$FOLLOW" == "yes" ] ; then
            return 0
        fi
    elif [ "$integration" == "Kubernetes" ] ; then
        if [ -n "$service" ] ; then
            if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
                kubectl logs -n bunkerweb -l app="$service" --tail=-1 -f
            else
                kubectl logs -n bunkerweb -l app="$service" --tail=-1
            fi
            return 0
        else
            if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
                kubectl logs -n bunkerweb -l app=bunkerweb --tail=-1 -f
                return 0
            else
                log "UTILS" "ℹ️ " "🪪 Description of BunkerWeb pods ..."
                kubectl describe pods -n bunkerweb -l app=bunkerweb

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb logs ..."
                kubectl logs -n bunkerweb -l app=bunkerweb --tail=-1

                log "UTILS" "ℹ️ " "🪪 Description of BunkerWeb Scheduler pods ..."
                kubectl describe pods -n bunkerweb -l app=bunkerweb-scheduler

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb Scheduler logs ..."
                kubectl logs -n bunkerweb -l app=bunkerweb-scheduler --tail=-1

                log "UTILS" "ℹ️ " "🪪 Description of BunkerWeb Controller pods ..."
                kubectl describe pods -n bunkerweb -l app=bunkerweb-controller

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb Controller logs ..."
                kubectl logs -n bunkerweb -l app=bunkerweb-controller --tail=-1

                log "UTILS" "ℹ️ " "🪪 Description of BunkerWeb DB pods ..."
                kubectl describe pods -n bunkerweb-db -l app=bunkerweb-db

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb DB logs ..."
                kubectl logs -n bunkerweb-db -l app=bunkerweb-db --tail=-1

                if [ "$type" == "ui" ] ; then
                    log "UTILS" "ℹ️ " "🪪 Description of BunkerWeb UI pods ..."
                    kubectl describe pods -n bunkerweb -l app=bunkerweb-ui

                    log "UTILS" "ℹ️ " "📜 Showing BunkerWeb UI logs ..."
                    kubectl logs -n bunkerweb -l app=bunkerweb-ui --tail=-1
                elif [ "$type" == "api" ] ; then
                    log "UTILS" "ℹ️ " "🪪 Description of BunkerWeb API pods ..."
                    kubectl describe pods -n bunkerweb -l app=bunkerweb-api

                    log "UTILS" "ℹ️ " "📜 Showing BunkerWeb API logs ..."
                    kubectl logs -n bunkerweb -l app=bunkerweb-api --tail=-1
                fi
            fi
        fi
    else
        if $IS_FREEBSD ; then
            log_file=""
            if [ -n "$service" ] ; then
                case "$service" in
                    bunkerweb)
                        log_file="/var/log/bunkerweb/error.log"
                        ;;
                    bunkerweb-scheduler|bunkerweb_scheduler|scheduler)
                        log_file="/var/log/bunkerweb/scheduler.log"
                        ;;
                    bunkerweb-ui|bunkerweb_ui|ui)
                        log_file="/var/log/bunkerweb/ui.log"
                        ;;
                    bunkerweb-api|bunkerweb_api|api)
                        log_file="/var/log/bunkerweb/api.log"
                        ;;
                esac

                if [ -n "$log_file" ] ; then
                    if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
                        tail -f "$log_file"
                    else
                        cat "$log_file"
                    fi
                    return 0
                fi

                service "$service" status
                return 0
            fi

            if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
                tail -f /var/log/bunkerweb/error.log
                return 0
            fi

            log "UTILS" "ℹ️ " "📜 Showing BunkerWeb Scheduler logs ..."
            cat /var/log/bunkerweb/scheduler.log

            log "UTILS" "ℹ️ " "📜 Showing BunkerWeb logs ..."
            cat /var/log/bunkerweb/error.log

            log "UTILS" "ℹ️ " "📜 Showing BunkerWeb access logs ..."
            cat /var/log/bunkerweb/access.log

            if [ "$type" == "ui" ] ; then
                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb UI logs ..."
                cat /var/log/bunkerweb/ui.log

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb UI access logs ..."
                cat /var/log/bunkerweb/ui-access.log
            elif [ "$type" == "api" ] ; then
                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb API logs ..."
                cat /var/log/bunkerweb/api.log

                log "UTILS" "ℹ️ " "📜 Showing BunkerWeb API access logs ..."
                cat /var/log/bunkerweb/api-access.log
            fi
        else
            if [ -n "$service" ] ; then
                if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
                    docker exec -u 0 bunkerweb-linux journalctl -u "$service" --no-pager -f
                else
                    docker exec -u 0 bunkerweb-linux journalctl -u "$service" --no-pager
                fi
                return 0
            else
                if ! $trapped && [ "$FOLLOW" == "yes" ] ; then
                    docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb --no-pager -f
                    return 0
                else
                    log "UTILS" "ℹ️ " "📜 Showing BunkerWeb Scheduler logs ..."
                    docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb-scheduler --no-pager
                    docker exec -u 0 bunkerweb-linux cat /var/log/bunkerweb/scheduler.log

                    log "UTILS" "ℹ️ " "📜 Showing BunkerWeb logs ..."
                    docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb --no-pager
                    docker exec -u 0 bunkerweb-linux cat /var/log/bunkerweb/error.log

                    log "UTILS" "ℹ️ " "📜 Showing BunkerWeb access logs ..."
                    docker exec -u 0 bunkerweb-linux cat /var/log/bunkerweb/access.log

                    if [ "$type" == "ui" ] ; then
                        log "UTILS" "ℹ️ " "📜 Showing BunkerWeb UI logs ..."
                        docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb-ui --no-pager
                        docker exec -u 0 bunkerweb-linux cat /var/log/bunkerweb/ui.log

                        log "UTILS" "ℹ️ " "📜 Showing BunkerWeb UI access logs ..."
                        docker exec -u 0 bunkerweb-linux cat /var/log/bunkerweb/ui-access.log
                    elif [ "$type" == "api" ] ; then
                        log "UTILS" "ℹ️ " "📜 Showing BunkerWeb API logs ..."
                        docker exec -u 0 bunkerweb-linux journalctl -u bunkerweb-api --no-pager
                        docker exec -u 0 bunkerweb-linux cat /var/log/bunkerweb/api.log

                        log "UTILS" "ℹ️ " "📜 Showing BunkerWeb API access logs ..."
                        docker exec -u 0 bunkerweb-linux cat /var/log/bunkerweb/api-access.log
                    fi
                fi
            fi
        fi
    fi

    if [ "$integration" == "Kubernetes" ] ; then
        misc_pods=$(kubectl get pods -n misc -o jsonpath='{.items[*].metadata.name}')
        if echo "$misc_pods" | grep -q "custom-api-" ; then
            log "UTILS" "ℹ️ " "🪪 Description of custom-api pods ..."
            kubectl describe pods -n misc -l app=custom-api

            log "UTILS" "ℹ️ " "🔧 Showing custom-api logs ..."
            kubectl logs -n misc -l app=custom-api --tail=-1
        fi

        minikube_mount_logs=$(ls /tmp/minikube_mount_*.log)
        if [ -n "$minikube_mount_logs" ] ; then
            for log_file in $minikube_mount_logs ; do
                log "UTILS" "ℹ️ " "Showing minikube $(echo "$log_file" | sed 's@/tmp/minikube_mount_\(.*\).log@\1@g' | tr '_' '/') mount logs ..."
                cat "$log_file"
            done
        fi
    else
        containers=$(docker ps -a --format "{{.Names}}")
        if echo "$containers" | grep -q "bw-db" ; then
            log "UTILS" "ℹ️ " "🐳 Showing database logs ..."
            docker logs bw-db
        fi

        if echo "$containers" | grep -q "custom-api" ; then
            log "UTILS" "ℹ️ " "🔧 Showing custom-api logs ..."
            docker logs custom-api
        fi

        if echo "$containers" | grep -q "php-fpm" ; then
            log "UTILS" "ℹ️ " "🐘 Showing php-fpm logs ..."
            docker logs php-fpm
        fi

        # if echo "$containers" | grep -q "dnsmasq" ; then
        #     log "UTILS" "ℹ️ " "🤿 Showing dnsmasq logs ..."
        #     docker logs dnsmasq
        # fi

        if echo "$containers" | grep -q "redis-master" ; then
            log "UTILS" "ℹ️ " "🐳 Showing redis-master logs ..."
            docker logs redis-master
        fi

        if echo "$containers" | grep -q "valkey" ; then
            log "UTILS" "ℹ️ " "🐳 Showing valkey logs ..."
            docker logs valkey
        fi

        if echo "$containers" | grep -q "redis-sentinel-1" ; then
            log "UTILS" "ℹ️ " "🐳 Showing sentinel logs ..."
            docker compose -f tests/misc/docker/sentinel.yml logs
        fi

        if echo "$containers" | grep -q "valkey-sentinel-1" ; then
            log "UTILS" "ℹ️ " "🐳 Showing valkey-sentinel logs ..."
            docker compose -f tests/misc/docker/valkey-sentinel.yml logs
        fi

        if echo "$containers" | grep -q "crowdsec" ; then
            log "UTILS" "ℹ️ " "🦙 Showing CrowdSec logs ..."
            docker compose -f tests/misc/docker/crowdsec.yml logs
        fi
    fi

    if [ -f geckodriver.log ] ; then
        log "UTILS" "ℹ️ " "🦎 Showing Geckodriver logs ..."
        cat geckodriver.log
    fi
}

function exit_wrapper() {
    exit_code=$?
    if [ "$exit_code" -eq 0 ] && [ "$(basename "$0")" != "run.sh" ] ; then
        return 0
    fi
    trapped=true

    end=$(redis_cli get end)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$end" ] ; then
        log "UTILS" "❌" "💽 Failed to get end flag from redis server, setting it to 0"
        end=0
    fi

    if [ -n "$category" ] && [ -f "tests/scripts/after/$category.sh" ] ; then
        log "UTILS" "ℹ️ " "🔧 Running after script for \"$category\" ..."

        chmod +x "tests/scripts/after/$category.sh"

        # shellcheck disable=SC1090
        ./tests/scripts/after/"$category".sh "$integration" "$release" "$category"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            # Exiting here skipped cleanup_stack, so a broken after script left the whole stack
            # running and the next spec inherited its containers and networks. Keep the failure,
            # tear the stack down anyway.
            log "UTILS" "❌" "🔧 After script for \"$category\" failed"
            exit_code=1
            after_failed=true
        fi
    fi

    if [ "$end" -eq 0 ] && [ -z "${NO_LOG:-}" ]; then
        log_stack
    fi
    cleanup_stack "$exit_code"

    if ${after_failed:-false} ; then
        exit 1
    fi
}

if [ "$(basename "$0")" != "stop.sh" ] && [ "$(basename "$0")" != "log.sh" ] && [ "$(basename "$0")" != "test.sh" ] ; then
    # show logs and cleanup stack on exit
    trap exit_wrapper EXIT
fi
