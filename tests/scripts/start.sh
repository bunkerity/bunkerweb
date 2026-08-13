#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"

log "START" "ℹ️ " "Building BunkerWeb stack for integration \"$integration\" ..."

BW_VERSION="$(cat /tmp/bw_version.txt)"
export BW_VERSION

if redis-cli ping | grep -q "PONG" ; then
    log "START" "ℹ️ " "💽 Redis server is healthy ✅"
else
    log "START" "❌" "💽 Redis server is not healthy"
    exit 1
fi

database=$(redis-cli get database)
# shellcheck disable=SC2181
if [ $? -ne 0 ] || [ -z "$database" ] ; then
    log "START" "⚠️" "💽 Failed to get database from redis server"
    if [ "$type" == "ui" ] || [ "$integration" == "Autoconf" ] || [ "$integration" == "Kubernetes" ] ; then
        log "START" "⚠️" "💽 Setting database to mariadb"
        database="mariadb"
    else
        log "START" "⚠️" "💽 Setting database to sqlite"
        database="sqlite"
    fi
fi

if [ "$database" != "sqlite" ] ; then
    if [ "$integration" == "Kubernetes" ] ; then
        db_pods=$(kubectl get pods -n bunkerweb-db -o jsonpath="{.items[*].metadata.name}")
        if echo "$db_pods" | grep -vq "bunkerweb-db-" ; then
            kubectl apply -f tests/misc/k8s/"$database".yml
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "☸️ Apply failed for $database"
                exit 1
            fi
        fi
    else
        containers=$(docker ps -a --format "{{.Names}}" | grep "bw-db")
        if echo "$containers" | grep -vq "bw-db" ; then
            robust_docker_pull "tests/misc/docker/$database.yml" "$database"
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Pull failed for $database after multiple attempts"
                exit 1
            fi

            docker compose -f tests/misc/docker/"$database".yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "⚠️" "🐳 Up failed for $database, retrying ..."
                docker compose -f tests/misc/docker/"$database".yml down -v
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "🐳 Down failed for $database"
                    exit 1
                fi
                docker compose -f tests/misc/docker/"$database".yml up -d
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "🐳 Up failed for $database"
                    exit 1
                fi
            fi
        fi
    fi
elif [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] || [ "$integration" == "All-in-one" ] ; then
    network=$(docker network ls --format "{{.Name}}" | grep "bw-db")
    if [ -z "$network" ] ; then
        docker network create --driver bridge --subnet 10.10.10.0/24 bw-db --label "com.docker.compose.network=bw-db" > /dev/null
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Network creation failed for bw-db"
            exit 1
        fi
    fi
fi

redis_type=$(redis-cli get redis_type)
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to get redis_type from redis server"
    exit 1
fi

