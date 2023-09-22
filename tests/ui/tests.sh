#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "Integration \"$integration\" is not supported ❌"
    exit 1
fi

# Prepare environment
if [ "$integration" = "docker" ] ; then
    sed -i "s@bunkerity/bunkerweb:.*@bunkerweb-tests@" docker-compose.yml
    sed -i "s@bunkerity/bunkerweb-scheduler:.*@scheduler-tests@" docker-compose.yml
    sed -i "s@bunkerity/bunkerweb-ui:.*@ui-tests@" docker-compose.yml

    # Start stack
    docker-compose pull bw-docker-proxy app1
    if [ $? -ne 0 ] ; then
        echo "❌ Pull failed"
        exit 1
    fi

    echo "🤖 Starting stack ..."
    docker compose up -d
    if [ $? -ne 0 ] ; then
        echo "🤖 Up failed, retrying ... ⚠️"
        docker compose down -v --remove-orphans
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "🤖 Up failed ❌"
            exit 1
        fi
    fi
fi

i=0
if [ "$integration" == "docker" ] ; then
    while [ $i -lt 120 ] ; do
        containers=("ui_bw_1" "ui_bw-scheduler_1" "ui_bw-ui_1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
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
    while [ $i -lt 120 ] ; do
        check="$(sudo cat /var/log/bunkerweb/error.log | grep "BunkerWeb is ready")"
        if ! [ -z "$check" ] ; then
            echo "🤖 Linux stack is healthy ✅"
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
        echo "🤖 Linux stack is not healthy ❌"
        exit 1
    fi
fi

# Start tests
if [ "$integration" == "docker" ] ; then
    docker-compose -f docker-compose.test.yml build
    if [ $? -ne 0 ] ; then
        echo "❌ Build failed"
        exit 1
    fi

    docker-compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from ui-tests
else
    python3 main.py
fi

if [ $? -ne 0 ] ; then
    if [ "$integration" == "docker" ] ; then
        docker compose logs
    else
        sudo journalctl -u bunkerweb --no-pager
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

# Exit
exit 0