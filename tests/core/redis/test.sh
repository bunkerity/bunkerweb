#!/bin/bash

echo "🧰 Building redis stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🧰 Pull failed ❌"
    exit 1
fi

echo "🧰 Building custom redis image ..."
docker compose build bw-redis
if [ $? -ne 0 ] ; then
    echo "🧰 Build failed ❌"
    exit 1
fi

echo "🧰 Building tests images ..."
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🧰 Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_SCAN: "yes"@USE_REVERSE_SCAN: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_ANTIBOT: "cookie"@USE_ANTIBOT: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP: "0\.0\.0\.0/0"@BLACKLIST_IP: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT: "[0-9]*"@REDIS_PORT: "6379"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "1"@REDIS_DATABASE: "0"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "yes"@REDIS_SSL: "no"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🧰 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🧰 Down failed ❌"
        exit 1
    fi

    echo "🧰 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "activated" "reverse_scan" "antibot" "tweaked"
do
    if [ "$test" = "activated" ] ; then
        echo "🧰 Running tests with redis with default values ..."
    elif [ "$test" = "reverse_scan" ] ; then
        echo "🧰 Running tests with redis with reverse scan activated ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_SCAN: "no"@USE_REVERSE_SCAN: "yes"@' {} \;
    elif [ "$test" = "antibot" ] ; then
        echo "🧰 Running tests with redis with antibot cookie activated ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_SCAN: "yes"@USE_REVERSE_SCAN: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_ANTIBOT: "no"@USE_ANTIBOT: "cookie"@' {} \;
    elif [ "$test" = "tweaked" ] ; then
        echo "🧰 Running tests with redis' settings tweaked ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_ANTIBOT: "cookie"@USE_ANTIBOT: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT: "[0-9]*"@REDIS_PORT: "6380"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "0"@REDIS_DATABASE: "1"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "no"@REDIS_SSL: "yes"@' {} \;
    fi

    echo "🧰 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🧰 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "🧰 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🧰 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("redis-bw-1" "redis-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🧰 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🧰 Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests

    if [ $? -ne 0 ] ; then
        echo "🧰 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "🧰 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🧰 Tests are done ! ✅"
