#!/bin/bash

# Go to env
cd ./tests/ui

# Prepare environment
sed -i "s@bunkerity/bunkerweb:.*@bunkerweb-tests@" docker-compose.yml
sed -i "s@bunkerity/bunkerweb-scheduler:.*@scheduler-tests@" docker-compose.yml
sed -i "s@bunkerity/bunkerweb-ui:.*@ui-tests@" docker-compose.yml

# Start stack
docker-compose pull bw-docker-proxy app1
if [ $? -ne 0 ] ; then
    echo "❌ Pull failed"
    exit 1
fi
docker-compose up -d
if [ $? -ne 0 ] ; then
    echo "❌ Up failed"
    exit 1
fi

docker-compose stop ui-tests

i=0
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

# Start tests
docker-compose start ui-tests

# Exit
exit $?