if [ -n "$redis_type" ] ; then
    if [ "$integration" != "Kubernetes" ] ; then
        if [ "$redis_type" != "valkey" ] ; then
            containers=$(docker ps -a --format "{{.Names}}" | grep "redis-master")
            if echo "$containers" | grep -vq "redis-master" ; then
                robust_docker_pull "tests/misc/docker/redis-master.yml" "redis-master"
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "🐳 Pull failed for redis-master after multiple attempts"
                    exit 1
                fi

                docker compose -f tests/misc/docker/redis-master.yml up -d
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "⚠️" "🐳 Up failed for redis-master, retrying ..."
                    docker compose -f tests/misc/docker/redis-master.yml down -v
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "❌" "🐳 Down failed for redis-master"
                        exit 1
                    fi
                    docker compose -f tests/misc/docker/redis-master.yml up -d
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "❌" "🐳 Up failed for redis-master"
                        exit 1
                    fi
                fi
            fi

            if [ "$redis_type" == "sentinel" ] ; then
                containers=$(docker ps -a --format "{{.Names}}" | grep "redis-sentinel-1")
                if echo "$containers" | grep -vq "redis-sentinel-1" ; then
                    robust_docker_pull "tests/misc/docker/sentinel.yml" "sentinel stack"
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "❌" "🐳 Pull failed for sentinel stack after multiple attempts"
                        exit 1
                    fi

                    docker compose -f tests/misc/docker/sentinel.yml up -d
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "⚠️" "🐳 Up failed for sentinel stack, retrying ..."
                        docker compose -f tests/misc/docker/sentinel.yml down -v
                        # shellcheck disable=SC2181
                        if [ $? -ne 0 ] ; then
                            log "START" "❌" "🐳 Down failed for sentinel stack"
                            exit 1
                        fi
                        docker compose -f tests/misc/docker/sentinel.yml up -d
                        # shellcheck disable=SC2181
                        if [ $? -ne 0 ] ; then
                            log "START" "❌" "🐳 Up failed for sentinel stack"
                            exit 1
                        fi
                    fi
                fi
            fi

            if [ "$redis_type" == "valkey-sentinel" ] ; then
                containers=$(docker ps -a --format "{{.Names}}" | grep "valkey-sentinel-1")
                if echo "$containers" | grep -vq "valkey-sentinel-1" ; then
                    robust_docker_pull "tests/misc/docker/valkey-sentinel.yml" "valkey-sentinel stack"
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "❌" "🐳 Pull failed for valkey-sentinel stack after multiple attempts"
                        exit 1
                    fi

                    docker compose -f tests/misc/docker/valkey-sentinel.yml up -d
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "⚠️" "🐳 Up failed for valkey-sentinel stack, retrying ..."
                        docker compose -f tests/misc/docker/valkey-sentinel.yml down -v
                        # shellcheck disable=SC2181
                        if [ $? -ne 0 ] ; then
                            log "START" "❌" "🐳 Down failed for valkey-sentinel stack"
                            exit 1
                        fi
                        docker compose -f tests/misc/docker/valkey-sentinel.yml up -d
                        # shellcheck disable=SC2181
                        if [ $? -ne 0 ] ; then
                            log "START" "❌" "🐳 Up failed for valkey-sentinel stack"
                            exit 1
                        fi
                    fi
                fi
            fi
        else
            containers=$(docker ps -a --format "{{.Names}}" | grep "valkey")
            if echo "$containers" | grep -vq "valkey" ; then
                robust_docker_pull "tests/misc/docker/valkey.yml" "valkey"
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "🐳 Pull failed for valkey after multiple attempts"
                    exit 1
                fi

                docker compose -f tests/misc/docker/valkey.yml up -d
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "⚠️" "🐳 Up failed for valkey, retrying ..."
                    docker compose -f tests/misc/docker/valkey.yml down -v
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "❌" "🐳 Down failed for valkey"
                        exit 1
                    fi
                    docker compose -f tests/misc/docker/valkey.yml up -d
                    # shellcheck disable=SC2181
                    if [ $? -ne 0 ] ; then
                        log "START" "❌" "🐳 Up failed for valkey"
                        exit 1
                    fi
                fi
            fi
        fi
    else
        if [ "$redis_type" != "valkey" ] ; then
            redis_pods=$(kubectl get pods -n redis -o jsonpath="{.items[*].metadata.name}")
            if echo "$redis_pods" | grep -vq "redis-master-" ; then
                kubectl apply -f tests/misc/k8s/redis-master.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for redis-master"
                    exit 1
                fi

                kubectl apply -f /tmp/redis-master-secrets.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for redis-master-secrets"
                    exit 1
                fi
            fi

            if [ "$redis_type" == "sentinel" ] && echo "$redis_pods" | grep -vq "redis-sentinel-" ; then
                kubectl apply -f tests/misc/k8s/redis-sentinel.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for redis-sentinel stack"
                    exit 1
                fi

                kubectl apply -f /tmp/redis-slave-secrets.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for redis-slave-secrets"
                    exit 1
                fi

                kubectl apply -f /tmp/redis-sentinel-secrets.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for redis-sentinel-secrets"
                    exit 1
                fi
            fi
        else
            redis_pods=$(kubectl get pods -n redis -o jsonpath="{.items[*].metadata.name}")
            if [ "$redis_type" == "valkey-sentinel" ] && echo "$redis_pods" | grep -vq "valkey-sentinel-" ; then
                kubectl apply -f tests/misc/k8s/valkey-sentinel.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for valkey-sentinel"
                    exit 1
                fi

                kubectl apply -f /tmp/valkey-sentinel-secrets.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for valkey-sentinel-secrets"
                    exit 1
                fi
            elif echo "$redis_pods" | grep -vq "valkey-" ; then
                kubectl apply -f tests/misc/k8s/valkey.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for valkey"
                    exit 1
                fi

                kubectl apply -f /tmp/valkey-secrets.yml
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    log "START" "❌" "☸️ Apply failed for valkey-secrets"
                    exit 1
                fi
            fi
        fi
    fi
