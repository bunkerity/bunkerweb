#!/bin/bash

echo "⭕ Building errors stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "⭕ Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "⭕ Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@ERRORS: "403=/errors/403.html"@ERRORS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@INTERCEPTED_ERROR_CODES: "400 401 404 405 413 429 500 501 502 503 504"@INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "⭕ Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "⭕ Down failed ❌"
        exit 1
    fi

    echo "⭕ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "default" "custom_403" "without_403"
do
    if [ "$test" = "default" ] ; then
        echo "⭕ Running tests with default configuration ..."
    elif [ "$test" = "custom_403" ] ; then
        echo "⭕ Running tests with a custom 403 page ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@ERRORS: ""@ERRORS: "403=/errors/403.html"@' {} \;
    elif [ "$test" = "without_403" ] ; then
        echo "⭕ Running tests without a 403 being intercepted ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@ERRORS: "403=/errors/403.html"@ERRORS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"@INTERCEPTED_ERROR_CODES: "400 401 404 405 413 429 500 501 502 503 504"@' {} \;
    fi

    echo "⭕ Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "⭕ Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "⭕ Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "⭕ Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("errors-bw-1" "errors-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "⭕ Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "⭕ Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests

    if [ $? -ne 0 ] ; then
        echo "⭕ Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "⭕ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "⭕ Tests are done ! ✅"
