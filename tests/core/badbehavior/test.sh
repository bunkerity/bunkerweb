#!/bin/bash

echo "📟 Building badbehavior stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "📟 Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "📟 Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BAD_BEHAVIOR: "no"@USE_BAD_BEHAVIOR: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_STATUS_CODES: "400 401 404 405 429 444"@BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_BAN_TIME: "5"@BAD_BEHAVIOR_BAN_TIME: "86400"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_THRESHOLD: "20"@BAD_BEHAVIOR_THRESHOLD: "10"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_COUNT_TIME: "5"@BAD_BEHAVIOR_COUNT_TIME: "60"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "📟 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "📟 Down failed ❌"
        exit 1
    fi

    echo "📟 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "activated" "deactivated" "status_codes" "ban_time" "threshold" "count_time"
do
    if [ "$test" = "activated" ] ; then
        echo "📟 Running tests with badbehavior activated ..."
    elif [ "$test" = "deactivated" ] ; then
        echo "📟 Running tests without badbehavior ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BAD_BEHAVIOR: "yes"@USE_BAD_BEHAVIOR: "no"@' {} \;
    elif [ "$test" = "status_codes" ] ; then
        echo "📟 Running tests with badbehavior's 403 status code removed from the list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BAD_BEHAVIOR: "no"@USE_BAD_BEHAVIOR: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"@BAD_BEHAVIOR_STATUS_CODES: "400 401 404 405 429 444"@' {} \;
    elif [ "$test" = "ban_time" ] ; then
        echo "📟 Running tests with badbehavior's ban time changed to 5 seconds ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_STATUS_CODES: "400 401 404 405 429 444"@BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_BAN_TIME: "86400"@BAD_BEHAVIOR_BAN_TIME: "5"@' {} \;
    elif [ "$test" = "threshold" ] ; then
        echo "📟 Running tests with badbehavior's threshold set to 20 ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_BAN_TIME: "5"@BAD_BEHAVIOR_BAN_TIME: "86400"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_THRESHOLD: "10"@BAD_BEHAVIOR_THRESHOLD: "20"@' {} \;
    elif [ "$test" = "count_time" ] ; then
        echo "📟 Running tests with badbehavior's count time set to 5 seconds ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_THRESHOLD: "20"@BAD_BEHAVIOR_THRESHOLD: "10"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_COUNT_TIME: "60"@BAD_BEHAVIOR_COUNT_TIME: "5"@' {} \;
    fi

    echo "📟 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "📟 Up failed ❌"
        exit 1
    fi

    # Check if stack is healthy
    echo "📟 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("badbehavior-bw-1" "badbehavior-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "📟 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "📟 Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "📟 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "📟 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "📟 Tests are done ! ✅"
