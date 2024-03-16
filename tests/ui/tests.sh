#!/bin/bash

integration=$1
test=$2

if [ -z "$integration" ] ; then
    echo "Please provide an integration name as argument ❌"
    exit 1
elif [ -z "$test" ] ; then
    echo "Please provide a test name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "Integration \"$integration\" is not supported ❌"
    exit 1
fi

test=$(basename "$test")

echo "🌐 Building UI stack for integration \"$integration\", test: $test ..."

cleanup_stack () {
    echo "🌐 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🌐 Cleanup failed ❌"
        exit 1
    fi

    echo "🌐 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

# Prepare environment
if [ "$integration" = "docker" ] ; then
    sed -i "s@bunkerity/bunkerweb:.*@bunkerweb-tests@" docker-compose.yml
    sed -i "s@bunkerity/bunkerweb-scheduler:.*@scheduler-tests@" docker-compose.yml
    sed -i "s@bunkerity/bunkerweb-ui:.*@ui-tests@" docker-compose.yml

    cleanup_stack

    echo "🌐 Starting stack ..."
    docker compose up --build -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🌐 Up failed, retrying ... ⚠️"
        cleanup_stack
        docker compose up --build -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🌐 Up failed ❌"
            exit 1
        fi
    fi
else
    sudo systemctl stop bunkerweb bunkerweb-ui
    sudo sed -i "/--bind \"127.0.0.1:7000\" &/c\        --bind \"127.0.0.1:7000\" --log-level debug &" /usr/share/bunkerweb/scripts/bunkerweb-ui.sh
    sudo mkdir /var/www/html/app1.example.com /var/www/html/app2.example.com /var/www/html/app3.example.com
    sudo touch /var/www/html/app1.example.com/index.html /var/www/html/app2.example.com/index.html /var/www/html/app3.example.com/index.html
    sudo find /etc/bunkerweb/configs/ -type f -exec rm -f {} \;
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
    export TEST_TYPE="linux"
fi

echo "🌐 Waiting for stack to be healthy ..."
i=0
if [ "$integration" == "docker" ] ; then
    while [ $i -lt 120 ] ; do
        containers=("ui-bw-1" "ui-bw-scheduler-1" "ui-bw-ui-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
            if [ "$check" = "" ] ; then
                echo "⚠️ Container $container is not healthy yet ..."
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker-compose logs
        echo "❌ Docker stack is not healthy"
        exit 1
    fi
else
    sudo systemctl start bunkerweb bunkerweb-ui
    healthy="false"
    retries=0
    while [[ $healthy = "false" && $retries -lt 5 ]] ; do
        while [ $i -lt 120 ] ; do
            if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                echo "🌐 Linux stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            echo "🛡️ Showing BunkerWeb journal logs ..."
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb UI journal logs ..."
            sudo journalctl -u bunkerweb-ui --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
            echo "🌐 Linux stack is not healthy ❌"
            exit 1
        fi

        if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
            echo "🌐 ⚠ Linux stack got an issue, restarting ..."
            sudo journalctl --rotate
            sudo journalctl --vacuum-time=1s
            cleanup_stack
            sudo systemctl start bunkerweb
            retries=$((retries+1))
        else
            healthy="true"
        fi
    done
    if [ $retries -ge 5 ] ; then
        echo "🌐 Linux stack could not be healthy ❌"
        exit 1
    fi
fi

# Start tests
if [ "$integration" == "docker" ] ; then
    echo "TEST_FILE=$test" > .env
    docker-compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "❌ Build failed"
        exit 1
    fi

    docker-compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from ui-tests
else
    python3 "$test"
fi

# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    if [ "$integration" == "docker" ] ; then
        rm -f .env
        docker compose logs
    else
        echo "🛡️ Showing BunkerWeb journal logs ..."
        sudo journalctl -u bunkerweb --no-pager
        echo "🛡️ Showing BunkerWeb UI journal logs ..."
        sudo journalctl -u bunkerweb-ui --no-pager
        echo "🛡️ Showing BunkerWeb UI logs ..."
        sudo cat /var/log/bunkerweb/ui.log
        echo "🛡️ Showing BunkerWeb UI access logs ..."
        sudo cat /var/log/bunkerweb/ui-access.log
        echo "🛡️ Showing BunkerWeb error logs ..."
        sudo cat /var/log/bunkerweb/error.log
        echo "🛡️ Showing BunkerWeb access logs ..."
        sudo cat /var/log/bunkerweb/access.log
        echo "🛡️ Showing Geckodriver logs ..."
        sudo cat geckodriver.log
    fi
    echo "❌ Tests failed"
    exit 1
fi
