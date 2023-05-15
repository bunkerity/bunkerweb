#!/bin/bash

echo "👮 Building modsecurity stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "👮 Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "👮 Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY: "no"@USE_MODSECURITY: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY_CRS: "no"@USE_MODSECURITY_CRS: "yes"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "👮 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "👮 Down failed ❌"
        exit 1
    fi

    echo "👮 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "activated" "crs_deactivated" "deactivated"
do
    if [ "$test" = "activated" ] ; then
        echo "👮 Running tests with modsecurity activated ..."
    elif [ "$test" = "crs_deactivated" ] ; then
        echo "👮 Running tests without the CRS ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY_CRS: "yes"@USE_MODSECURITY_CRS: "no"@' {} \;
    elif [ "$test" = "deactivated" ] ; then
        echo "👮 Running tests without modsecurity ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY_CRS: "no"@USE_MODSECURITY_CRS: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY: "yes"@USE_MODSECURITY: "no"@' {} \;
    fi

    echo "👮 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "👮 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "👮 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "👮 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("modsecurity-bw-1" "modsecurity-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "👮 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "👮 Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "👮 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "👮 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "👮 Tests are done ! ✅"
