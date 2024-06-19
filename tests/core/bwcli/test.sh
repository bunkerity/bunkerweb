#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "⌨️ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "⌨️ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "⌨️ Building bwcli stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose pull bw-docker
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⌨️ Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⌨️ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    MAKEFLAGS="-j $(nproc)" sudo pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt

    echo "⌨️ Installing Redis ..."
    export NEEDRESTART_SUSPEND=1
    export DEBIAN_FRONTEND=noninteractive
    sudo -E apt install --no-install-recommends -y redis
    redis-server --daemonize yes
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⌨️ Redis start failed ❌"
        exit 1
    fi
    echo "⌨️ Redis installed ✅"

    echo "USE_REDIS=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_HOST=127.0.0.1" | sudo tee -a /etc/bunkerweb/variables.env
    export USE_REDIS="yes"
    export REDIS_HOST="127.0.0.1"
    sudo touch /var/www/html/index.html
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

cleanup_stack () {
    echo "⌨️ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⌨️ Cleanup failed ❌"
        exit 1
    fi

    echo "⌨️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "⌨️ Running bwcli tests ..."

echo "⌨️ Starting stack ..."
if [ "$integration" == "docker" ] ; then
    docker compose up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⌨️ Up failed, retrying ... ⚠️"
        cleanup_stack
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "⌨️ Up failed ❌"
            exit 1
        fi
    fi
else
    sudo systemctl start bunkerweb
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⌨️ Start failed ❌"
        exit 1
    fi
fi

# Check if stack is healthy
echo "⌨️ Waiting for stack to be healthy ..."
i=0
if [ "$integration" == "docker" ] ; then
    while [ $i -lt 120 ] ; do
        containers=("bwcli-bw-1" "bwcli-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "⌨️ Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "⌨️ Docker stack is not healthy ❌"
        exit 1
    fi
else
    healthy="false"
    retries=0
    while [[ $healthy = "false" && $retries -lt 5 ]] ; do
        while [ $i -lt 120 ] ; do
            if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                echo "⌨️ Linux stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
            echo "⌨️ Linux stack is not healthy ❌"
            exit 1
        fi

        if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
            echo "⌨️ ⚠ Linux stack got an issue, restarting ..."
            sudo journalctl --rotate
            sudo journalctl --vacuum-time=1s
            cleanup_stack
            sudo systemctl start bunkerweb
            retries=$((retries+1))
        else
            healthy="true"
        fi
    done
    if [ "$retries" -ge 5 ] ; then
        echo "⌨️ Linux stack could not be healthy ❌"
        exit 1
    fi
fi

# Start tests

if [ "$integration" == "docker" ] ; then
    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
else
    sudo python3 linux.py
fi

# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "⌨️ Test bwcli failed ❌"
    echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
    if [ "$integration" == "docker" ] ; then
            docker compose logs bw bw-scheduler
    else
        sudo journalctl -u bunkerweb --no-pager
        echo "🛡️ Showing BunkerWeb error logs ..."
        sudo cat /var/log/bunkerweb/error.log
        echo "🛡️ Showing BunkerWeb access logs ..."
        sudo cat /var/log/bunkerweb/access.log
    fi
    exit 1
else
    echo "⌨️ Test bwcli succeeded ✅"
fi

echo "⌨️ Tests are done ! ✅"
