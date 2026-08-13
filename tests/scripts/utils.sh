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

    database=$(redis-cli get database)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$database" ] ; then
        log "START" "⚠️" "💽 Failed to get database from redis server, clearing all database just in case"
        database="error"
    fi

    need_socket=$(redis-cli get need_socket)
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

            minikube_cmd_pids=$(redis-cli lrange minikube_cmd_pids 0 -1)
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
                redis-cli del minikube_cmd_pids > /dev/null
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

    if [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
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

            redis-cli set restart_crowdsec 1
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

        if [ "$type" == "ui" ] ; then
            docker exec -u 0 bunkerweb-linux systemctl stop bunkerweb-ui
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐧 Failed to stop BunkerWeb UI service"
                return 1
            fi
        elif [ "$type" == "api" ] ; then
            docker exec -u 0 bunkerweb-linux systemctl stop bunkerweb-api
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "🐧 Failed to stop BunkerWeb API service"
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
    restart_whole_stack=$(redis-cli get restart_whole_stack)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$restart_whole_stack" ] ; then
        log "UTILS" "❌" "💽 Failed to get restart_whole_stack from redis server"
        return 1
    fi

    restart_services=$(redis-cli get restart_services)
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

    database=$(redis-cli get database)
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
                postgresql) expected_image="postgres:18-alpine" ;;
                oracle) expected_image="gvenzl/oracle-free:23-slim-faststart" ;;
            esac

            existing_image=$(docker inspect -f '{{.Config.Image}}' bw-db 2>/dev/null || true)
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

        docker compose -f tests/docker/docker-compose.all-in-one.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "UTILS" "❌" "🍱 Failed to start BunkerWeb All-in-one"
            return 1
        fi
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
            elif [ "$type" == "api" ] ; then
                docker exec -u 0 bunkerweb-linux systemctl restart bunkerweb-api
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "UTILS" "❌" "🐧 Failed to restart BunkerWeb API service"
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

    if [ -f geckodriver.log ] ; then
        rm -f geckodriver.log
    fi

    if [ "$restart_whole_stack" -eq 1 ] ; then
        log "UTILS" "ℹ️ " "🔄 Restarted whole stack due to version change ✅"
    else
        log "UTILS" "ℹ️ " "🔄 Restarted current stack ✅"
    fi

    redis-cli set restart_whole_stack 0 > /dev/null
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "UTILS" "❌" "💽 Failed to reset restart_whole_stack in redis server"
        return 1
    fi

    redis-cli set restart_services 0 > /dev/null
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

    end=$(redis-cli get end)
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
            exit 1
        fi
    fi

    if [ "$end" -eq 0 ] && [ -z "${NO_LOG:-}" ]; then
        log_stack
    fi
    cleanup_stack "$exit_code"
}

if [ "$(basename "$0")" != "stop.sh" ] && [ "$(basename "$0")" != "log.sh" ] && [ "$(basename "$0")" != "test.sh" ] ; then
    # show logs and cleanup stack on exit
    trap exit_wrapper EXIT
fi
