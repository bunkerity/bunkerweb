#!/bin/bash

echo "⌨️ Building bunkernet stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "⌨️ Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "⌨️ Build failed ❌"
    exit 1
fi

cleanup_stack () {
    echo "⌨️ Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "⌨️ Down failed ❌"
        exit 1
    fi

    echo "⌨️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "⌨️ Running bwcli tests ..."

echo "⌨️ Starting stack ..."
docker compose up -d 2>/dev/null
if [ $? -ne 0 ] ; then
    echo "⌨️ Up failed, retrying ... ⚠️"
    manual=1
    cleanup_stack
    manual=0
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "⌨️ Up failed ❌"
        exit 1
    fi
fi

# Check if stack is healthy
echo "⌨️ Waiting for stack to be healthy ..."
i=0
while [ $i -lt 120 ] ; do
    containers=("bwcli-bw-1" "bwcli-bw-scheduler-1")
    healthy="true"
    for container in "${containers[@]}" ; do
        check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
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

# Start tests

docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests

if [ $? -ne 0 ] ; then
    echo "⌨️ Test bwcli failed ❌"
    echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
    docker compose logs bw bw-scheduler
    exit 1
else
    echo "⌨️ Test bwcli succeeded ✅"
fi

echo "⌨️ Tests are done ! ✅"