fi

# Starting stack
if [ -f /tmp/example_stack.txt ] && [ "$integration" == "Docker" ] ; then
    # A Docker example ships the whole stack, BunkerWeb included, so the framework
    # deploys that instead of composing one of its own. Autoconf and Kubernetes examples
    # ship only their application layer and land further down, on top of this stack.
    example_stack="$(cat /tmp/example_stack.txt)"
    example_hook setup "$integration" || exit 1
    log "START" "ℹ️ " "📕 Starting example stack from $example_stack ..."
    compose_up "$example_stack" "example stack" "📕" || exit 1
elif [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
    docker compose -f tests/docker/docker-compose.bunkerweb.yml up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "⚠️" "🐳 Up failed for BunkerWeb, retrying ..."
        docker compose -f tests/docker/docker-compose.bunkerweb.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Down failed for BunkerWeb"
            exit 1
        fi
        docker compose -f tests/docker/docker-compose.bunkerweb.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Up failed for BunkerWeb"
            exit 1
        fi
    fi

    # Since 1.7 the scheduler only dispatches: it posts jobs to the API, which queues
    # them on the broker for bw-worker to execute. All three belong to every stack,
    # whatever the test type — without them the stack boots and runs zero jobs.
    # The scheduler compose owns bw-storage and the API and worker attach to it as
    # external, so create it here: they come up first and a clean host has no volume.
    docker volume create bw-storage > /dev/null
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "❌" "🐳 Failed to create the bw-storage volume"
        exit 1
    fi

    compose_up "tests/docker/docker-compose.api.yml" "API" || exit 1
    compose_up "tests/docker/docker-compose.worker.yml" "worker" || exit 1

    docker compose -f tests/docker/docker-compose.scheduler.yml up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "⚠️" "🐳 Up failed for scheduler, retrying ..."
        docker compose -f tests/docker/docker-compose.scheduler.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Down failed for scheduler"
            exit 1
        fi
        docker compose -f tests/docker/docker-compose.scheduler.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Up failed for scheduler"
            exit 1
        fi
    fi

    if [ "$integration" == "Autoconf" ] ; then
        docker compose -f tests/docker/docker-compose.autoconf.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "⚠️" "🔩 Up failed for autoconf, retrying ..."
            docker compose -f tests/docker/docker-compose.autoconf.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🔩 Down failed for autoconf"
                exit 1
            fi
            docker compose -f tests/docker/docker-compose.autoconf.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🔩 Up failed for autoconf"
                exit 1
            fi
        fi

        robust_docker_pull "tests/misc/docker/docker-socket-proxy.yml" "bw-docker"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Pull failed for bw-docker after multiple attempts"
            exit 1
        fi

        docker compose -f tests/misc/docker/docker-socket-proxy.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "⚠️" "🐳 Up failed for bw-docker, retrying ..."
            docker compose -f tests/misc/docker/docker-socket-proxy.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Down failed for bw-docker"
                exit 1
            fi
            docker compose -f tests/misc/docker/docker-socket-proxy.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Up failed for bw-docker"
                exit 1
            fi
        fi
    fi

    if [ "$type" == "ui" ] ; then
        docker compose -f tests/docker/docker-compose.ui.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "⚠️" "🐳 Up failed for UI, retrying ..."
            docker compose -f tests/docker/docker-compose.ui.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Down failed for UI"
                exit 1
            fi
            docker compose -f tests/docker/docker-compose.ui.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Up failed for UI"
                exit 1
            fi
        fi
    fi
elif [ "$integration" == "All-in-one" ] ; then
    docker compose -f tests/docker/docker-compose.all-in-one.yml up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "⚠️" "🍱 Up failed for BunkerWeb All-in-one, retrying ..."
        docker compose -f tests/docker/docker-compose.all-in-one.yml down -v
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🍱 Down failed for BunkerWeb All-in-one"
            exit 1
        fi
        docker compose -f tests/docker/docker-compose.all-in-one.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🍱 Up failed for BunkerWeb All-in-one"
            exit 1
        fi
    fi

    need_socket=$(redis-cli get need_socket)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        need_socket=0
    fi

    if [ "$need_socket" == "1" ] ; then
        robust_docker_pull "tests/misc/docker/docker-socket-proxy.yml" "bw-docker"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Pull failed for bw-docker after multiple attempts"
            exit 1
        fi

        docker compose -f tests/misc/docker/docker-socket-proxy.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "⚠️" "🐳 Up failed for bw-docker, retrying ..."
            docker compose -f tests/misc/docker/docker-socket-proxy.yml down -v
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Down failed for bw-docker"
                exit 1
            fi
            docker compose -f tests/misc/docker/docker-socket-proxy.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Up failed for bw-docker"
                exit 1
            fi
        fi
    fi
elif [ "$integration" == "Kubernetes" ] ; then
    # Apply manifests via Kustomize for dynamic image tags
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
    # The API is applied for every type: the 1.7 scheduler dispatches its jobs through
    # it, so a cluster without it runs none.
    cp tests/k8s/bunkerweb-api.yml "$KZ_DIR/bunkerweb-api.yml"
    if [ "$type" == "ui" ] ; then
        cp tests/k8s/bunkerweb-ui.yml "$KZ_DIR/bunkerweb-ui.yml"
    fi

    {
        echo "resources:";
        echo "- bunkerweb.yml";
        echo "- bunkerweb-api.yml";
        if [ "$type" == "ui" ] ; then
            echo "- bunkerweb-ui.yml";
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
        echo "- name: localhost:5000/bunkerity/bunkerweb-api";
        echo "  newName: ${NEW_PREFIX}/bunkerweb-api";
        echo "  newTag: ${NEW_TAG}";
        echo "- name: localhost:5000/bunkerity/bunkerweb-worker";
        echo "  newName: ${NEW_PREFIX}/bunkerweb-worker";
        echo "  newTag: ${NEW_TAG}";
        if [ "$type" == "ui" ] ; then
            echo "- name: localhost:5000/bunkerity/bunkerweb-ui";
            echo "  newName: ${NEW_PREFIX}/bunkerweb-ui";
            echo "  newTag: ${NEW_TAG}";
        fi
    } > "$KZ_DIR/kustomization.yaml"

    kubectl apply -k "$KZ_DIR"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "❌" "☸️ Apply failed for BunkerWeb (kustomize)"
        exit 1
    fi

    # Cleanup temporary kustomize directory
    rm -rf "$KZ_DIR"

    kubectl apply -f tests/misc/k8s/lb.yml
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "❌" "☸️ Apply failed for lb"
        exit 1
    fi

    kubectl apply -f /tmp/secrets.yml
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "❌" "☸️ Apply failed for secrets"
        exit 1
    fi

    if [ "$type" == "ui" ] ; then
        kubectl apply -f /tmp/secrets-ui.yml
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "☸️ Apply failed for secrets-ui"
            exit 1
        fi
    fi

    kubectl apply -f /tmp/secrets-api.yml
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "START" "❌" "☸️ Apply failed for secrets-api"
        exit 1
    fi
else
    if $IS_FREEBSD ; then
        service bunkerweb start
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐚 Start failed for BunkerWeb"
            exit 1
        fi

        service bunkerweb_scheduler start
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐚 Start failed for BunkerWeb Scheduler"
            exit 1
        fi

        if [ "$type" == "ui" ] ; then
            service bunkerweb_ui start
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐚 Start failed for BunkerWeb UI"
                exit 1
            fi
        elif [ "$type" == "api" ] ; then
            service bunkerweb_api start
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐚 Start failed for BunkerWeb API"
                exit 1
            fi
        fi
    else
        docker exec -u 0 bunkerweb-linux systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐧 Start failed for BunkerWeb"
            exit 1
        fi

        docker exec -u 0 bunkerweb-linux systemctl start bunkerweb-scheduler
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐧 Start failed for BunkerWeb Scheduler"
            exit 1
        fi

        if [ "$type" == "ui" ] ; then
            docker exec -u 0 bunkerweb-linux systemctl start bunkerweb-ui
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐧 Start failed for BunkerWeb UI"
                exit 1
            fi
        elif [ "$type" == "api" ] ; then
            docker exec -u 0 bunkerweb-linux systemctl start bunkerweb-api
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐧 Start failed for BunkerWeb API"
                exit 1
            fi
        fi
    fi
fi

restart_crowdsec=$(redis-cli get restart_crowdsec)
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "START" "❌" "💽 Failed to get restart_crowdsec from redis server"
    exit 1
fi

if [ "$integration" != "All-in-one" ] && [ "$restart_crowdsec" == "1" ] ; then
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

    docker compose -f tests/misc/docker/crowdsec.yml exec crowdsec cscli hub update
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "UTILS" "❌" "🦙 Failed to update CrowdSec hub"
        return 1
    fi

    redis-cli set restart_crowdsec 0 > /dev/null
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "UTILS" "❌" "🦙 Failed to set restart_crowdsec flag in redis server"
        return 1
    fi
fi

if [ -f /tmp/example_stack.txt ] && [ "$integration" != "Docker" ] ; then
    # Autoconf and Kubernetes examples carry only their application layer: their services
    # configure BunkerWeb through container labels or ingress annotations, and the stack
    # they attach to is the one started above. They take the slot the generated
    # services.yml would have used.
    example_stack="$(cat /tmp/example_stack.txt)"
    example_hook setup "$integration" || exit 1
    log "START" "ℹ️ " "📕 Deploying example services from $example_stack ..."

    if [ "$integration" == "Kubernetes" ] ; then
        kubectl apply -f "$example_stack"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "📕 Apply failed for the example services"
            exit 1
        fi
    else
        compose_up "$example_stack" "example services" "📕" || exit 1
    fi
elif [ -f /tmp/services.yml ] ; then
    if [ "$integration" == "Kubernetes" ] ; then
        kubectl apply -f /tmp/services.yml
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "☸️ Apply failed for services"
            exit 1
        fi
    else
        robust_docker_pull "/tmp/services.yml" "dockerized services"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "❌" "🐳 Pull failed for dockerized services after multiple attempts"
            exit 1
        fi

        docker compose -f /tmp/services.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "START" "⚠️" "🐳 Up failed for dockerized services, retrying ..."
            cleanup_stack
            docker compose -f /tmp/services.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "START" "❌" "🐳 Up failed for dockerized services"
                exit 1
            fi
        fi
    fi
fi
