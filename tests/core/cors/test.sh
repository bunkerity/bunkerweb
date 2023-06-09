#!/bin/bash

echo "🛰️ Building cors stack ..."

# Starting stack
docker compose pull bw-docker app1
if [ $? -ne 0 ] ; then
    echo "🛰️ Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🛰️ Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CORS: "yes"@USE_CORS: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: ".*"$@CORS_ALLOW_ORIGIN: "\*"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_EXPOSE_HEADERS: "X-Test"@CORS_EXPOSE_HEADERS: "Content-Length,Content-Range"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_MAX_AGE: "3600"@CORS_MAX_AGE: "86400"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_CREDENTIALS: "yes"@CORS_ALLOW_CREDENTIALS: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_METHODS: "GET, HEAD, POST, OPTIONS"@CORS_ALLOW_METHODS: "GET, POST, OPTIONS"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_HEADERS: "X-Test"@CORS_ALLOW_HEADERS: "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🛰️ Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🛰️ Down failed ❌"
        exit 1
    fi

    echo "🛰️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🛰️ Initializing workspace ..."
docker compose -f docker-compose.init.yml up --build
if [ $? -ne 0 ] ; then
    echo "🛰️ Build failed ❌"
    exit 1
elif [[ $(stat -L -c "%a %g %u" www/app1.example.com/index.php) != "655 101 33" ]] ; then
    echo "🛰️ Init failed, permissions are not correct ❌"
    exit 1
fi

for test in "deactivated" "activated" "allow_origin" "tweaked_settings"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🛰️ Running tests without cors ..."
    elif [ "$test" = "activated" ] ; then
        echo "🛰️ Running tests with cors ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CORS: "no"@USE_CORS: "yes"@' {} \;
    elif [ "$test" = "allow_origin" ] ; then
        echo "🛰️ Running tests with a specific origin allowed only ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: "\*"@CORS_ALLOW_ORIGIN: "^http://app1\\\\.example\\\\.com$$"@' {} \;
    elif [ "$test" = "tweaked_settings" ] ; then
        echo "🛰️ Running tests with tweaked cors settings ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "no"@GENERATE_SELF_SIGNED_SSL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: ".*"$@CORS_ALLOW_ORIGIN: "^https://app1\\\\.example\\\\.com$$"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_EXPOSE_HEADERS: "Content-Length,Content-Range"@CORS_EXPOSE_HEADERS: "X-Test"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_MAX_AGE: "86400"@CORS_MAX_AGE: "3600"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_CREDENTIALS: "no"@CORS_ALLOW_CREDENTIALS: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_METHODS: "GET, POST, OPTIONS"@CORS_ALLOW_METHODS: "GET, HEAD, POST, OPTIONS"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_HEADERS: "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"@CORS_ALLOW_HEADERS: "X-Test"@' {} \;
    fi

    echo "🛰️ Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🛰️ Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "🛰️ Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🛰️ Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("cors-bw-1" "cors-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🛰️ Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🛰️ Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🛰️ Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "🛰️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🛰️ Tests are done ! ✅"
